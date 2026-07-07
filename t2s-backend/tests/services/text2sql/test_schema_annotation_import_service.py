from __future__ import annotations

import io
import sys
import types

from openpyxl import Workbook
import pytest
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

from models.text2sql_schema_annotation import Text2SQLSchemaAnnotation
from services.text2sql import schema_annotation_import_service
from services.text2sql.schema_annotation_import_service import Text2SQLSchemaAnnotationImportService


class DummyConfigService:
    def get_connection_key(self, db, user_id=None):  # noqa: ARG002
        return "sqlserver|localhost|1433|biz|dbo|sa"


def _xlsx(headers: list[str], rows: list[list[str]]) -> bytes:
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
    Text2SQLSchemaAnnotation.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_import_xlsx_schema_annotations():
    db = _build_session()
    service = Text2SQLSchemaAnnotationImportService(DummyConfigService())

    summary = service.import_file(
        db,
        filename="annotations.xlsx",
        content=_xlsx(
            ["table_name", "column_name", "column_comment", "table_comment", "aliases"],
            [
                ["T_STUDENT", "GENDER_ID", "性别", "学生信息", "性别编码,男女"],
                ["T_STUDENT", "NAME", "姓名", "学生信息", ""],
            ],
        ),
    )

    rows = db.query(Text2SQLSchemaAnnotation).order_by(Text2SQLSchemaAnnotation.column_name).all()

    assert summary["parsed"] == 2
    assert summary["upserted"] == 2
    assert rows[0].column_name == "GENDER_ID"
    assert rows[0].column_comment == "性别"
    assert rows[0].table_comment == "学生信息"


def test_package_exports_schema_annotation_import_service_instance():
    assert isinstance(schema_annotation_import_service, Text2SQLSchemaAnnotationImportService)
    assert callable(schema_annotation_import_service.import_file)


def test_import_utf8_csv_schema_annotations():
    db = _build_session()
    service = Text2SQLSchemaAnnotationImportService(DummyConfigService())

    summary = service.import_file(
        db,
        filename="annotations.csv",
        content="table_name,column_name,table_comment,column_comment\nBIZ_PERSON,NAME,科研人员,姓名\n".encode(
            "utf-8"
        ),
    )

    row = db.query(Text2SQLSchemaAnnotation).one()
    assert summary["parsed"] == 1
    assert summary["upserted"] == 1
    assert row.table_name == "BIZ_PERSON"
    assert row.column_name == "NAME"
    assert row.table_comment == "科研人员"
    assert row.column_comment == "姓名"


def test_import_csv_content_with_xlsx_filename():
    db = _build_session()
    service = Text2SQLSchemaAnnotationImportService(DummyConfigService())

    summary = service.import_file(
        db,
        filename="annotations.xlsx",
        content="table_name,column_name,table_comment,column_comment\nBIZ_PERSON,ID,科研人员,主键\n".encode(
            "utf-8"
        ),
    )

    assert summary["parsed"] == 1
    assert summary["upserted"] == 1


def test_import_gbk_csv_schema_annotations():
    db = _build_session()
    service = Text2SQLSchemaAnnotationImportService(DummyConfigService())

    summary = service.import_file(
        db,
        filename="annotations.csv",
        content="table_name,column_name,table_comment,column_comment\nBIZ_PERSON,NAME,科研人员,姓名\n".encode(
            "gbk"
        ),
    )

    assert summary["parsed"] == 1
    assert summary["upserted"] == 1


def test_invalid_binary_xlsx_reports_readable_error():
    db = _build_session()
    service = Text2SQLSchemaAnnotationImportService(DummyConfigService())

    with pytest.raises(ValueError, match="不是有效的 .xlsx/.xlsm"):
        service.import_file(
            db,
            filename="annotations.xlsx",
            content=b"not really an excel workbook",
        )
