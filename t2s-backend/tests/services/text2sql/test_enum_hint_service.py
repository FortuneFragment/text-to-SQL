from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine, text

from core.config import settings
from services.text2sql.enum_hint_service import Text2SQLEnumHintService


class DummySchemaService:
    def __init__(self, metadata_map: dict[str, list[dict]]):
        self._metadata_map = metadata_map

    @staticmethod
    def _normalize_identifier(value: str | None) -> str:
        text_value = (value or "").strip().strip("`").strip('"')
        if "." in text_value:
            text_value = text_value.split(".")[-1]
        return text_value.lower()

    def get_live_table_column_metadata(
        self,
        db,
        table_names: list[str] | None = None,
        queryable_columns_map: dict[str, set[str]] | None = None,
    ) -> dict[str, list[dict]]:
        target_tables = list(table_names or self._metadata_map.keys())
        normalized_queryable: dict[str, set[str]] = {}
        for table_name, columns in (queryable_columns_map or {}).items():
            normalized_queryable[self._normalize_identifier(table_name)] = {
                self._normalize_identifier(column_name)
                for column_name in columns
            }

        result: dict[str, list[dict]] = {}
        for table_name in target_tables:
            columns = list(self._metadata_map.get(table_name, []))
            allowed = normalized_queryable.get(self._normalize_identifier(table_name))
            if allowed is not None:
                columns = [
                    item
                    for item in columns
                    if self._normalize_identifier(str(item.get("name") or "")) in allowed
                ]
            result[table_name] = columns
        return result


class BrokenSchemaService:
    def get_live_table_column_metadata(self, *args, **kwargs):
        raise RuntimeError("schema down")


def test_select_probe_columns_filters_type_and_id():
    columns = [
        {"name": "id", "type": "int", "is_primary_key": True},
        {"name": "tenant_id", "type": "varchar(32)", "is_primary_key": False},
        {"name": "status", "type": "varchar(32)", "is_primary_key": False},
        {"name": "gender", "type": "char(2)", "is_primary_key": False},
        {"name": "level", "type": "tinyint", "is_primary_key": False},
        {"name": "nickname", "type": "text", "is_primary_key": False},
    ]

    selected = Text2SQLEnumHintService._select_probe_columns(columns, max_columns=10)
    selected_names = {item["name"] for item in selected}

    assert selected_names == {"status", "gender", "level"}


def test_build_probe_sql_differs_for_text_and_tinyint():
    text_sql = Text2SQLEnumHintService._build_probe_sql(
        table_name="t_student",
        column_name="status",
        column_type="varchar(32)",
        primary_key_column="id",
        sample_rows=100,
        top_values=5,
    )
    tinyint_sql = Text2SQLEnumHintService._build_probe_sql(
        table_name="t_student",
        column_name="level",
        column_type="tinyint",
        primary_key_column="id",
        sample_rows=100,
        top_values=5,
    )

    assert "TRIM(`status`) <> ''" in text_sql
    assert "ORDER BY `id` ASC" in text_sql
    assert "TRIM(`level`)" not in tinyint_sql
    assert "`level` IS NOT NULL" in tinyint_sql


def test_normalize_probe_rows_removes_dirty_and_sorts():
    rows = [
        ("在读", 10),
        ("毕业", 8),
        (" ", 9),
        (None, 3),
        ("毕业", 6),
        ("休学", 1),
    ]

    normalized = Text2SQLEnumHintService._normalize_probe_rows(
        rows,
        is_text_column=True,
        top_values=3,
    )

    assert normalized == [("在读", 10), ("毕业", 8), ("休学", 1)]


def test_trim_hint_map_prefers_column_coverage():
    hint_map = {
        "t_student": {
            "status": [("在读", 10), ("毕业", 8)],
            "gender": [("男", 9), ("女", 7)],
        }
    }
    base_hint = "业务约束"
    full_text = Text2SQLEnumHintService._append_hint_block(base_hint, hint_map)

    trimmed = Text2SQLEnumHintService._trim_hint_map_for_prompt(
        base_prompt_hint=base_hint,
        hint_map=hint_map,
        max_prompt_chars=len(full_text) - 1,
    )

    assert set(trimmed.get("t_student", {}).keys()) == {"status", "gender"}
    assert all(len(values) >= 1 for values in trimmed["t_student"].values())

    merged_hint = Text2SQLEnumHintService._append_hint_block(base_hint, trimmed)
    payload = json.loads(merged_hint.split("enum_hints_json:\n", 1)[1])
    assert "t_student" in payload["enum_hints"]


def test_build_prompt_hint_from_sqlite_sampling(tmp_path, monkeypatch):
    db_file = Path(tmp_path) / "enum_hint.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE t_student (
                    id INTEGER PRIMARY KEY,
                    status TEXT,
                    gender TEXT,
                    grade INTEGER,
                    nickname TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO t_student (id, status, gender, grade, nickname) VALUES
                (1, '在读', '男', 1, 'A'),
                (2, '在读', '女', 1, 'B'),
                (3, '毕业', '男', 2, 'C'),
                (4, '在读', '男', 1, 'D'),
                (5, '', '男', 3, 'E'),
                (6, NULL, '女', 3, 'F')
                """
            )
        )

    metadata_map = {
        "t_student": [
            {"name": "id", "type": "int", "is_primary_key": True},
            {"name": "status", "type": "varchar(32)", "is_primary_key": False},
            {"name": "gender", "type": "char(2)", "is_primary_key": False},
            {"name": "grade", "type": "tinyint", "is_primary_key": False},
            {"name": "nickname", "type": "text", "is_primary_key": False},
        ]
    }
    service = Text2SQLEnumHintService(lambda db: engine, DummySchemaService(metadata_map))

    monkeypatch.setattr(settings, "TEXT2SQL_ENUM_HINT_MAX_TABLES", 1)
    monkeypatch.setattr(settings, "TEXT2SQL_ENUM_HINT_SAMPLE_ROWS", 100)
    monkeypatch.setattr(settings, "TEXT2SQL_ENUM_HINT_TOP_VALUES", 3)
    monkeypatch.setattr(settings, "TEXT2SQL_ENUM_HINT_MAX_COLUMNS_PER_TABLE", 4)
    monkeypatch.setattr(settings, "TEXT2SQL_ENUM_HINT_MAX_WORKERS", 1)
    monkeypatch.setattr(settings, "TEXT2SQL_ENUM_HINT_PROBE_TIMEOUT_MS", 300)
    monkeypatch.setattr(settings, "TEXT2SQL_ENUM_HINT_MAX_PROMPT_CHARS", 2000)

    prompt_hint = service.build_prompt_hint(
        db=object(),
        candidate_tables=["t_student"],
        queryable_columns_map={"t_student": {"status", "gender", "grade"}},
        base_prompt_hint="基础约束",
    )

    assert "enum_hints_json" in prompt_hint
    payload = json.loads(prompt_hint.split("enum_hints_json:\n", 1)[1])
    enum_hints = payload["enum_hints"]["t_student"]

    assert enum_hints["status"][0] == "在读"
    assert "毕业" in enum_hints["status"]
    assert "" not in enum_hints["status"]


def test_build_prompt_hint_fail_open_on_schema_error():
    service = Text2SQLEnumHintService(lambda db: None, BrokenSchemaService())

    prompt_hint = service.build_prompt_hint(
        db=object(),
        candidate_tables=["t_student"],
        queryable_columns_map=None,
        base_prompt_hint="原始提示",
    )

    assert prompt_hint == "原始提示"
