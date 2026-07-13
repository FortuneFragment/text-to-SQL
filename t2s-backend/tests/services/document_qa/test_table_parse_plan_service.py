import io
import json

import pytest
from openpyxl import Workbook
from langchain_core.messages import AIMessage

from services.document_qa.table_parse_plan_service import (
    ComplexTableParsePlan,
    HierarchyColumn,
    RowPath,
    RowPathSegment,
    ValueColumn,
    build_complex_plan_result,
    build_tree_from_complex_plan,
    grid_to_llm_json,
    normalize_complex_parse_plan,
    parse_complex_table_parse_plan,
    extract_sheet_grid,
    validate_complex_parse_plan,
    TableParsePlanService,
)
from services.document_qa.table_semantic_service import TableSemanticService


def _complex_sheet():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "统计表"
    sheet.merge_cells("A1:E1")
    sheet["A1"] = "招生统计"
    sheet.append(["类别", "项目", "代码", "招生数", "毕业数"])
    sheet.append(["学生", "本科生", "01", 100, 80])
    sheet.append([None, "其中女生", "01F", 60, 50])
    sheet.append(["说明", None, None, None, None])
    return sheet


def _complex_plan(*, row_paths=None, hierarchy_columns=None):
    return ComplexTableParsePlan(
        table_range="A1:E5",
        title_ranges=["A1:E1"],
        header_ranges=["A2:E2"],
        data_row_range="A3:E5",
        hierarchy_columns=hierarchy_columns
        or [
            HierarchyColumn(header="类别", col="A"),
            HierarchyColumn(header="项目", col="B"),
            HierarchyColumn(header="代码", col="C"),
        ],
        value_columns=[
            ValueColumn(header="招生数", col="D", group="人数"),
            ValueColumn(header="毕业数", col="E", group="人数"),
        ],
        row_paths=row_paths or [],
        ignored_rows=[5],
        hierarchy_fill_down=True,
    )


def test_compact_grid_preserves_merged_cells_and_full_profiles():
    sheet = _complex_sheet()

    grid = extract_sheet_grid(sheet)
    payload = json.loads(grid_to_llm_json(grid))

    assert grid.table_range == "A1:E5"
    assert grid.rows[0][0].merged_range == "A1:E1"
    assert grid.rows[0][1].is_merged_child is True
    assert payload["max_row"] == 5
    assert len(payload["row_profiles"]) == 5
    assert len(payload["column_profiles"]) == 5
    assert any(row["row"] == 1 for row in payload["sampled_rows"])


def test_complex_plan_json_repairs_trailing_commas_and_validates_models():
    raw = """```json
    {
      "table_range": "A1:E5",
      "title_ranges": ["A1:E1"],
      "header_ranges": ["A2:E2"],
      "data_row_range": "A3:E5",
      "hierarchy_columns": [{"header": "类别", "col": "A"}],
      "value_columns": [{"header": "招生数", "col": "D", "group": "人数"}],
      "row_paths": [],
      "ignored_rows": [5],
      "hierarchy_fill_down": true,
      "notes": [],
    }
    ```"""

    plan = parse_complex_table_parse_plan(raw)

    assert plan.table_range == "A1:E5"
    assert plan.hierarchy_columns[0].col == "A"
    assert plan.value_columns[0].group == "人数"


def test_sparse_row_paths_override_special_rows_without_skipping_regular_rows():
    sheet = _complex_sheet()
    special_path = RowPath(
        row=4,
        path=[
            RowPathSegment(header="类别", ref="A3", role="group"),
            RowPathSegment(header="项目", ref="B3", role="item"),
            RowPathSegment(header="项目", ref="B4", role="qualifier"),
            RowPathSegment(header="代码", ref="C4", role="code"),
        ],
    )
    plan = _complex_plan(row_paths=[special_path])

    tree_refs, tree, coverage = build_tree_from_complex_plan(sheet, plan)

    assert tree_refs["类别 - 学生"]["项目 - 本科生"]["代码 - 01"]["人数"]["招生数"] == "D3"
    special = tree_refs["类别 - 学生"]["项目 - 本科生"]["项目 - 其中女生"]["代码 - 01F"]
    assert special["人数"]["毕业数"] == "E4"
    assert tree["类别 - 学生"]["项目 - 本科生"]["代码 - 01"]["人数"]["招生数"] == 100
    assert coverage.data_rows == 2
    assert coverage.expected_cells == 4
    assert coverage.covered_cells == 4
    assert coverage.skipped_rows == [5]
    assert coverage.complete is True


