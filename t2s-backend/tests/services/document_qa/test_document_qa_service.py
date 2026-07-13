import pytest
from types import SimpleNamespace

from api.v1.document_qa import compat_router, router
from schemas.document_qa import TableJobResponse
from services.document_qa.document_qa_service import DocumentQAService


class _FakeTableQAService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def answer_global(self, db, **kwargs):
        self.calls.append(kwargs)
        return {
            "answer": "语义树答案",
            "evidence_paths": ["学院 | 专业 | 招生人数：100"],
            "candidates": [],
        }


class _FakeFinalChain:
    def __or__(self, other):
        return self

    def invoke(self, payload):
        assert payload["document_answer"] == "学校位于长沙市。"
        assert payload["table_answer"] == "地址为长沙市岳麓区。"
        return "最终答案：学校位于长沙市岳麓区。"


def test_query_runs_document_and_table_chains_and_returns_only_final_answer(monkeypatch):
    table_service = _FakeTableQAService()
    service = DocumentQAService(table_service)
    document_kb = SimpleNamespace(id=1, usage="document_qa", collection_name="documents")

    monkeypatch.setattr(
        service,
        "_resolve_query_scope",
        lambda db, kb_id: ([document_kb], True, None),
    )
    monkeypatch.setattr(
        service,
        "_retrieve_from_kbs",
        lambda db, **kwargs: [
            {
                "kb_id": 1,
                "file_id": 10,
                "chunk_id": 20,
                "score": 0.9,
                "text": "普通文档依据",
            }
        ],
    )
    monkeypatch.setattr(service, "_answer_with_llm", lambda db, **kwargs: "普通文档答案")
    monkeypatch.setattr(service, "_resolve_final_answer", lambda db, **kwargs: "用户问题的最终答案")

    result = service.query(object(), question="招生人数是多少？", history=[], top_k=6)

    assert result == {"answer": "用户问题的最终答案", "evidences": []}
    assert len(table_service.calls) == 1
    assert table_service.calls[0]["question"] == "招生人数是多少？"
    assert table_service.calls[0]["kb_id"] is None


def test_final_answer_uses_only_reliable_single_chain_without_extra_prefix():
    service = DocumentQAService(_FakeTableQAService())

    answer = service._resolve_final_answer(
        object(),
        question="学校在哪里？",
        history=[],
        document_answer="最终答案：学校位于长沙市。",
        document_evidence=["学校地址：长沙市"],
        table_answer="当前未检索到相关表格，无法回答问题。",
        table_evidence=[],
    )

    assert answer == "学校位于长沙市。"


def test_final_answer_reports_insufficient_when_both_chains_have_no_evidence():
    service = DocumentQAService(_FakeTableQAService())

    answer = service._resolve_final_answer(
        object(),
        question="未知问题",
        history=[],
        document_answer="",
        document_evidence=[],
        table_answer="当前证据不足，未找到可以回答该问题的表格路径。",
        table_evidence=[],
    )

    assert answer == "当前知识库中未找到足够依据回答该问题。"


def test_final_answer_fuses_two_reliable_answers_and_strips_meta_prefix(monkeypatch):
    import sys
    doc_qa_service_module = sys.modules["services.document_qa.document_qa_service"]
    service = DocumentQAService(_FakeTableQAService())
    monkeypatch.setattr(
        doc_qa_service_module,
        "_FINAL_ANSWER_PROMPT",
        _FakeFinalChain(),
    )
    monkeypatch.setattr(
        doc_qa_service_module.common_llm_service,
        "get_chat_model",
        lambda db: object(),
    )

    answer = service._resolve_final_answer(
        object(),
        question="学校在哪里？",
        history=[],
        document_answer="学校位于长沙市。",
        document_evidence=["学校位于长沙市"],
        table_answer="地址为长沙市岳麓区。",
        table_evidence=["学校 | 地址：长沙市岳麓区"],
    )

    assert answer == "学校位于长沙市岳麓区。"


