from __future__ import annotations

import re

from sqlglot import exp, parse_one

_DANGEROUS_KEYWORDS = re.compile(
    r"\b(DROP|DELETE|TRUNCATE|ALTER|INSERT|UPDATE|CREATE|REPLACE|GRANT|REVOKE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)


class Text2SQLValidatorService:
    """中文备注：封装规则校验。
    类职责：聚合同类能力并提供统一调用入口。
    """
    @staticmethod
    def normalize_identifier(value: str | None) -> str:
        """中文备注：规范化identifier相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return (value or "").strip().strip("`").strip('"').lower()

    @staticmethod
    def normalize_table_identifier(value: str | None) -> str:
        """中文备注：规范化table identifier相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        table_name = Text2SQLValidatorService.normalize_identifier(value)
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if "." in table_name:
            table_name = table_name.split(".")[-1]
        # 3. 返回结果：输出当前函数最终结果。
        return table_name

    @staticmethod
    def split_sql_statements(sql: str) -> list[str]:
        """中文备注：拆分sql statements相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return [part.strip() for part in sql.rstrip(";").split(";") if part.strip()]

    @staticmethod
    def build_alias_map(tree: exp.Expression) -> dict[str, str]:
        """中文备注：构建alias map相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `alias_map: dict[str, str]`。
        alias_map: dict[str, str] = {}
        # 2. 迭代处理：遍历集合并逐项构建结果。
        for table in tree.find_all(exp.Table):
            if table.name:
                real_table = str(table.name)
                alias_map[real_table] = real_table
                if table.alias:
                    alias_map[str(table.alias)] = real_table
        # 3. 返回结果：输出当前函数最终结果。
        return alias_map

    @staticmethod
    def extract_tables_from_ast(tree: exp.Expression) -> list[str]:
        """中文备注：提取tables from ast相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `tables: list[str]`。
        tables: list[str] = []
        # 2. 迭代处理：遍历集合并逐项构建结果。
        for table in tree.find_all(exp.Table):
            if table.name:
                tables.append(str(table.name))
        # 3. 返回结果：输出当前函数最终结果。
        return list(dict.fromkeys(tables))

    @staticmethod
    def extract_column_references(tree: exp.Expression) -> list[dict[str, str | None]]:
        """中文备注：提取column references相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `refs: list[dict[str, str | None]]`。
        refs: list[dict[str, str | None]] = []
        # 2. 迭代处理：遍历集合并逐项构建结果。
        for column in tree.find_all(exp.Column):
            if not column.name or column.name == "*":
                continue
            refs.append(
                {
                    "table_alias": str(column.table) if column.table else None,
                    "column": str(column.name),
                }
            )
        # 3. 返回结果：输出当前函数最终结果。
        return refs

    @staticmethod
    def normalize_table_columns_map(
        table_columns_map: dict[str, set[str]] | None,
    ) -> dict[str, set[str]]:
        """中文备注：规范化table columns map相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        normalized: dict[str, set[str]] = {}
        # 2. 迭代处理：遍历集合并逐项构建结果。
        for table_name, columns in (table_columns_map or {}).items():
            normalized_table = Text2SQLValidatorService.normalize_table_identifier(table_name)
            if not normalized_table:
                continue
            normalized_columns = {
                Text2SQLValidatorService.normalize_identifier(column)
                for column in (columns or set())
                if Text2SQLValidatorService.normalize_identifier(column)
            }
            normalized.setdefault(normalized_table, set()).update(normalized_columns)
        # 3. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        return normalized

    @staticmethod
    def validate_columns_exist(
        tree: exp.Expression,
        table_columns_map: dict[str, set[str]],
    ) -> tuple[bool, str]:
        """中文备注：校验columns exist相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `alias_map`。
        alias_map = Text2SQLValidatorService.build_alias_map(tree)
        normalized_alias_map = {
            Text2SQLValidatorService.normalize_identifier(alias): Text2SQLValidatorService.normalize_table_identifier(table)
            for alias, table in alias_map.items()
            if alias and table
        }
        involved_tables = set(normalized_alias_map.values())

        # 2. 迭代处理：遍历集合并逐项构建结果。
        for ref in Text2SQLValidatorService.extract_column_references(tree):
            column_name = ref["column"]
            normalized_column = Text2SQLValidatorService.normalize_identifier(column_name)
            table_alias = ref["table_alias"]

            if table_alias:
                real_table = normalized_alias_map.get(
                    Text2SQLValidatorService.normalize_identifier(table_alias)
                )
                if not real_table:
                    return False, f"SQL 中存在未知表别名: {table_alias}"
                if normalized_column not in table_columns_map.get(real_table, set()):
                    return False, f"字段不存在: {real_table}.{column_name}"
                continue

            matched_tables = [
                table_name
                for table_name in involved_tables
                if normalized_column in table_columns_map.get(table_name, set())
            ]
            if not matched_tables:
                return False, f"字段不存在: {column_name}"
            if len(matched_tables) > 1:
                return False, f"字段归属不明确: {column_name}"

        # 3. 返回结果：输出当前函数最终结果。
        return True, ""

    @staticmethod
    def validate_sql(
        sql: str,
        allowed_tables: list[str] | None = None,
        table_columns_map: dict[str, set[str]] | None = None,
        max_tables: int | None = None,
    ) -> tuple[bool, str]:
        """中文备注：校验sql相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        normalized = sql.strip()
        # 2. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        if not normalized:
            return False, "SQL 不能为空"

        # 3. 条件分支：根据当前状态选择不同处理路径。
        if _DANGEROUS_KEYWORDS.search(sql):
            return False, "SQL 包含禁止的写操作关键字"

        # 4. 变量构建：计算并更新 `statements`。
        statements = Text2SQLValidatorService.split_sql_statements(sql)
        # 5. 条件分支：根据当前状态选择不同处理路径。
        if len(statements) != 1:
            return False, "不允许执行多条 SQL 语句"

        # 6. 核心处理：执行当前阶段的业务逻辑。
        try:
            tree = parse_one(statements[0], read="mysql")
        except Exception as error:  # noqa: BLE001
            return False, f"SQL 解析失败: {error}"

        # 7. 条件分支：根据当前状态选择不同处理路径。
        if not isinstance(tree, exp.Select):
            return False, "仅允许 SELECT 查询"
        # 8. 条件分支：根据当前状态选择不同处理路径。
        if list(tree.find_all(exp.Union)):
            return False, "暂不允许 UNION 查询"

        # 9. 变量构建：计算并更新 `referenced_tables`。
        referenced_tables = Text2SQLValidatorService.extract_tables_from_ast(tree)
        # 10. 条件分支：根据当前状态选择不同处理路径。
        if not referenced_tables:
            return False, "SQL 必须至少引用一张真实表"
        # 11. 条件分支：根据当前状态选择不同处理路径。
        if max_tables is not None and len(referenced_tables) > max(1, int(max_tables)):
            return False, f"SQL 引用了过多表，最多允许 {int(max_tables)} 张表"

        # 12. 条件分支：根据当前状态选择不同处理路径。
        if allowed_tables:
            allowed_table_set = {
                Text2SQLValidatorService.normalize_table_identifier(item)
                for item in allowed_tables
                if item and str(item).strip()
            }
            illegal_tables = [
                table
                for table in referenced_tables
                if Text2SQLValidatorService.normalize_table_identifier(table) not in allowed_table_set
            ]
            if illegal_tables:
                return False, f"SQL 使用了未授权的表: {', '.join(illegal_tables)}"

        # 13. 条件分支：根据当前状态选择不同处理路径。
        if table_columns_map is not None:
            normalized_map = Text2SQLValidatorService.normalize_table_columns_map(table_columns_map)
            missing_tables = [
                table_name
                for table_name in referenced_tables
                if Text2SQLValidatorService.normalize_table_identifier(table_name) not in normalized_map
            ]
            if missing_tables:
                return False, f"SQL 使用了不存在的表: {', '.join(missing_tables)}"

            columns_valid, error_message = Text2SQLValidatorService.validate_columns_exist(tree, normalized_map)
            if not columns_valid:
                return False, error_message

        # 14. 返回结果：输出当前函数最终结果。
        return True, ""