def test_normalization_adds_omitted_hierarchy_columns_and_repairs_qualifier_parent():
    sheet = _complex_sheet()
    parent = RowPath(
        row=3,
        path=[
            RowPathSegment(header="类别", ref="A3", role="group"),
            RowPathSegment(header="项目", ref="B3", role="item"),
            RowPathSegment(header="代码", ref="C3", role="code"),
        ],
    )
    qualifier = RowPath(
        row=4,
        path=[RowPathSegment(header="项目", ref="B4", role="qualifier")],
    )
    plan = _complex_plan(
        row_paths=[parent, qualifier],
        hierarchy_columns=[HierarchyColumn(header="项目", col="B")],
    )

    normalized = normalize_complex_parse_plan(plan, sheet)

    assert [column.col for column in normalized.hierarchy_columns] == ["A", "B", "C"]
    repaired = normalized.row_paths[1].path
    assert [(segment.ref, segment.role) for segment in repaired] == [
        ("A3", "group"),
        ("B3", "item"),
        ("B4", "qualifier"),
    ]
    assert validate_complex_parse_plan(normalized, sheet) == []


def test_complex_result_keeps_full_plan_metadata_records_and_coverage():
    sheet = _complex_sheet()
    plan = _complex_plan()

    result = build_complex_plan_result(
        sheet,
        file_name="demo.xlsx",
        plan=plan,
        raw_plan_output="{\"source\": \"test\"}",
        validation_warnings=[],
    )

    assert result.title == "招生统计"
    assert result.headers == ["类别", "项目", "代码", "招生数", "毕业数"]
    assert result.row_count == 2
    assert result.records[1]["项目"] == "其中女生"
    assert result.tree_metric_names == ["招生数", "毕业数"]
    assert result.raw_plan_output == "{\"source\": \"test\"}"
    assert result.coverage.complete is True
    assert any("本科生" in path and "招生数" in path for path in result.tree_path_text)


def test_llm_parse_flow_uses_complete_complex_plan(monkeypatch):
    sheet = _complex_sheet()
    response = {
        "table_range": "A1:E5",
        "title_ranges": ["A1:E1"],
        "header_ranges": ["A2:E2"],
        "data_row_range": "A3:E5",
        "hierarchy_columns": [
            {"header": "类别", "col": "A"},
            {"header": "项目", "col": "B"},
            {"header": "代码", "col": "C"},
        ],
        "value_columns": [
            {"header": "招生数", "col": "D", "group": "人数"},
            {"header": "毕业数", "col": "E", "group": "人数"},
        ],
        "row_paths": [],
        "ignored_rows": [5],
        "hierarchy_fill_down": True,
        "notes": [],
    }

    class FakeModel:
        def invoke(self, messages):
            assert messages and "column_profiles" in str(messages[0].content)
            return AIMessage(content=json.dumps(response, ensure_ascii=False))

    monkeypatch.setattr(
        "services.document_qa.table_parse_plan_service.common_llm_service.get_chat_model",
        lambda db=None: FakeModel(),
    )

    result = TableParsePlanService().parse_sheet_with_llm(
        sheet,
        file_name="demo.xlsx",
        db=None,
    )

    assert isinstance(result.parse_plan, ComplexTableParsePlan)
    assert result.row_count == 2
    assert result.coverage.complete is True
    assert "已使用 LLM 解析计划" in result.validation_warnings

    buffer = io.BytesIO()
    sheet.parent.save(buffer)
    parsed = TableSemanticService().parse_table(
        raw=buffer.getvalue(),
        file_type="xlsx",
        file_name="demo.xlsx",
        sheet_name="统计表",
        db=None,
        use_llm_plan=True,
    )
    assert parsed.parse_mode == "llm"
    assert parsed.parse_plan["table_range"] == "A1:E5"
    assert parsed.parse_plan["ignored_rows"] == [5]
    assert parsed.coverage["is_complete"] is True


def test_llm_parse_flow_rejects_missing_model_instead_of_heuristic_fallback(monkeypatch):
    sheet = _complex_sheet()
    monkeypatch.setattr(
        "services.document_qa.table_parse_plan_service.common_llm_service.get_chat_model",
        lambda db=None: None,
    )

    with pytest.raises(RuntimeError, match="禁止回退启发式解析计划"):
        TableParsePlanService().parse_sheet_with_llm(
            sheet,
            file_name="demo.xlsx",
            db=None,
        )


def test_llm_parse_flow_surfaces_model_failure_instead_of_heuristic_fallback(monkeypatch):
    sheet = _complex_sheet()

    class FailingModel:
        def invoke(self, messages):
            raise TimeoutError("model timeout")

    monkeypatch.setattr(
        "services.document_qa.table_parse_plan_service.common_llm_service.get_chat_model",
        lambda db=None: FailingModel(),
    )

    with pytest.raises(RuntimeError, match="LLM 解析计划失败，禁止回退启发式解析"):
        TableParsePlanService().parse_sheet_with_llm(
            sheet,
            file_name="demo.xlsx",
            db=None,
        )
