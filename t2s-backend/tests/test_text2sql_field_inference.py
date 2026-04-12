from services.text2sql.field_inference_service import Text2SQLFieldInferenceService


def test_field_inference_rule_fallback():
    service = Text2SQLFieldInferenceService(lambda: None)
    result = service.infer_fields(
        question="查学生状态",
        sql="SELECT stu_id, status_code FROM t_student LIMIT 10;",
        columns=["stu_id", "status_code"],
        rows=[{"stu_id": 1001, "status_code": 2}],
    )

    assert len(result) == 2
    assert result[0]["column"] == "stu_id"
    assert result[0]["confidence"] >= 0
    assert result[1]["column"] == "status_code"


def test_field_inference_normalizes_confidence():
    assert Text2SQLFieldInferenceService._normalize_confidence(1.5) == 1.0
    assert Text2SQLFieldInferenceService._normalize_confidence(-2) == 0.0
    assert Text2SQLFieldInferenceService._normalize_confidence("0.66") == 0.66
