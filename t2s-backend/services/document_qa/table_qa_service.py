from __future__ import annotations

import json
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from core.database import SessionLocal

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.orm import Session

from services.common.embeddings import get_embeddings
from services.common.llm_service import common_llm_service
from services.document_qa.table_semantic_service import TableSemanticService

logger = logging.getLogger(__name__)

MAX_RETRIEVAL_POOL = 120
MAX_REWRITTEN_QUERIES = 8
MAX_PARALLEL_SUB_QUERIES = 4

_TABLE_QA_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "你是表格语义树问答助手。请只根据表格摘要、字段和候选树路径回答用户问题。\n"
                "如果候选内容不足以回答，请说明未找到足够依据。\n"
                "涉及数值、指标或层级路径时，优先引用路径和字段。"
            ),
        ),
        (
            "human",
            (
                "表格信息：\n{table_info}\n\n"
                "用户问题：{question}\n\n"
                "对话历史：\n{history}\n\n"
                "候选树路径：\n{evidence}"
            ),
        ),
    ]
)

_RERANK_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是表格问答候选排序器。只输出候选编号 JSON 数组，例如 [2,1,4]，不要输出解释。",
        ),
        (
            "human",
            "问题：{question}\n\n候选：\n{candidates}\n\n请按最能回答问题的顺序返回最多 {top_k} 个编号。",
        ),
    ]
)

_QUERY_REWRITE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "你是表格问答查询规划器。"
                "只输出合法 JSON 对象，不要输出 Markdown、解释或其他内容。"
            ),
        ),
        (
            "human",
            (
                "请把用户问题改写成适合独立检索表格语义树的子问题。\n\n"
                "规则：\n"
                "1. 如果问题同时询问多个并列对象、指标或统计项，拆成多个完整子问题。\n"
                "2. 每个子问题必须保留学校、院系、年份、地区、单位和统计口径等共同限定条件。\n"
                "3. 每个子问题必须能够独立检索，不能只输出名词片段。\n"
                "4. 如果只有一个明确问题，原样返回。\n"
                "5. 子问题最多 {max_queries} 个。\n\n"
                "示例：\n"
                "用户问题：湖南师范大学的博士研究生，普通本科生，硕士研究生有多少\n"
                "输出："
                '{{"sub_questions":['
                '"湖南师范大学的博士研究生有多少",'
                '"湖南师范大学的普通本科生有多少",'
                '"湖南师范大学的硕士研究生有多少"'
                "]}}\n\n"
                "用户问题：\n{question}"
            ),
        ),
    ]
)

_PIPELINE_SYNTHESIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "你是跨表格问答结果综合助手。"
                "只能依据提供的 table_answers 和 evidence_paths 回答，"
                "不得使用外部知识，不得编造数据。"
            ),
        ),
        (
            "human",
            (
                "原始问题：\n{question}\n\n"
                "各子问题的表格问答结果：\n{table_answers}\n\n"
                "回答要求：\n"
                "1. 逐个覆盖所有子问题。\n"
                "2. 合并来自不同表格的互补证据。\n"
                "3. 说明关键数据来自哪张表。\n"
                "4. 对没有有效证据的子问题明确说明证据不足。\n"
                "5. 只输出最终回答，不要输出 JSON。"
            ),
        ),
    ]
)


@dataclass
class TableQACandidate:
    text: str
    score: float
    source: str
    table_id: str | None = None
    table_title: str | None = None