def test_semantic_tree_preview_routes_are_removed():
    post_paths = {
        route.path
        for route in router.routes
        if "POST" in (route.methods or set())
    }
    get_paths = {
        route.path
        for route in router.routes
        if "GET" in (route.methods or set())
    }
    compat_post_paths = {
        route.path
        for route in compat_router.routes
        if "POST" in (route.methods or set())
    }

    assert "/document-qa/query" in post_paths
    assert "/document-qa/query/stream" in post_paths
    assert "/document-qa/table/answer" not in post_paths
    assert "/document-qa/table/search" not in post_paths
    assert "/document-qa/table/tables/{table_id}/tree" not in get_paths
    assert "/document-qa/table/parse-plan/parse" not in post_paths
    assert "/document-qa/table/table2tree/enhanced" not in post_paths
    assert "/table-parse-plan/parse" not in compat_post_paths
    assert "/table2tree/enhanced" not in compat_post_paths


def test_table_job_runtime_keeps_persisted_artifacts(monkeypatch):
    import sys
    from datetime import datetime

    document_qa_api = sys.modules["api.v1.document_qa"]
    now = datetime.now()
    artifact = {
        "id": 1,
        "kb_id": 6,
        "file_id": 5,
        "usage_snapshot": "table_semantic_tree",
        "processor_type": "table_semantic",
        "table_id": "table-1",
        "file_name": "source.xlsx",
        "sheet_name": "Sheet1",
        "table_title": "Sheet1",
        "summary_text": "summary",
        "candidate_fields": ["name"],
        "tree_path_text": [],
        "tree_metric_names": [],
        "tree_object_name": "tree.json",
        "row_count": 1,
        "column_count": 1,
        "created_at": now,
        "updated_at": now,
    }
    runtime_summary = {
        "file_id": 5,
        "kb_id": 6,
        "batch_id": "batch-1",
        "table_id": "table-1",
        "sheet_name": "Sheet1",
        "table_title": "Sheet1",
        "chunk_count": 1,
        "row_count": 1,
        "column_count": 1,
        "normalized_object_name": "normalized.xlsx",
    }

    class _SuccessfulResult:
        state = "SUCCESS"
        info = runtime_summary
        result = {"tables": [runtime_summary]}

        @staticmethod
        def ready():
            return True

        @staticmethod
        def successful():
            return True

    monkeypatch.setattr(
        document_qa_api.celery_app,
        "AsyncResult",
        lambda task_id: _SuccessfulResult(),
    )

    merged = document_qa_api._merge_table_job_runtime(
        {
            "task_id": "task-1",
            "state": "\u5b8c\u6210",
            "tables": [artifact],
        }
    )

    assert merged["tables"] == [artifact]
    assert merged["result"]["tables"] == [runtime_summary]
    assert TableJobResponse(**merged).tables[0].id == 1


def test_table_job_runtime_does_not_promote_partial_results(monkeypatch):
    import sys

    document_qa_api = sys.modules["api.v1.document_qa"]
    runtime_summary = {
        "file_id": 5,
        "kb_id": 6,
        "table_id": "table-1",
        "sheet_name": "Sheet1",
    }

    class _SuccessfulResult:
        state = "SUCCESS"
        info = runtime_summary
        result = {"tables": [runtime_summary]}

        @staticmethod
        def ready():
            return True

        @staticmethod
        def successful():
            return True

    monkeypatch.setattr(
        document_qa_api.celery_app,
        "AsyncResult",
        lambda task_id: _SuccessfulResult(),
    )

    merged = document_qa_api._merge_table_job_runtime(
        {
            "task_id": "task-1",
            "state": "\u5b8c\u6210",
            "tables": [],
        }
    )

    assert merged["tables"] == []
    assert TableJobResponse(**merged).tables == []


def test_query_no_evidence_returns_default_msg(monkeypatch):
    service = DocumentQAService(_FakeTableQAService())
    document_kb = SimpleNamespace(id=1, usage="document_qa", collection_name="documents")
    monkeypatch.setattr(service, "_resolve_query_scope", lambda db, kb_id: ([document_kb], True, None))
    monkeypatch.setattr(service, "_retrieve_from_kbs", lambda db, **kwargs: [])
    monkeypatch.setattr(
        service,
        "_query_table_answer",
        lambda db, **kwargs: {"answer": "", "evidence_paths": [], "candidates": []}
    )

    result = service.query(object(), question="test question", history=[], top_k=6)
    assert result == {"answer": "知识库中检索不到您所提问的信息", "evidences": []}


