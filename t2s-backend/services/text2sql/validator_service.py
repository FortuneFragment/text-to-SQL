from __future__ import annotations

import re

from sqlglot import exp, parse_one

from services.text2sql.sql_dialect import INTERNAL_SQLGLOT_DIALECT

_DANGEROUS_KEYWORDS = re.compile(
    r"\b(DROP|DELETE|TRUNCATE|ALTER|INSERT|UPDATE|CREATE|REPLACE|GRANT|REVOKE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)


class Text2SQLValidatorService:
    """负责 SQL 安全与语义校验。"""

    @staticmethod
    def normalize_identifier(value: str | None) -> str:
        """标准化标识符，便于大小写无关比较。"""
        return (value or "").strip().strip("`").strip('"').replace("[", "").replace("]", "").lower()

    @staticmethod
    def normalize_table_identifier(value: str | None) -> str:
        """标准化表名，自动去掉 schema 前缀。"""
        table_name = Text2SQLValidatorService.normalize_identifier(value)
        if "." in table_name:
            table_name = table_name.split(".")[-1]
        return table_name

    @staticmethod
    def split_sql_statements(sql: str) -> list[str]:
        """按分号拆分 SQL 语句。"""
        return [part.strip() for part in sql.rstrip(";").split(";") if part.strip()]

    @staticmethod
    def build_alias_map(tree: exp.Expression) -> dict[str, str]:
        """构建 SQL 中别名到真实表名的映射。"""
        alias_map: dict[str, str] = {}
        for table in tree.find_all(exp.Table):
            if table.name:
                real_table = str(table.name)
                alias_map[real_table] = real_table
                if table.alias:
                    alias_map[str(table.alias)] = real_table
        return alias_map

    @staticmethod
    def extract_tables_from_ast(tree: exp.Expression) -> list[str]:
        """从 AST 中提取涉及的表名。"""
        tables: list[str] = []
        for table in tree.find_all(exp.Table):
            if table.name:
                tables.append(str(table.name))
        return list(dict.fromkeys(tables))

    @staticmethod
    def extract_column_references(tree: exp.Expression) -> list[dict[str, str | None]]:
        """从 AST 中提取字段引用及其表别名。"""
        refs: list[dict[str, str | None]] = []
        for column in tree.find_all(exp.Column):
            if not column.name or column.name == "*":
                continue
            refs.append(
                {
                    "table_alias": str(column.table) if column.table else None,
                    "column": str(column.name),
                }
            )
        return refs

    @staticmethod
    def normalize_table_columns_map(
        table_columns_map: dict[str, set[str]] | None,
    ) -> dict[str, set[str]]:
        """标准化表字段白名单映射。"""
        normalized: dict[str, set[str]] = {}
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
        return normalized

    @staticmethod
    def validate_columns_exist(
        tree: exp.Expression,
        table_columns_map: dict[str, set[str]],
    ) -> tuple[bool, str]:
        """校验 SQL 引用字段是否存在且归属明确。"""
        alias_map = Text2SQLValidatorService.build_alias_map(tree)
        normalized_alias_map = {
            Text2SQLValidatorService.normalize_identifier(alias): Text2SQLValidatorService.normalize_table_identifier(table)
            for alias, table in alias_map.items()
            if alias and table
        }
        involved_tables = set(normalized_alias_map.values())
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
        return True, ""

    @staticmethod
    def _split_and_conditions(expression: exp.Expression | None) -> list[exp.Expression]:
        if expression is None:
            return []
        if isinstance(expression, exp.And):
            return (
                Text2SQLValidatorService._split_and_conditions(expression.this)
                + Text2SQLValidatorService._split_and_conditions(expression.expression)
            )
        return [expression]

    @staticmethod
    def _resolve_column_endpoint(
        column: exp.Expression | None,
        alias_map: dict[str, str],
    ) -> tuple[str, str] | None:
        if not isinstance(column, exp.Column):
            return None
        column_name = Text2SQLValidatorService.normalize_identifier(str(column.name or ""))
        table_alias = Text2SQLValidatorService.normalize_identifier(str(column.table or ""))
        if not column_name or not table_alias:
            return None
        real_table = alias_map.get(table_alias)
        if not real_table:
            return None
        return real_table, column_name

    @staticmethod
    def _canonical_condition_pair(
        left_endpoint: tuple[str, str],
        right_endpoint: tuple[str, str],
    ) -> tuple[str, str, str, str]:
        left_table, left_column = left_endpoint
        right_table, right_column = right_endpoint
        left_tuple = (left_table, left_column)
        right_tuple = (right_table, right_column)
        if left_tuple <= right_tuple:
            return left_table, left_column, right_table, right_column
        return right_table, right_column, left_table, left_column

    @classmethod
    def _build_allowed_join_signatures(
        cls,
        relation_hints: list[dict] | None,
    ) -> dict[frozenset[str], set[frozenset[tuple[str, str, str, str]]]]:
        allowed: dict[frozenset[str], set[frozenset[tuple[str, str, str, str]]]] = {}
        for relation in relation_hints or []:
            source_table = cls.normalize_table_identifier(str(relation.get("source_table") or ""))
            target_table = cls.normalize_table_identifier(str(relation.get("target_table") or ""))
            source_columns = [
                cls.normalize_identifier(str(item))
                for item in (relation.get("source_columns") or [])
                if cls.normalize_identifier(str(item))
            ]
            target_columns = [
                cls.normalize_identifier(str(item))
                for item in (relation.get("target_columns") or [])
                if cls.normalize_identifier(str(item))
            ]
            if not source_table or not target_table or not source_columns or len(source_columns) != len(target_columns):
                continue

            pairs = {
                cls._canonical_condition_pair(
                    (source_table, source_column),
                    (target_table, target_column),
                )
                for source_column, target_column in zip(source_columns, target_columns)
            }
            if not pairs:
                continue

            tables_key = frozenset({source_table, target_table})
            allowed.setdefault(tables_key, set()).add(frozenset(pairs))
        return allowed

    @classmethod
    def validate_join_constraints(
        cls,
        tree: exp.Expression,
        relation_hints: list[dict] | None,
    ) -> tuple[bool, str]:
        allowed_signatures = cls._build_allowed_join_signatures(relation_hints)
        if not allowed_signatures:
            return False, "当前未配置可用关系白名单，不允许多表 JOIN"

        alias_map = cls.build_alias_map(tree)
        normalized_alias_map = {
            cls.normalize_identifier(alias): cls.normalize_table_identifier(table)
            for alias, table in alias_map.items()
            if cls.normalize_identifier(alias) and cls.normalize_table_identifier(table)
        }

        join_nodes = list(tree.find_all(exp.Join))
        if not join_nodes:
            return False, "多表查询必须使用 JOIN 且提供 ON 条件"

        for join_node in join_nodes:
            on_expr = join_node.args.get("on")
            if on_expr is None:
                return False, "JOIN 必须包含 ON 条件，且只能使用等值连接"

            conditions = cls._split_and_conditions(on_expr)
            if not conditions:
                return False, "JOIN ON 条件不能为空"

            condition_pairs: set[tuple[str, str, str, str]] = set()
            joined_tables: set[str] = set()
            for condition in conditions:
                if not isinstance(condition, exp.EQ):
                    return False, "JOIN ON 仅允许使用等值连接（=）和 AND 组合"
                left_endpoint = cls._resolve_column_endpoint(condition.this, normalized_alias_map)
                right_endpoint = cls._resolve_column_endpoint(condition.expression, normalized_alias_map)
                if left_endpoint is None or right_endpoint is None:
                    return False, "JOIN ON 仅允许列与列比较，且必须显式带表别名"

                canonical_pair = cls._canonical_condition_pair(left_endpoint, right_endpoint)
                condition_pairs.add(canonical_pair)
                joined_tables.add(canonical_pair[0])
                joined_tables.add(canonical_pair[2])

            if len(joined_tables) != 2:
                return False, "JOIN ON 必须只连接两张表"

            signature = frozenset(condition_pairs)
            tables_key = frozenset(joined_tables)
            if signature not in allowed_signatures.get(tables_key, set()):
                return False, "JOIN 条件未命中关系白名单"
        return True, ""

    @staticmethod
    def validate_sql(
        sql: str,
        allowed_tables: list[str] | None = None,
        table_columns_map: dict[str, set[str]] | None = None,
        max_tables: int | None = None,
        relation_hints: list[dict] | None = None,
    ) -> tuple[bool, str]:
        """校验 SQL 结构安全性、表权限和字段合法性。"""
        normalized = sql.strip()
        if not normalized:
            return False, "SQL 不能为空"
        if _DANGEROUS_KEYWORDS.search(sql):
            return False, "SQL 包含禁止的写操作关键字"
        statements = Text2SQLValidatorService.split_sql_statements(sql)
        if len(statements) != 1:
            return False, "不允许执行多条 SQL 语句"
        try:
            tree = parse_one(statements[0], read=INTERNAL_SQLGLOT_DIALECT)
        except Exception as error:  # noqa: BLE001
            return False, f"SQL 解析失败: {error}"
        if not isinstance(tree, exp.Select):
            return False, "仅允许 SELECT 查询"
        if list(tree.find_all(exp.Union)):
            return False, "暂不允许 UNION 查询"
        referenced_tables = Text2SQLValidatorService.extract_tables_from_ast(tree)
        if not referenced_tables:
            return False, "SQL 必须至少引用一张真实表"

        max_allowed_tables = max(1, int(max_tables or 1))
        if len(referenced_tables) > max_allowed_tables:
            return False, f"SQL 引用了过多表，最多允许 {max_allowed_tables} 张表"
        if len(referenced_tables) > 1:
            joins = list(tree.find_all(exp.Join))
            if not joins:
                return False, "多表查询必须使用显式 JOIN 语法"
            if not relation_hints:
                return False, "当前系统仅支持单表查询，不允许未授权的多表或 JOIN SQL"
            joins_valid, join_error = Text2SQLValidatorService.validate_join_constraints(tree, relation_hints)
            if not joins_valid:
                return False, join_error

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
        return True, ""