class TableQAService:
    def __init__(self, semantic_service: TableSemanticService | None = None) -> None:
        self.semantic_service = semantic_service or TableSemanticService()

    def answer(
        self,
        db: Session,
        *,
        table_id: str,
        question: str,
        top_k: int = 8,
        history: list[dict] | None = None,
    ) -> dict:
        query = str(question or "").strip()
        if not query:
            raise ValueError("Question must not be empty")

        artifact = self.semantic_service.get_table(db, table_id)
        artifact_payload = self.semantic_service.artifact_to_response(artifact)
        tree_payload = self.semantic_service.get_table_tree(db, table_id)
        paths = _string_list(tree_payload.get("tree_path_text")) or artifact_payload["tree_path_text"]
        fields = _string_list(tree_payload.get("candidate_fields")) or artifact_payload["candidate_fields"]
        metrics = _string_list(tree_payload.get("tree_metric_names")) or artifact_payload["tree_metric_names"]

        candidates = self.retrieve(
            db,
            question=query,
            artifact=artifact_payload,
            paths=paths,
            fields=fields,
            top_k=max(int(top_k) * 2, int(top_k)),
        )
        candidates = self._rerank_with_llm(db, question=query, candidates=candidates, top_k=top_k)

        symbolic_answer = self._answer_symbolic(
            question=query,
            artifact=artifact_payload,
            paths=paths,
            fields=fields,
            metrics=metrics,
        )
        if symbolic_answer:
            mode = "symbolic"
            answer = symbolic_answer
        else:
            mode = "llm"
            answer = self._answer_with_llm(
                db,
                question=query,
                artifact=artifact_payload,
                candidates=candidates,
                history=history or [],
            )
            if not answer:
                mode = "retrieval"
                answer = self._format_retrieval_answer(candidates)

        return {
            "table_id": str(table_id),
            "table_ids": [str(table_id)],
            "answer": answer,
            "mode": mode,
            "evidence_paths": [item.text for item in candidates],
            "candidates": [item.__dict__ for item in candidates],
        }

    def answer_tree(
        self,
        db: Session,
        *,
        question: str,
        tree: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        top_k: int = 12,
        use_llm: bool = True,
        history: list[dict] | None = None,
    ) -> dict:
        query = str(question or "").strip()
        if not query:
            raise ValueError("Question must not be empty")
        if not isinstance(tree, dict) or not tree:
            raise ValueError("Tree must not be empty")

        metadata = metadata or {}
        paths, metrics = _flatten_tree_for_qa(tree)
        fields = _string_list(metadata.get("candidate_fields")) or metrics
        artifact = {
            "table_id": str(metadata.get("table_id") or ""),
            "table_title": str(metadata.get("table_title") or metadata.get("filename") or "临时语义树"),
            "summary_text": str(metadata.get("summary_text") or metadata.get("description") or ""),
            "row_count": metadata.get("row_count", "-"),
            "column_count": metadata.get("column_count", "-"),
        }
        if not artifact["summary_text"]:
            artifact["summary_text"] = f"临时语义树包含 {len(paths)} 条可检索路径。"

        candidates = self.retrieve(
            db,
            question=query,
            artifact=artifact,
            paths=paths,
            fields=fields,
            top_k=max(int(top_k) * 2, int(top_k)),
        )
        if use_llm:
            candidates = self._rerank_with_llm(db, question=query, candidates=candidates, top_k=top_k)
        else:
            candidates = candidates[: max(1, min(int(top_k), 50))]

        symbolic_answer = self._answer_symbolic(
            question=query,
            artifact=artifact,
            paths=paths,
            fields=fields,
            metrics=metrics,
        )
        if symbolic_answer:
            mode = "symbolic"
            answer = symbolic_answer
        elif use_llm:
            answer = self._answer_with_llm(
                db,
                question=query,
                artifact=artifact,
                candidates=candidates,
                history=history or [],
            )
            mode = "semantic_retrieval_llm" if answer else "semantic_retrieval"
            if not answer:
                answer = self._format_retrieval_answer(candidates)
        else:
            mode = "semantic_retrieval"
            answer = self._format_retrieval_answer(candidates)

        table_id = artifact["table_id"] or None
        return {
            "table_id": table_id,
            "table_ids": [table_id] if table_id else [],
            "answer": answer,
            "mode": mode,
            "evidence_paths": [item.text for item in candidates],
            "candidates": [item.__dict__ for item in candidates],
        }

    def answer_global(
        self,
        db: Session,
        *,
        question: str,
        kb_id: int | None = None,
        top_k: int = 8,
        history: list[dict] | None = None,
    ) -> dict:
        query = str(question or "").strip()
        if not query:
            raise ValueError("Question must not be empty")

        sub_questions = self._build_query_plan(db, question=query, use_llm=True)["sub_questions"]
        table_hits = self.semantic_service.search_tables(db, question=query, kb_id=kb_id, top_k=20)
        if table_hits:
            tables = []
            for hit in table_hits:
                try:
                    tables.append(self.semantic_service.get_table(db, str(hit.get("table_id"))))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("load table from search hit failed: table_id=%s error=%s", hit.get("table_id"), exc)
        else:
            tables = self.semantic_service.list_tables(db, kb_id=kb_id, limit=80)
        candidates: list[TableQACandidate] = []
        table_summaries: list[str] = []
        for table in tables:
            artifact_payload = self.semantic_service.artifact_to_response(table)
            table_summaries.append(
                f"{artifact_payload['table_id']} | {artifact_payload['table_title']} | {artifact_payload['summary_text']}"
            )
            try:
                tree_payload = self.semantic_service.get_table_tree(db, str(table.table_id))
            except Exception as exc:  # noqa: BLE001
                logger.warning("load table tree failed during global QA: table_id=%s error=%s", table.table_id, exc)
                tree_payload = {}
            paths = _string_list(tree_payload.get("tree_path_text")) or artifact_payload["tree_path_text"]
            fields = _string_list(tree_payload.get("candidate_fields")) or artifact_payload["candidate_fields"]
            for question_index, sub_question in enumerate(sub_questions, start=1):
                per_table = self.retrieve(
                    db,
                    question=sub_question,
                    artifact=artifact_payload,
                    paths=paths,
                    fields=fields,
                    top_k=min(max(2, int(top_k)), 6),
                )
                for item in per_table:
                    item.table_id = str(artifact_payload["table_id"])
                    item.table_title = str(artifact_payload["table_title"])
                    item.source = f"{item.source}:{item.table_id}:q{question_index}"
                    item.text = f"子问题：{sub_question}\n{item.text}"
                    candidates.append(item)

        candidates = _dedupe_candidates(candidates)
        candidates.sort(key=lambda item: item.score, reverse=True)
        candidates = candidates[: max(1, min(int(top_k) * 3, 30))]
        candidates = self._rerank_with_llm(db, question=query, candidates=candidates, top_k=top_k)
        table_ids = _dedupe_strings([str(item.table_id) for item in candidates if item.table_id])
        artifact = {
            "table_id": "global",
            "table_title": "多表检索",
            "summary_text": "\n".join(table_summaries[:20]) or "当前没有可用表格语义树。",
            "row_count": "-",
            "column_count": "-",
        }
        answer = self._answer_with_llm(
            db,
            question=query,
            artifact=artifact,
            candidates=candidates,
            history=history or [],
        )
        mode = "global_llm"
        if not answer:
            mode = "global_retrieval"
            answer = self._format_retrieval_answer(candidates)

        return {
            "table_id": None,
            "table_ids": table_ids,
            "answer": answer,
            "mode": mode,
            "evidence_paths": [item.text for item in candidates],
            "candidates": [item.__dict__ for item in candidates],
        }

    def answer_pipeline(
        self,
        db: Session,
        *,
        question: str,
        kb_id: int | None = None,
        top_k: int = 3,
        evidence_limit: int = 12,
        use_llm: bool = True,
        history: list[dict] | None = None,
    ) -> dict:
        query = str(question or "").strip()
        if not query:
            raise ValueError("Question must not be empty")

        query_plan = self._build_query_plan(
            db,
            question=query,
            use_llm=use_llm,
        )
        retrieval_questions = query_plan["sub_questions"]
        query_results = self._answer_retrieval_questions(
            db,
            retrieval_questions=retrieval_questions,
            kb_id=kb_id,
            top_k=top_k,
            evidence_limit=evidence_limit,
            use_llm=use_llm,
            history=history or [],
        )

        table_answers = [
            answer
            for result in query_results
            for answer in result.get("table_answers", [])
        ]

        table_candidates = _dedupe_pipeline_candidates(
            [
                {
                    **_pipeline_table_payload(hit),
                    "matched_queries": [str(result.get("question") or "")],
                }
                for result in query_results
                for hit in result.get("table_candidates", [])
            ]
        )

        if not table_candidates:
            return {
                "answer": "当前未检索到相关表格，无法回答问题。",
                "mode": "pipeline_no_table_candidates",
                "original_question": query,
                "retrieval_question": retrieval_questions[0] if len(retrieval_questions) == 1 else query,
                "retrieval_questions": retrieval_questions,
                "query_plan": query_plan,
                "query_results": _trim_pipeline_query_results(query_results),
                "table_candidates": [],
                "table_answers": [],
            }

        answer, synthesis_mode = self._synthesize_pipeline_answer(
            db,
            question=query,
            table_answers=table_answers,
            use_llm=use_llm,
        )

        return {
            "answer": answer,
            "mode": "pipeline_qa",
            "synthesis_mode": synthesis_mode,
            "original_question": query,
            "retrieval_questions": retrieval_questions,
            "query_plan": query_plan,
            "query_results": query_results,
            "table_candidates": table_candidates,
            "table_answers": table_answers,
        }

    def _answer_retrieval_questions(
        self,
        db: Session,
        *,
        retrieval_questions: list[str],
        kb_id: int | None,
        top_k: int,
        evidence_limit: int,
        use_llm: bool,
        history: list[dict],
    ) -> list[dict[str, Any]]:
        if not retrieval_questions:
            return []

        # 只有一个子问题时，不创建线程，直接复用当前请求的 Session。
        if len(retrieval_questions) == 1:
            return [
                self._answer_single_retrieval_question(
                    db,
                    retrieval_question=retrieval_questions[0],
                    kb_id=kb_id,
                    top_k=top_k,
                    evidence_limit=evidence_limit,
                    use_llm=use_llm,
                    history=history,
                )
            ]

        results: list[dict[str, Any] | None] = [None] * len(retrieval_questions)
        worker_count = min(len(retrieval_questions), MAX_PARALLEL_SUB_QUERIES)

        with ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix="table-qa",
        ) as executor:
            future_to_index = {
                executor.submit(
                    self._answer_retrieval_question_with_session,
                    retrieval_question=retrieval_question,
                    kb_id=kb_id,
                    top_k=top_k,
                    evidence_limit=evidence_limit,
                    use_llm=use_llm,
                    history=list(history),
                ): index
                for index, retrieval_question in enumerate(retrieval_questions)
            }

            for future in as_completed(future_to_index):
                index = future_to_index[future]
                # 不在这里吞异常。
                # LLM、数据库或其他关键调用失败时直接向上抛出。
                results[index] = future.result()

        return [result for result in results if result is not None]

    def _answer_retrieval_question_with_session(
        self,
        *,
        retrieval_question: str,
        kb_id: int | None,
        top_k: int,
        evidence_limit: int,
        use_llm: bool,
        history: list[dict],
    ) -> dict[str, Any]:
        worker_db = SessionLocal()
        try:
            return self._answer_single_retrieval_question(
                worker_db,
                retrieval_question=retrieval_question,
                kb_id=kb_id,
                top_k=top_k,
                evidence_limit=evidence_limit,
                use_llm=use_llm,
                history=history,
            )
        finally:
            worker_db.close()

    def _answer_single_retrieval_question(
        self,
        db: Session,
        *,
        retrieval_question: str,
        kb_id: int | None,
        top_k: int,
        evidence_limit: int,
        use_llm: bool,
        history: list[dict],
    ) -> dict[str, Any]:
        hits = self.semantic_service.search_tables(
            db,
            question=retrieval_question,
            kb_id=kb_id,
            top_k=max(1, min(int(top_k), 20)),
        )

        question_answers: list[dict[str, Any]] = []
        for hit in hits:
            table_payload = _pipeline_table_payload(hit)
            table_id = str(hit.get("table_id") or "").strip()

            if not table_id:
                question_answers.append(
                    {
                        "sub_question": retrieval_question,
                        "retrieval_question": retrieval_question,
                        "table": table_payload,
                        "error": "table_id is empty",
                    }
                )
                continue

            try:
                tree_payload = self.semantic_service.get_table_tree(db, table_id)
                metadata = {
                    "table_id": table_id,
                    "table_title": hit.get("table_title"),
                    "filename": hit.get("file_name") or hit.get("filename"),
                    "sheet_name": hit.get("sheet_name"),
                    "summary_text": hit.get("summary_text"),
                    "candidate_fields": hit.get("candidate_fields", []),
                    "row_count": hit.get("row_count"),
                    "column_count": hit.get("column_count"),
                }
                qa_result = self.answer_tree(
                    db,
                    question=retrieval_question,
                    tree=tree_payload.get("tree") or {},
                    metadata=metadata,
                    top_k=evidence_limit,
                    use_llm=use_llm,
                    history=history,
                )
                question_answers.append(
                    {
                        "sub_question": retrieval_question,
                        "retrieval_question": retrieval_question,
                        "table": table_payload,
                        "qa": qa_result,
                    }
                )
            except RuntimeError:
                # 按要求：LLM 不可用或关键调用失败时直接报错，不转换成“证据不足”。
                raise
            except Exception as exc:  # noqa: BLE001
                # 单张表的数据异常可以记录，让其他候选表继续处理。
                logger.warning(
                    "table QA failed: question=%s table_id=%s error=%s",
                    retrieval_question,
                    table_id,
                    exc,
                )
                question_answers.append(
                    {
                        "sub_question": retrieval_question,
                        "retrieval_question": retrieval_question,
                        "table": table_payload,
                        "error": f"{exc.__class__.__name__}: {exc}",
                    }
                )
        return {
            "question": retrieval_question,
            "table_candidates": hits,
            "table_answers": question_answers,
        }

    def _synthesize_pipeline_answer(
        self,
        db: Session,
        *,
        question: str,
        table_answers: list[dict[str, Any]],
        use_llm: bool,
    ) -> tuple[str, str]:
        compact_answers = _compact_pipeline_answers(table_answers)

        if not compact_answers:
            return (
                "当前检索到的表格中没有足够证据回答该问题。",
                "insufficient_evidence",
            )

        # 调用方明确关闭 LLM 时，允许使用确定性格式化。
        if not use_llm:
            return (
                _format_pipeline_answers(compact_answers),
                "deterministic",
            )

        model = common_llm_service.get_chat_model(db)
        if model is None:
            raise RuntimeError(
                "Pipeline 最终综合失败：当前没有可用的 LLM"
            )

        payload = json.dumps(
            compact_answers[:20],
            ensure_ascii=False,
            default=str,
            indent=2,
        )

        try:
            chain = (
                _PIPELINE_SYNTHESIS_PROMPT
                | model
                | StrOutputParser()
            )

            answer = str(
                chain.invoke(
                    {
                        "question": question,
                        "table_answers": payload,
                    }
                )
            ).strip()
        except Exception as exc:
            logger.exception(
                "pipeline final synthesis LLM invocation failed"
            )
            raise RuntimeError(
                "Pipeline 最终综合 LLM 调用失败："
                f"{exc.__class__.__name__}: {exc}"
            ) from exc

        if not answer:
            raise RuntimeError(
                "Pipeline 最终综合失败：LLM 返回内容为空"
            )

        return answer, "llm_synthesis"

    def _build_query_plan(
        self,
        db: Session,
        *,
        question: str,
        use_llm: bool,
    ) -> dict[str, Any]:
        normalized_question = str(question or "").strip()
        if not normalized_question:
            raise ValueError("Question must not be empty")

        if not use_llm:
            sub_questions = _split_question_heuristically(normalized_question)
            return {
                "original_question": normalized_question,
                "sub_questions": sub_questions,
                "rewritten": sub_questions != [normalized_question],
                "source": (
                    "heuristic"
                    if sub_questions != [normalized_question]
                    else "original"
                ),
            }

        model = common_llm_service.get_chat_model(db)
        if model is None:
            raise RuntimeError("表格问题拆分失败：当前没有可用的 LLM")

        try:
            chain = _QUERY_REWRITE_PROMPT | model | StrOutputParser()
            output = str(
                chain.invoke(
                    {
                        "question": normalized_question,
                        "max_queries": MAX_REWRITTEN_QUERIES,
                    }
                )
            ).strip()
        except Exception as exc:
            logger.exception("table QA query rewrite failed")
            raise RuntimeError(
                f"表格问题拆分 LLM 调用失败：{exc.__class__.__name__}: {exc}"
            ) from exc

        sub_questions = _parse_sub_questions_output(
            normalized_question,
            output,
        )

        if not sub_questions:
            raise RuntimeError(
                "表格问题拆分失败：LLM 返回内容不是有效的 sub_questions JSON"
            )

        return {
            "original_question": normalized_question,
            "sub_questions": sub_questions,
            "rewritten": sub_questions != [normalized_question],
            "source": "llm",
        }

    def retrieve(
        self,
        db: Session,
        *,
        question: str,
        artifact: dict,
        paths: list[str],
        fields: list[str],
        top_k: int,
    ) -> list[TableQACandidate]:
        query = str(question or "").strip()
        candidate_texts: list[tuple[str, str]] = [
            (str(artifact.get("summary_text") or ""), "summary"),
            (f"字段: {'、'.join(fields)}", "fields"),
        ]
        candidate_texts.extend((path, "tree_path") for path in paths)

        scored = [
            TableQACandidate(
                text=text,
                score=self._lexical_score(query, text),
                source=source,
                table_id=str(artifact.get("table_id") or "") or None,
                table_title=str(artifact.get("table_title") or "") or None,
            )
            for text, source in candidate_texts
            if text
        ]
        scored.sort(key=lambda item: item.score, reverse=True)
        pool = [item for item in scored if item.score > 0][:MAX_RETRIEVAL_POOL]
        if len(pool) < min(len(scored), MAX_RETRIEVAL_POOL):
            seen = {item.text for item in pool}
            pool.extend(item for item in scored if item.text not in seen and len(pool) < MAX_RETRIEVAL_POOL)

        if not pool:
            return []

        try:
            semantic_scores = self._semantic_scores(db, query, [item.text for item in pool])
        except Exception as exc:  # noqa: BLE001
            logger.warning("table QA semantic retrieve failed: %s", exc)
            semantic_scores = []

        if semantic_scores:
            max_lexical = max((item.score for item in pool), default=1.0) or 1.0
            for item, semantic_score in zip(pool, semantic_scores):
                normalized_lexical = item.score / max_lexical
                item.score = 0.65 * float(semantic_score) + 0.35 * normalized_lexical

        pool.sort(key=lambda item: item.score, reverse=True)
        return pool[: max(1, min(int(top_k), 30))]

    @staticmethod
    def _lexical_score(question: str, text: str) -> float:
        query = str(question or "").lower()
        target = str(text or "").lower()
        if not query or not target:
            return 0.0

        terms = [term for term in re.split(r"[\s,，。；;：:、|/\\()（）]+", query) if term]
        score = sum(2.0 for term in terms if len(term) > 1 and term in target)
        query_chars = {char for char in query if "\u4e00" <= char <= "\u9fff"}
        if query_chars:
            text_chars = {char for char in target if "\u4e00" <= char <= "\u9fff"}
            score += len(query_chars & text_chars) / max(1, len(query_chars))
        return float(score)

    @staticmethod
    def _semantic_scores(db: Session, question: str, texts: list[str]) -> list[float]:
        embeddings = get_embeddings(db)
        query_vector = embeddings.embed_query(question)
        doc_vectors = embeddings.embed_documents(texts)
        return [_cosine_similarity(query_vector, vector) for vector in doc_vectors]

    def _rerank_with_llm(
        self,
        db: Session,
        *,
        question: str,
        candidates: list[TableQACandidate],
        top_k: int,
    ) -> list[TableQACandidate]:
        safe_top_k = max(1, min(int(top_k), 20))

        # 候选不足两个时不需要调用 LLM。
        if len(candidates) <= 1:
            return candidates[:safe_top_k]

        model = common_llm_service.get_chat_model(db)
        if model is None:
            raise RuntimeError(
                "表格问答候选排序失败：当前没有可用的大模型"
            )

        candidate_text = "\n\n".join(
            (
                f"{index + 1}. "
                f"table_id={item.table_id or '-'} "
                f"title={item.table_title or '-'} "
                f"source={item.source} "
                f"score={item.score:.4f}\n"
                f"{item.text[:900]}"
            )
            for index, item in enumerate(candidates[:30])
        )

        try:
            chain = _RERANK_PROMPT | model | StrOutputParser()
            output = str(
                chain.invoke(
                    {
                        "question": question,
                        "candidates": candidate_text,
                        "top_k": safe_top_k,
                    }
                )
            ).strip()
        except Exception as exc:
            logger.exception("table QA LLM rerank failed")
            raise RuntimeError(
                "表格问答候选排序大模型调用失败："
                f"{exc.__class__.__name__}: {exc}"
            ) from exc

        order = _extract_rank_ids(
            output,
            limit=len(candidates),
        )

        if not order:
            raise RuntimeError(
                "表格问答候选排序失败：大模型返回格式无效"
            )

        selected: list[TableQACandidate] = []
        used: set[int] = set()

        for number in order:
            index = number - 1
            if (
                index < 0
                or index >= len(candidates)
                or index in used
            ):
                continue

            used.add(index)
            selected.append(candidates[index])

            if len(selected) >= safe_top_k:
                break

        # LLM 返回数量不足时，用原始排序补足。
        if len(selected) < safe_top_k:
            selected.extend(
                item
                for index, item in enumerate(candidates)
                if index not in used
            )

        return selected[:safe_top_k]

    def _answer_symbolic(
        self,
        *,
        question: str,
        artifact: dict,
        paths: list[str],
        fields: list[str],
        metrics: list[str],
    ) -> str:
        query = str(question or "")
        if _asks_fields(query):
            names = metrics or fields
            if not names:
                return ""
            return f"这张表共有 {len(fields)} 个字段，主要指标包括：{'、'.join(names[:80])}。"

        if re.search(r"多少\s*行|几\s*行|记录数|数据量|行数", query):
            return (
                f"表格《{artifact.get('table_title')}》共有 {artifact.get('row_count')} 行数据、"
                f"{artifact.get('column_count')} 个字段。"
            )

        operation = _detect_operation(query)
        if not operation:
            return ""

        metric_name = _select_symbolic_metric(query, paths=paths, metrics=metrics)
        if not metric_name:
            return ""

        scope_values = _matched_hierarchy_scope_values(
            query,
            paths=paths,
            metric_name=metric_name,
        )
        values = _extract_numeric_values(
            paths,
            metric_name=metric_name,
            scope_values=scope_values,
        )
        if not values:
            return ""
        if {str(item.get("unit") or "") for item in values} != {"number"}:
            return ""
        if operation in {"sum", "avg"} and not scope_values and not _asks_whole_table_scope(query):
            return ""
        if operation in {"max", "min"} and len(values) < 2:
            return ""

        metric_names = [metric_name]
        if operation == "sum":
            total = sum(item["value"] for item in values)
            return _format_metric_answer("合计", metric_names, total, values[:8])
        if operation == "avg":
            avg = sum(item["value"] for item in values) / len(values)
            return _format_metric_answer("平均值", metric_names, avg, values[:8])
        if operation == "max":
            top = max(values, key=lambda item: item["value"])
            return _format_extreme_answer("最大值", top)
        if operation == "min":
            bottom = min(values, key=lambda item: item["value"])
            return _format_extreme_answer("最小值", bottom)
        return ""

    def _answer_with_llm(
        self,
        db: Session,
        *,
        question: str,
        artifact: dict,
        candidates: list[TableQACandidate],
        history: list[dict],
    ) -> str:
        # 没有检索证据时不调用 LLM。
        # 这是“证据不足”，不是 LLM 故障。
        if not candidates:
            return ""

        model = common_llm_service.get_chat_model(db)
        if model is None:
            raise RuntimeError(
                "表格问答失败：当前没有可用的大模型"
            )

        table_info = (
            f"table_id: {artifact.get('table_id')}\n"
            f"标题: {artifact.get('table_title')}\n"
            f"摘要: {artifact.get('summary_text')}\n"
            f"规模: {artifact.get('row_count')} 行 / "
            f"{artifact.get('column_count')} 列"
        )

        evidence = "\n".join(
            (
                f"[{index + 1}] "
                f"score={item.score:.4f} "
                f"source={item.source} "
                f"table_id={item.table_id or '-'}\n"
                f"{item.text}"
            )
            for index, item in enumerate(candidates)
        )

        history_text = "\n".join(
            (
                f"Q: {item.get('question', '')}\n"
                f"A: {item.get('answer', '')}"
            )
            for item in history[-8:]
            if str(item.get("question") or "").strip()
        ) or "（无）"

        try:
            chain = _TABLE_QA_PROMPT | model | StrOutputParser()
            answer = str(
                chain.invoke(
                    {
                        "table_info": table_info,
                        "question": question,
                        "history": history_text,
                        "evidence": evidence,
                    }
                )
            ).strip()
        except Exception as exc:
            logger.exception("table QA LLM answer failed")
            raise RuntimeError(
                "表格问答大模型调用失败："
                f"{exc.__class__.__name__}: {exc}"
            ) from exc

        if not answer:
            raise RuntimeError(
                "表格问答失败：大模型返回内容为空"
            )

        return answer

    @staticmethod
    def _format_retrieval_answer(candidates: list[TableQACandidate]) -> str:
        if not candidates:
            return "当前表格语义树中未找到与问题相关的内容。"
        lines = ["找到以下相关表格路径："]
        for item in candidates[:8]:
            prefix = f"表 {item.table_title}：" if item.table_title else ""
            lines.append(f"- {prefix}{item.text}")
        return "\n".join(lines)