def test_query_evidence_but_llm_not_configured(monkeypatch):
    service = DocumentQAService(_FakeTableQAService())
    document_kb = SimpleNamespace(id=1, usage="document_qa", collection_name="documents")
    monkeypatch.setattr(service, "_resolve_query_scope", lambda db, kb_id: ([document_kb], True, None))
    monkeypatch.setattr(
        service,
        "_retrieve_from_kbs",
        lambda db, **kwargs: [{"kb_id": 1, "text": "evidence", "score": 0.9}],
    )
    monkeypatch.setattr(
        service,
        "_query_table_answer",
        lambda db, **kwargs: {"answer": "", "evidence_paths": [], "candidates": []}
    )

    import sys
    doc_qa_service_module = sys.modules["services.document_qa.document_qa_service"]
    monkeypatch.setattr(
        doc_qa_service_module.common_llm_service,
        "get_chat_model",
        lambda db: None,
    )

    with pytest.raises(ValueError, match="大模型未配置"):
        service.query(object(), question="test question", history=[], top_k=6)


def test_query_evidence_but_llm_fails(monkeypatch):
    service = DocumentQAService(_FakeTableQAService())
    document_kb = SimpleNamespace(id=1, usage="document_qa", collection_name="documents")
    monkeypatch.setattr(service, "_resolve_query_scope", lambda db, kb_id: ([document_kb], True, None))
    monkeypatch.setattr(
        service,
        "_retrieve_from_kbs",
        lambda db, **kwargs: [{"kb_id": 1, "text": "evidence", "score": 0.9}],
    )
    monkeypatch.setattr(
        service,
        "_query_table_answer",
        lambda db, **kwargs: {"answer": "", "evidence_paths": [], "candidates": []}
    )

    import sys
    doc_qa_service_module = sys.modules["services.document_qa.document_qa_service"]

    class FakeFailingChain:
        def __or__(self, other):
            return self
        def invoke(self, *args, **kwargs):
            raise Exception("Connection timed out")

    monkeypatch.setattr(
        doc_qa_service_module,
        "_ANSWER_PROMPT",
        FakeFailingChain(),
    )
    monkeypatch.setattr(
        doc_qa_service_module.common_llm_service,
        "get_chat_model",
        lambda db: object(),
    )

    with pytest.raises(RuntimeError, match="大模型调用失败"):
        service.query(object(), question="test question", history=[], top_k=6)


def test_query_evidence_but_llm_returns_empty(monkeypatch):
    service = DocumentQAService(_FakeTableQAService())
    document_kb = SimpleNamespace(id=1, usage="document_qa", collection_name="documents")
    monkeypatch.setattr(service, "_resolve_query_scope", lambda db, kb_id: ([document_kb], True, None))
    monkeypatch.setattr(
        service,
        "_retrieve_from_kbs",
        lambda db, **kwargs: [{"kb_id": 1, "text": "evidence", "score": 0.9}],
    )
    monkeypatch.setattr(
        service,
        "_query_table_answer",
        lambda db, **kwargs: {"answer": "", "evidence_paths": [], "candidates": []}
    )

    import sys
    doc_qa_service_module = sys.modules["services.document_qa.document_qa_service"]

    class FakeEmptyChain:
        def __or__(self, other):
            return self
        def invoke(self, *args, **kwargs):
            return ""

    monkeypatch.setattr(
        doc_qa_service_module,
        "_ANSWER_PROMPT",
        FakeEmptyChain(),
    )
    monkeypatch.setattr(
        doc_qa_service_module.common_llm_service,
        "get_chat_model",
        lambda db: object(),
    )

    with pytest.raises(ValueError, match="大模型返回空内容"):
        service.query(object(), question="test question", history=[], top_k=6)
