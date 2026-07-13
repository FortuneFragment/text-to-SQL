import pytest
from services.document_qa.table_qa_service import TableQAService, _split_question_heuristically
from services.document_qa.table_search_index_service import _merge_hits

def test_split_question_heuristically_chinese():
    res = _split_question_heuristically("湖南师范大学的博士研究生，普通本科生，硕士研究生有多少")
    assert res == [
        "湖南师范大学的博士研究生有多少",
        "湖南师范大学的普通本科生有多少",
        "湖南师范大学的硕士研究生有多少",
    ]

def test_split_question_heuristically_no_suffix():
    res = _split_question_heuristically("湖南师范大学的博士研究生")
    assert res == ["湖南师范大学的博士研究生"]


def test_answer_retrieval_questions_parallel(monkeypatch):
    import sys
    from services.document_qa.table_qa_service import TableQAService
    from unittest.mock import MagicMock
    
    table_qa_service_module = sys.modules["services.document_qa.table_qa_service"]
    service = TableQAService()
    
    # Mock single question execution to return its text as mock result
    monkeypatch.setattr(
        service,
        "_answer_single_retrieval_question",
        lambda db, retrieval_question, **kwargs: {
            "question": retrieval_question,
            "table_candidates": [],
            "table_answers": [{"answer": f"Ans for {retrieval_question}"}]
        }
    )
    
    mock_session = MagicMock()
    monkeypatch.setattr(
        table_qa_service_module,
        "SessionLocal",
        lambda: mock_session
    )
    
    questions = ["Q1", "Q2", "Q3"]
    results = service._answer_retrieval_questions(
        db=mock_session,
        retrieval_questions=questions,
        kb_id=1,
        top_k=3,
        evidence_limit=5,
        use_llm=True,
        history=[]
    )
    
    # Verify order is preserved
    assert [r["question"] for r in results] == ["Q1", "Q2", "Q3"]


def test_synthesize_pipeline_answer_no_evidence():
    from services.document_qa.table_qa_service import TableQAService
    service = TableQAService()
    ans, mode = service._synthesize_pipeline_answer(
        object(),
        question="test",
        table_answers=[],
        use_llm=True
    )
    assert ans == "当前检索到的表格中没有足够证据回答该问题。"
    assert mode == "insufficient_evidence"


def test_synthesize_pipeline_answer_no_llm():
    from services.document_qa.table_qa_service import TableQAService
    service = TableQAService()
    table_answers = [{
        "sub_question": "sub Q",
        "table": {"table_title": "T1"},
        "qa": {"answer": "T1 answer", "evidence_paths": ["path1"]}
    }]
    ans, mode = service._synthesize_pipeline_answer(
        object(),
        question="test",
        table_answers=table_answers,
        use_llm=False
    )
    assert "T1 answer" in ans
    assert "T1" in ans
    assert mode == "deterministic"


def test_synthesize_pipeline_answer_llm_not_configured(monkeypatch):
    import sys
    from services.document_qa.table_qa_service import TableQAService
    table_qa_service_module = sys.modules["services.document_qa.table_qa_service"]
    service = TableQAService()
    table_answers = [{
        "sub_question": "sub Q",
        "table": {"table_title": "T1"},
        "qa": {"answer": "T1 answer", "evidence_paths": ["path1"]}
    }]
    monkeypatch.setattr(
        table_qa_service_module.common_llm_service,
        "get_chat_model",
        lambda db: None
    )
    with pytest.raises(RuntimeError, match="Pipeline 最终综合失败：当前没有可用的 LLM"):
        service._synthesize_pipeline_answer(
            object(),
            question="test",
            table_answers=table_answers,
            use_llm=True
        )


