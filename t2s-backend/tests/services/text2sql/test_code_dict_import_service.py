from __future__ import annotations

import io
import sys
import types

from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

try:
    import langchain_openai  # noqa: F401
except ModuleNotFoundError:
    langchain_openai_stub = types.ModuleType("langchain_openai")

    class _StubChatOpenAI:
        def __init__(self, *args, **kwargs):
            pass

    langchain_openai_stub.ChatOpenAI = _StubChatOpenAI
    sys.modules["langchain_openai"] = langchain_openai_stub

from models.text2sql_code_dict_binding import Text2SQLCodeDictBinding
from models.text2sql_code_dict_value import Text2SQLCodeDictValue
from services.text2sql import code_dict_import_service
from services.text2sql.code_dict_import_service import Text2SQLCodeDictImportService as Service


class DummyConfigService:
    def get_connection_key(self, db, user_id=None):  # noqa: ARG002
        return "sqlserver|localhost|1433|biz|dbo|sa"


def _sheet(headers, rows):
    return (headers, [list(row) for row in rows])


def _xlsx(headers, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _build_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Text2SQLCodeDictValue.__table__.create(engine)
    Text2SQLCodeDictBinding.__table__.create(engine)
    return sessionmaker(bind=engine)()


def test_build_value_items_uses_minimal_columns_and_dedupes():
    items, report = Service.build_value_items(
        _sheet(
            ["category_key", "code", "name"],
            [
                ["NATION", "1", "汉族"],
                ["NATION", "1", "汉族-覆盖"],
                ["NATION", "", "缺编码"],
            ],
        )
    )

    assert items == [{"category_key": "NATION", "code": "1", "name": "汉族-覆盖"}]
    assert report == {"value_count": 1, "category_count": 1, "skipped_rows": 1}


def test_build_value_items_supports_chinese_aliases():
    items, _ = Service.build_value_items(
        _sheet(
            ["字典编码", "编码", "名称"],
            [["PROJECT_TYPE", "Z0717", "青年科学基金项目（B类）"]],
        )
    )

    assert items == [
        {
            "category_key": "PROJECT_TYPE",
            "code": "Z0717",
            "name": "青年科学基金项目（B类）",
        }
    ]


def test_build_binding_items_uses_minimal_columns_and_uppercases_identifiers():
    items, report = Service.build_binding_items(
        _sheet(
            ["table_name", "column_name", "category_key"],
            [
                ["biz_person", "nation_id", "NATION"],
                ["", "title_id", "TITLE"],
            ],
        )
    )

    assert items == [{"table_name": "BIZ_PERSON", "column_name": "NATION_ID", "category_key": "NATION"}]
    assert report == {"binding_count": 1, "skipped_rows": 1}


def test_build_binding_items_supports_chinese_aliases():
    items, _ = Service.build_binding_items(
        _sheet(
            ["源表", "源列", "字典编码"],
            [["BIZ_PROJECT", "PROJECT_TYPE_CODE", "PROJECT_TYPE"]],
        )
    )

    assert items == [
        {
            "table_name": "BIZ_PROJECT",
            "column_name": "PROJECT_TYPE_CODE",
            "category_key": "PROJECT_TYPE",
        }
    ]


def test_import_files_persists_minimal_value_and_binding():
    db = _build_session()
    service = Service(DummyConfigService())
    files = [
        {
            "filename": "码值字典.xlsx",
            "content": _xlsx(
                ["category_key", "code", "name"],
                [["NATION", "1", "汉族"]],
            ),
        },
        {
            "filename": "字段码值绑定.xlsx",
            "content": _xlsx(
                ["table_name", "column_name", "category_key"],
                [["BIZ_PERSON", "NATION_ID", "NATION"]],
            ),
        },
        {
            "filename": "码字.xlsx",
            "content": _xlsx(["dm", "mc"], [["Z0717", "青年科学基金项目（B类）"]]),
        },
    ]

    summary = service.import_files(db, files=files)

    assert summary["value"] == {"value_count": 1, "category_count": 1, "skipped_rows": 0, "written": 1}
    assert summary["binding"] == {"binding_count": 1, "skipped_rows": 0, "written": 1}
    assert summary["ignored_files"] == ["码字.xlsx"]
    value = db.query(Text2SQLCodeDictValue).one()
    assert value.category_key == "NATION" and value.code == "1" and value.name == "汉族"
    binding = db.query(Text2SQLCodeDictBinding).one()
    assert binding.table_name == "BIZ_PERSON" and binding.column_name == "NATION_ID"
    assert binding.category_key == "NATION"


def test_import_binding_only_does_not_delete_existing_values():
    db = _build_session()
    service = Service(DummyConfigService())

    service.import_files(
        db,
        files=[
            {
                "filename": "码值字典.xlsx",
                "content": _xlsx(["category_key", "code", "name"], [["NATION", "1", "汉族"]]),
            }
        ],
    )
    service.import_files(
        db,
        files=[
            {
                "filename": "字段码值绑定.xlsx",
                "content": _xlsx(["table_name", "column_name", "category_key"], [["BIZ_PERSON", "NATION_ID", "NATION"]]),
            }
        ],
    )

    assert db.query(Text2SQLCodeDictValue).count() == 1
    assert db.query(Text2SQLCodeDictBinding).count() == 1


def test_split_import_methods_write_only_target_layer():
    db = _build_session()
    service = Service(DummyConfigService())

    value_summary = service.import_value_files(
        db,
        files=[
            {
                "filename": "码值字典.xlsx",
                "content": _xlsx(["category_key", "code", "name"], [["NATION", "1", "汉族"]]),
            }
        ],
    )
    binding_summary = service.import_binding_files(
        db,
        files=[
            {
                "filename": "字段码值绑定.xlsx",
                "content": _xlsx(["table_name", "column_name", "category_key"], [["BIZ_PERSON", "NATION_ID", "NATION"]]),
            }
        ],
    )

    assert value_summary["value"]["written"] == 1
    assert value_summary["binding"]["written"] == 0
    assert binding_summary["value"]["written"] == 0
    assert binding_summary["binding"]["written"] == 1
    assert db.query(Text2SQLCodeDictValue).count() == 1
    assert db.query(Text2SQLCodeDictBinding).count() == 1


def test_package_exports_code_dict_import_service_instance():
    assert isinstance(code_dict_import_service, Service)
    assert callable(code_dict_import_service.import_files)
    assert callable(code_dict_import_service.import_value_files)
    assert callable(code_dict_import_service.import_binding_files)