def _pipeline_table_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "score": float(row.get("score") or 0.0),
        "table_id": str(row.get("table_id") or ""),
        "batch_id": str(row.get("batch_id") or ""),
        "filename": str(row.get("file_name") or row.get("filename") or ""),
        "file_name": str(row.get("file_name") or row.get("filename") or ""),
        "sheet_name": str(row.get("sheet_name") or ""),
        "table_title": str(row.get("table_title") or ""),
        "tree_object": str(row.get("tree_object") or row.get("tree_object_name") or ""),
        "tree_object_name": str(row.get("tree_object_name") or row.get("tree_object") or ""),
        "tree_metric_names": row.get("tree_metric_names") if isinstance(row.get("tree_metric_names"), list) else [],
        "source": str(row.get("source") or ""),
    }


def _dedupe_pipeline_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for candidate in candidates:
        key = str(candidate.get("table_id") or candidate.get("tree_object") or len(order))
        if key not in by_key:
            by_key[key] = dict(candidate)
            order.append(key)
            continue
        existing = by_key[key]
        if float(candidate.get("score") or 0.0) > float(existing.get("score") or 0.0):
            matched_queries = existing.get("matched_queries", [])
            existing.update(candidate)
            existing["matched_queries"] = matched_queries
        matched = existing.setdefault("matched_queries", [])
        for query in candidate.get("matched_queries", []):
            if query and query not in matched:
                matched.append(query)
    return [by_key[key] for key in order]