def test_synthesize_pipeline_answer_llm_fails(monkeypatch):
    import sys
    from services.document_qa.table_qa_service import TableQAService
    table_qa_service_module = sys.modules["services.document_qa.table_qa_service"]
    service = TableQAService()
    table_answers = [{
        "sub_question": "sub Q",
        "table": {"table_title": "T1"},
        "qa": {"answer": "T1 answer", "evidence_paths": ["path1"]}
    }]
    monkeypatch.setattr(
        table_qa_service_module.common_llm_service,
        "get_chat_model",
        lambda db: object()
    )
    
    class FakeFailingChain:
        def __or__(self, other):
            return self
        def invoke(self, *args, **kwargs):
            raise Exception("synthesis error")

    monkeypatch.setattr(
        table_qa_service_module,
        "_PIPELINE_SYNTHESIS_PROMPT",
        FakeFailingChain()
    )

    with pytest.raises(RuntimeError, match="Pipeline 最终综合 LLM 调用失败"):
        service._synthesize_pipeline_answer(
            object(),
            question="test",
            table_answers=table_answers,
            use_llm=True
        )


def test_synthesize_pipeline_answer_llm_empty(monkeypatch):
    import sys
    from services.document_qa.table_qa_service import TableQAService
    table_qa_service_module = sys.modules["services.document_qa.table_qa_service"]
    service = TableQAService()
    table_answers = [{
        "sub_question": "sub Q",
        "table": {"table_title": "T1"},
        "qa": {"answer": "T1 answer", "evidence_paths": ["path1"]}
    }]
    monkeypatch.setattr(
        table_qa_service_module.common_llm_service,
        "get_chat_model",
        lambda db: object()
    )
    
    class FakeEmptyChain:
        def __or__(self, other):
            return self
        def invoke(self, *args, **kwargs):
            return ""

    monkeypatch.setattr(
        table_qa_service_module,
        "_PIPELINE_SYNTHESIS_PROMPT",
        FakeEmptyChain()
    )

    with pytest.raises(RuntimeError, match="Pipeline 最终综合失败：LLM 返回内容为空"):
        service._synthesize_pipeline_answer(
            object(),
            question="test",
            table_answers=table_answers,
            use_llm=True
        )


def test_rrf_merge_rewards_tables_found_by_both_retrievers():
    semantic_hits = [
        {"table_id": "semantic-only", "score": 0.95, "source": "cosine"},
        {"table_id": "hybrid", "score": 0.85, "source": "cosine"},
    ]
    text_hits = [
        {"table_id": "hybrid", "score": 18.0, "source": "text"},
        {"table_id": "text-only", "score": 12.0, "source": "text"},
    ]

    rows = _merge_hits(semantic_hits, text_hits, limit=3)

    assert rows[0]["table_id"] == "hybrid"
    assert rows[0]["source"] == "rrf:cosine+text"
    assert all(0.0 <= row["score"] <= 1.0 for row in rows)


def test_symbolic_max_requires_an_exact_metric_and_ignores_other_numeric_fields():
    service = TableQAService()
    paths = [
        "项目 - 本科生 | 招生数: 100; 毕业数: 999",
        "项目 - 硕士生 | 招生数: 120; 毕业数: 80",
    ]

    answer = service._answer_symbolic(
        question="哪个项目招生数最多",
        artifact={"table_title": "招生表"},
        paths=paths,
        fields=["项目", "招生数", "毕业数"],
        metrics=["招生数", "毕业数"],
    )

    assert "招生数的最大值为 120" in answer
    assert "999" not in answer
    assert service._answer_symbolic(
        question="哪个项目最多",
        artifact={"table_title": "招生表"},
        paths=paths,
        fields=["项目", "招生数", "毕业数"],
        metrics=["招生数", "毕业数"],
    ) == ""


def test_symbolic_sum_respects_hierarchy_scope_and_rejects_percentages():
    service = TableQAService()
    paths = [
        "学校 - 湖南师范大学 | 项目 - 本科生 | 招生数: 100",
        "学校 - 其他学校 | 项目 - 本科生 | 招生数: 900",
    ]

    answer = service._answer_symbolic(
        question="湖南师范大学招生数合计",
        artifact={"table_title": "招生表"},
        paths=paths,
        fields=["学校", "项目", "招生数"],
        metrics=["招生数"],
    )
    assert "招生数的合计为 100" in answer
    assert "1000" not in answer

    assert service._answer_symbolic(
        question="所有项目就业率平均值",
        artifact={"table_title": "就业表"},
        paths=["项目 - 本科生 | 就业率: 90%", "项目 - 硕士生 | 就业率: 95%"],
        fields=["项目", "就业率"],
        metrics=["就业率"],
    ) == ""
