from __future__ import annotations

KB_USAGE_TABLE_ROUTE = "table_route"
KB_USAGE_FEW_SHOT = "few_shot"
KB_USAGE_DATA_DICTIONARY = "data_dictionary"

KB_USAGE_VALUES = {
    KB_USAGE_TABLE_ROUTE,
    KB_USAGE_FEW_SHOT,
    KB_USAGE_DATA_DICTIONARY,
}

KB_USAGE_LABELS = {
    KB_USAGE_TABLE_ROUTE: "表路由",
    KB_USAGE_FEW_SHOT: "Few-shot",
    KB_USAGE_DATA_DICTIONARY: "数据字典",
}


def normalize_kb_usage(value: object, *, default: str = KB_USAGE_TABLE_ROUTE) -> str:
    usage = str(value or "").strip().lower()
    if usage in KB_USAGE_VALUES:
        return usage
    fallback = str(default or "").strip().lower()
    return fallback if fallback in KB_USAGE_VALUES else KB_USAGE_TABLE_ROUTE
