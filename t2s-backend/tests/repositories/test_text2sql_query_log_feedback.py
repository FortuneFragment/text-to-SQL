from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.text2sql_query_log import Text2SQLQueryLog
from repositories.text2sql_query_log_repo import Text2SQLQueryLogRepository


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Text2SQLQueryLog.__table__.create(bind=engine)
    Text2SQLQueryLogRepository._relation_guard_column_checked = False
    Text2SQLQueryLogRepository._feedback_score_column_checked = False
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _create_success_log(db, *, user_id: int, question: str) -> Text2SQLQueryLog:
    return Text2SQLQueryLogRepository(db).create(
        user_id=user_id,
        question=question,
        generated_sql="SELECT 1",
        final_sql="SELECT 1",
        status="success",
        error_message=None,
        selected_tables="[]",
        relation_guard_used=False,
        row_count=1,
        duration_ms=10,
        repaired=False,
    )


def test_update_feedback_persists_score_for_owner(session):
    log = _create_success_log(session, user_id=7, question="q1")
    repo = Text2SQLQueryLogRepository(session)

    assert repo.update_feedback(log_id=log.id, user_id=7, score=5) is True

    session.expire_all()
    refreshed = session.get(Text2SQLQueryLog, log.id)
    assert refreshed.feedback_score == 5


def test_update_feedback_rejects_non_owner(session):
    log = _create_success_log(session, user_id=7, question="q1")
    repo = Text2SQLQueryLogRepository(session)

    assert repo.update_feedback(log_id=log.id, user_id=999, score=5) is False

    session.expire_all()
    refreshed = session.get(Text2SQLQueryLog, log.id)
    assert refreshed.feedback_score is None


def test_fewshot_threshold_filter_only_keeps_high_scores(session):
    high = _create_success_log(session, user_id=7, question="high")
    mid = _create_success_log(session, user_id=7, question="mid")
    _unrated = _create_success_log(session, user_id=7, question="unrated")

    repo = Text2SQLQueryLogRepository(session)
    repo.update_feedback(log_id=high.id, user_id=7, score=5)
    repo.update_feedback(log_id=mid.id, user_id=7, score=3)

    rows = (
        session.query(Text2SQLQueryLog)
        .filter(Text2SQLQueryLog.status == "success")
        .filter(Text2SQLQueryLog.final_sql.isnot(None))
        .filter(Text2SQLQueryLog.feedback_score >= 5)
        .all()
    )

    assert [row.question for row in rows] == ["high"]
