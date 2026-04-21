from __future__ import annotations

from core.config import settings
import services.text2sql.vector_service as vector_module
from services.text2sql.vector_service import Text2SQLVectorService


class DummyEmbeddings:
    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


def _build_service(monkeypatch, raw_hits: list[dict]) -> Text2SQLVectorService:
    service = Text2SQLVectorService(kb_id=2)
    monkeypatch.setattr(settings, "MILVUS_VECTOR_DIM", 3)
    monkeypatch.setattr(service, "_resolve_collection_name", lambda db, requested_kb_id=None: (2, "kb_route"))
    monkeypatch.setattr(service, "_load_file_name_lookup", lambda db, file_ids: {})
    monkeypatch.setattr(vector_module, "get_embeddings", lambda: DummyEmbeddings())
    monkeypatch.setattr(vector_module.milvus_repo, "search_chunks", lambda **kwargs: list(raw_hits))
    return service


def test_search_tables_ignores_overly_shared_tokens(monkeypatch):
    service = _build_service(
        monkeypatch,
        raw_hits=[
            {
                "score": 0.92,
                "file_id": 1,
                "text": "id name status zt rq sj bh mc",
            }
        ],
    )

    scores = service.search_tables(
        db=object(),
        question="请帮我找学分比较高的课",
        candidate_tables=["kc_jb", "ty_yy", "xk_jl", "xs_jb"],
        top_k=10,
        candidate_profiles={
            "kc_jb": "kc_jb id name status zt rq sj bh mc",
            "ty_yy": "ty_yy id name status zt rq sj bh mc",
            "xk_jl": "xk_jl id name status zt rq sj bh mc",
            "xs_jb": "xs_jb id name status zt rq sj bh mc",
        },
        route_kb_id=2,
    )

    assert scores == {}


def test_search_tables_keeps_specific_token_signal(monkeypatch):
    service = _build_service(
        monkeypatch,
        raw_hits=[
            {
                "score": 0.88,
                "file_id": 1,
                "text": "mc zt xf 学分 课程",
            }
        ],
    )

    scores = service.search_tables(
        db=object(),
        question="有哪些课学分比较高",
        candidate_tables=["kc_jb", "ty_yy"],
        top_k=10,
        candidate_profiles={
            "kc_jb": "kc_jb 课程基本 bh mc zt xf xs",
            "ty_yy": "ty_yy 体育场馆预约 bh mc zt yy_rq ks_sj js_sj",
        },
        route_kb_id=2,
    )

    assert float(scores.get("kc_jb", 0.0)) > 0.0
    assert float(scores.get("ty_yy", 0.0)) == 0.0
