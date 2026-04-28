from __future__ import annotations

import pytest

from services.text2sql.generator_service import Text2SQLGeneratorService


class DummySchemaService:
    def build_live_schema_json(self, db, selected_tables, queryable_columns_map=None):
        return "{}"


def test_generate_sql_raises_when_llm_unavailable():
    service = Text2SQLGeneratorService(
        model_provider=lambda: None,
        schema_service=DummySchemaService(),
    )

    with pytest.raises(ValueError, match="大模型不可用"):
        service.generate_sql(
            db=object(),
            question="查询最近的订单",
            runtime_config={"selected_tables": ["t_order"]},
        )