def _trim_pipeline_query_results(query_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trimmed: list[dict[str, Any]] = []
    for item in query_results:
        answers = item.get("table_answers", [])
        trimmed.append(
            {
                "question": item.get("question"),
                "table_candidates": [_pipeline_table_payload(hit) for hit in item.get("table_candidates", [])],
                "table_answer_count": len(answers),
                "answerable_count": sum(1 for answer in answers if (answer.get("qa") or {}).get("evidence_paths")),
            }
        )
    return trimmed


def _compact_pipeline_answers(
    table_answers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []

    for item in table_answers:
        table = item.get("table") or {}
        qa = item.get("qa") or {}

        answer = str(qa.get("answer") or "").strip()
        evidence_paths = qa.get("evidence_paths") or []
        error = str(item.get("error") or "").strip()

        compact_item = {
            "sub_question": item.get("sub_question"),
            "table": {
                "table_id": table.get("table_id"),
                "table_title": table.get("table_title"),
                "filename": (
                    table.get("filename")
                    or table.get("file_name")
                ),
                "sheet_name": table.get("sheet_name"),
            },
            "answer": answer or None,
            "evidence_paths": evidence_paths[:8],
            "error": error or None,
        }

        # 有答案、证据或错误才加入最终综合内容。
        if answer or evidence_paths or error:
            compact.append(compact_item)

    return compact


def _format_pipeline_answers(
    compact_answers: list[dict[str, Any]],
) -> str:
    lines = ["表格问答结果："]

    for item in compact_answers:
        table = item.get("table") or {}

        table_name = (
            table.get("table_title")
            or table.get("filename")
            or table.get("table_id")
            or "未知表格"
        )

        sub_question = (
            str(item.get("sub_question") or "").strip()
        )
        answer = str(item.get("answer") or "").strip()
        error = str(item.get("error") or "").strip()

        prefix = (
            f"{sub_question}："
            if sub_question
            else ""
        )

        if answer:
            lines.append(
                f"- {prefix}{answer}（来源：{table_name}）"
            )
        elif error:
            lines.append(
                f"- {prefix}处理失败：{error}"
            )
        else:
            lines.append(
                f"- {prefix}当前证据不足。"
            )

    return "\n".join(lines)


def _asks_fields(question: str) -> bool:
    return bool(re.search(r"字段|列名|指标|有哪些列|有哪些指标|主要指标", question))


def _detect_operation(question: str) -> str:
    if re.search(r"合计|总和|求和|总计|加总", question):
        return "sum"
    if re.search(r"平均|均值|avg", question, flags=re.IGNORECASE):
        return "avg"
    if re.search(r"最大|最高|最多|max", question, flags=re.IGNORECASE):
        return "max"
    if re.search(r"最小|最低|最少|min", question, flags=re.IGNORECASE):
        return "min"
    return ""


def _select_symbolic_metric(question: str, *, paths: list[str], metrics: list[str]) -> str:
    normalized_question = _normalize_symbolic_text(question)
    configured_metrics = {
        _normalize_symbolic_text(name)
        for name in metrics
        if _normalize_symbolic_text(name)
    }
    path_metrics: list[str] = []
    for field, _, _ in _iter_numeric_path_values(paths):
        normalized_field = _normalize_symbolic_text(field)
        if configured_metrics and normalized_field not in configured_metrics:
            continue
        if normalized_field and normalized_field in normalized_question and field not in path_metrics:
            path_metrics.append(field)

    if not path_metrics:
        return ""
    longest_length = max(len(_normalize_symbolic_text(name)) for name in path_metrics)
    longest = [name for name in path_metrics if len(_normalize_symbolic_text(name)) == longest_length]
    return longest[0] if len(longest) == 1 else ""


def _matched_hierarchy_scope_values(
    question: str,
    *,
    paths: list[str],
    metric_name: str,
) -> list[str]:
    normalized_question = _normalize_symbolic_text(question)
    normalized_metric = _normalize_symbolic_text(metric_name)
    matches: list[str] = []
    for path in paths:
        for segment in str(path).split("|")[:-1]:
            if " - " not in segment:
                continue
            value = segment.split(" - ", 1)[1].strip()
            normalized_value = _normalize_symbolic_text(value)
            if (
                len(normalized_value) < 2
                or normalized_value == normalized_metric
                or re.fullmatch(r"[-+]?\d+(?:\.\d+)?%?", normalized_value)
                or normalized_value not in normalized_question
            ):
                continue
            if normalized_value not in matches:
                matches.append(normalized_value)
    return matches


def _asks_whole_table_scope(question: str) -> bool:
    return bool(re.search(r"全表|整张表|全部|所有(?:记录|行|项目|条目|数据)|各项", question))


def _extract_numeric_values(
    paths: list[str],
    *,
    metric_name: str,
    scope_values: list[str],
) -> list[dict[str, Any]]:
    normalized_metric = _normalize_symbolic_text(metric_name)
    rows: list[dict[str, Any]] = []
    for field, raw_value, path in _iter_numeric_path_values(paths):
        normalized_path = _normalize_symbolic_text(path)
        if any(scope not in normalized_path for scope in scope_values):
            continue
        if _normalize_symbolic_text(field) != normalized_metric:
            continue
        value = _parse_number(raw_value)
        if value is None:
            continue
        rows.append(
            {
                "field": field,
                "value": value,
                "unit": "%" if raw_value.strip().endswith("%") else "number",
                "path": path,
            }
        )
    return rows


def _iter_numeric_path_values(paths: list[str]):
    pattern = re.compile(
        r"(?:^|[|;])\s*([^|;:：]+?)\s*[:：]\s*"
        r"([-+]?\d[\d,]*(?:\.\d+)?%?)(?=\s*(?:;|$))"
    )
    for path in paths:
        path_text = str(path)
        for match in pattern.finditer(path_text):
            yield match.group(1).strip(), match.group(2), path_text


def _normalize_symbolic_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _parse_number(value: str) -> float | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    is_percent = text.endswith("%")
    if is_percent:
        text = text[:-1]
    try:
        number = float(text)
    except ValueError:
        return None
    return number / 100.0 if is_percent else number


def _format_metric_answer(label: str, metric_names: list[str], value: float, evidence: list[dict[str, Any]]) -> str:
    metric_text = "、".join(metric_names[:6]) if metric_names else "匹配指标"
    lines = [f"{metric_text}的{label}为 {_format_number(value)}。"]
    if evidence:
        lines.append("参考路径：")
        lines.extend(f"- {item['path']}" for item in evidence)
    return "\n".join(lines)


def _format_extreme_answer(label: str, item: dict[str, Any]) -> str:
    return f"{item['field']}的{label}为 {_format_number(item['value'])}。\n参考路径：\n- {item['path']}"


def _format_number(value: float) -> str:
    if math.isfinite(value) and float(value).is_integer():
        return str(int(value))
    return f"{value:.6g}"


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _extract_rank_ids(text: str, *, limit: int) -> list[int]:
    numbers = [int(item) for item in re.findall(r"\d+", str(text or ""))]
    return [number for number in numbers if 1 <= number <= limit]


def _parse_sub_questions_output(
    original_question: str,
    output: str,
) -> list[str]:
    value = str(output or "").strip()

    if value.startswith("```"):
        value = re.sub(
            r"^```(?:json)?",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()
        value = re.sub(r"```$", "", value).strip()

    start = value.find("{")
    end = value.rfind("}")
    if start >= 0 and end > start:
        value = value[start : end + 1]

    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return []

    if not isinstance(payload, dict):
        return []

    return _normalize_rewritten_queries(
        original_question,
        payload.get("sub_questions"),
    )


def _split_question_heuristically(question: str) -> list[str]:
    original = str(question or "").strip()
    if not original:
        return []

    body = original.rstrip("？?")
    suffix = _detect_question_suffix(body)

    if suffix is None:
        return [original]

    stem = body[: -len(suffix["matched"])].strip()
    parts = _split_parallel_parts(stem)

    if len(parts) < 2:
        return [original]

    prefix, first_item = _split_shared_prefix(parts[0])
    if not prefix or not first_item:
        return [original]

    rewritten: list[str] = []

    for index, raw_part in enumerate(parts):
        item = first_item if index == 0 else raw_part.strip()
        if not item:
            continue

        if "的" not in item and not item.startswith(prefix):
            item = f"{prefix}{item}"

        rewritten.append(f"{item}{suffix['normalized']}")

    return (
        _normalize_rewritten_queries(original, rewritten)
        or [original]
    )


def _detect_question_suffix(
    question: str,
) -> dict[str, str] | None:
    # 不要把“人数”“数量”作为后缀的一部分移除，
    # 否则容易生成“人数人数是多少”。
    suffixes = [
        ("分别有多少", "有多少"),
        ("分别是多少", "是多少"),
        ("总数是多少", "总数是多少"),
        ("数量是多少", "数量是多少"),
        ("人数是多少", "人数是多少"),
        ("有多少", "有多少"),
        ("是多少", "是多少"),
        ("有哪些", "有哪些"),
        ("是什么", "是什么"),
    ]

    for matched, normalized in suffixes:
        if question.endswith(matched):
            return {
                "matched": matched,
                "normalized": normalized,
            }

    return None


def _split_parallel_parts(
    text: str,
) -> list[str]:
    value = str(text or "").strip()

    if not value:
        return []

    # 明确标点具有最高可信度。
    punctuation_parts = [
        part.strip()
        for part in re.split(
            r"[，,、；;]+",
            value,
        )
        if part.strip()
    ]

    # 已经通过标点拆成多个部分时，
    # 不再继续按“和、及、与”切分，
    # 避免规则过度处理。
    if len(punctuation_parts) > 1:
        return punctuation_parts

    part = punctuation_parts[0]

    # 只处理共享前缀后的指标部分。
    #
    # 和平区的本科生和研究生
    # prefix = 和平区的
    # tail = 本科生和研究生
    if "的" not in part:
        return [part]

    separator_index = part.rfind("的")
    prefix = part[
        : separator_index + 1
    ]
    tail = part[
        separator_index + 1 :
    ].strip()

    tail_parts = _split_by_conjunction(
        tail
    )

    if len(tail_parts) <= 1:
        return [part]

    return [
        f"{prefix}{tail_parts[0]}",
        *tail_parts[1:],
    ]


_CONJUNCTION_PATTERN = re.compile(
    r"以及|并且|和|及|与"
)


def _split_by_conjunction(
    text: str,
) -> list[str]:
    value = str(text or "").strip()

    if not value:
        return []

    return _split_conjunction_segment(
        value
    )


def _split_conjunction_segment(
    value: str,
) -> list[str]:
    matches = list(
        _CONJUNCTION_PATTERN.finditer(
            value
        )
    )

    # 从最右边开始判断。
    #
    # 中华人民共和国和美国
    # 会先识别最后一个“和”；
    # “共和”中的“和”右侧只有一个“国”，
    # 因此不会被继续拆分。
    for match in reversed(matches):
        left = value[
            : match.start()
        ].strip()

        right = value[
            match.end() :
        ].strip()

        if not _valid_parallel_fragment(
            left
        ):
            continue

        if not _valid_parallel_fragment(
            right
        ):
            continue

        return [
            *_split_conjunction_segment(
                left
            ),
            right,
        ]

    return [value]


def _valid_parallel_fragment(
    value: str,
) -> bool:
    text = str(value or "").strip()

    if len(text) < 2:
        return False

    if text.endswith("的"):
        return False

    if re.search(
        r"[，,、；;？?]",
        text,
    ):
        return False

    return True


def _split_shared_prefix(
    first_part: str,
) -> tuple[str, str]:
    separator_index = first_part.rfind("的")

    if separator_index < 0:
        return "", first_part

    prefix = first_part[: separator_index + 1].strip()
    item = first_part[separator_index + 1 :].strip()

    return prefix, item


def _normalize_rewritten_queries(
    original_question: str,
    values: Any,
) -> list[str]:
    if not isinstance(values, list):
        return []

    result: list[str] = []
    seen: set[str] = set()
    original_key = re.sub(
        r"\s+",
        "",
        original_question.lower(),
    )

    for value in values:
        text = re.sub(
            r"\s+",
            " ",
            str(value or ""),
        ).strip()

        text = re.sub(
            r"^[\d一二三四五六七八九十]+[.、)）]\s*",
            "",
            text,
        )

        if not text:
            continue

        key = re.sub(r"\s+", "", text.lower())
        if key in seen:
            continue

        seen.add(key)
        result.append(text)

        if len(result) >= MAX_REWRITTEN_QUERIES:
            break

    if len(result) > 1:
        without_original = [
            text
            for text in result
            if re.sub(r"\s+", "", text.lower())
            != original_key
        ]
        if without_original:
            result = without_original

    return result or [original_question]


def _dedupe_candidates(candidates: list[TableQACandidate]) -> list[TableQACandidate]:
    output: list[TableQACandidate] = []
    seen: set[tuple[str | None, str]] = set()
    for item in candidates:
        key = (item.table_id, item.text)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _dedupe_strings(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _flatten_tree_for_qa(tree: dict[str, Any]) -> tuple[list[str], list[str]]:
    paths: list[str] = []
    metrics: list[str] = []

    def walk(value: Any, path: list[str]) -> None:
        if isinstance(value, dict):
            if value and all(not isinstance(item, (dict, list)) for item in value.values()):
                leaf_parts = []
                for key, item in value.items():
                    key_text = str(key)
                    metrics.append(key_text)
                    leaf_parts.append(f"{key_text}: {item}")
                prefix = " | ".join(path)
                paths.append(f"{prefix} | {'; '.join(leaf_parts)}" if prefix else "; ".join(leaf_parts))
                return
            for key, item in value.items():
                key_text = str(key)
                metrics.append(key_text)
                walk(item, [*path, key_text])
            return

        if isinstance(value, list):
            for index, item in enumerate(value, start=1):
                walk(item, [*path, f"第{index}项"])
            return

        if path:
            paths.append(f"{' | '.join(path)}: {value}")

    walk(tree, [])
    return _dedupe_strings(paths), _dedupe_strings(metrics)[:160]
