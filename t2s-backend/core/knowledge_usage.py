from __future__ import annotations

from core.knowledge_policy import KnowledgeUsage, parse_usage


KB_USAGE_TABLE_ROUTE = KnowledgeUsage.TABLE_ROUTE.value
KB_USAGE_FEW_SHOT = KnowledgeUsage.FEW_SHOT.value
KB_USAGE_DATA_DICTIONARY = KnowledgeUsage.DATA_DICTIONARY.value
KB_USAGE_DOCUMENT_QA = KnowledgeUsage.DOCUMENT_QA.value
KB_USAGE_TABLE_SEMANTIC_TREE = KnowledgeUsage.TABLE_SEMANTIC_TREE.value

KB_USAGE_VALUES = {usage.value for usage in KnowledgeUsage}

KB_USAGE_LABELS = {
    KB_USAGE_TABLE_ROUTE: "表路由",
    KB_USAGE_FEW_SHOT: "Few-shot",
    KB_USAGE_DATA_DICTIONARY: "数据字典",
    KB_USAGE_DOCUMENT_QA: "文档问答",
    KB_USAGE_TABLE_SEMANTIC_TREE: "表格语义树",
}


def parse_kb_usage(value: object) -> str:
    """严格解析知识库用途，非法值直接抛出领域异常。"""
    return parse_usage(value).value


def normalize_kb_usage(
    value: object,
    *,
    default: str = KB_USAGE_TABLE_ROUTE,
) -> str:
    """不进行默认用途回退。"""
    del default
    return parse_kb_usage(value)