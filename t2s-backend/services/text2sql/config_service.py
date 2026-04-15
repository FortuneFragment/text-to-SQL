import json
from typing import Any

from sqlalchemy.orm import Session

from repositories.text2sql_config_repo import Text2SQLConfigRepository
from repositories.text2sql_scoped_config_repo import Text2SQLScopedConfigRepository
from schemas.text2sql import Text2SQLConfigResponse, Text2SQLConnectionResponse, UpdateText2SQLConfigRequest
from services.text2sql.connection_service import Text2SQLConnectionService
from services.text2sql.schema_service import Text2SQLSchemaService


GLOBAL_CONFIG_USER_ID = 1
_UNCONFIGURED_CONNECTION_KEY = "unconfigured"


class Text2SQLConfigService:
    """中文备注：封装配置管理。
    类职责：聚合同类能力并提供统一调用入口。
    """
    def __init__(
        self,
        schema_service: Text2SQLSchemaService,
        connection_service: Text2SQLConnectionService,
    ):
        """中文备注：处理对象生命周期中的 __init__ 特殊逻辑。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `self.schema_service`。
        self.schema_service = schema_service
        self.connection_service = connection_service

    @staticmethod
    def _safe_loads(raw: str | None, default: list[str]) -> list[str]:
        """中文备注：处理loads相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 条件分支：根据当前状态选择不同处理路径。
        if not raw:
            return default
        # 2. 核心处理：执行当前阶段的业务逻辑。
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return default
        # 3. 条件分支：根据当前状态选择不同处理路径。
        if not isinstance(parsed, list):
            return default
        # 4. 返回结果：输出当前函数最终结果。
        return [str(item) for item in parsed]

    @staticmethod
    def _normalize_selected_tables(selected_tables: list[str]) -> list[str]:
        """中文备注：规范化selected tables相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `cleaned: list[str]`。
        cleaned: list[str] = []
        seen: set[str] = set()
        # 2. 迭代处理：遍历集合并逐项构建结果。
        for item in selected_tables:
            table_name = str(item).strip()
            if not table_name:
                continue
            key = table_name.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(table_name)
        # 3. 返回结果：输出当前函数最终结果。
        return cleaned

    @staticmethod
    def _normalize_key_part(value: Any) -> str:
        """中文备注：规范化key part相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return str(value or "").strip().lower()

    @classmethod
    def _build_connection_key(cls, connection: Text2SQLConnectionResponse) -> str:
        """中文备注：构建connection key相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 条件分支：根据当前状态选择不同处理路径。
        if not connection.configured:
            return _UNCONFIGURED_CONNECTION_KEY

        # 2. 返回结果：输出当前函数最终结果。
        return "|".join(
            [
                cls._normalize_key_part(connection.db_type or "mysql"),
                cls._normalize_key_part(connection.host),
                str(int(connection.port or 3306)),
                cls._normalize_key_part(connection.database),
                cls._normalize_key_part(connection.username),
            ]
        )

    def _get_active_connection_key(self, db: Session) -> str:
        """中文备注：获取active connection key相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `connection`。
        connection = self.connection_service.get_public_connection(db)
        # 2. 返回结果：输出当前函数最终结果。
        return self._build_connection_key(connection)

    def get_connection_key(self, db: Session) -> str:
        """中文备注：获取connection key相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return self._get_active_connection_key(db)

    def _build_response(self, config_record) -> Text2SQLConfigResponse:
        """中文备注：构建response相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 条件分支：根据当前状态选择不同处理路径。
        if not config_record:
            return Text2SQLConfigResponse()

        # 2. 变量构建：计算并更新 `selected_tables`。
        selected_tables = self._safe_loads(config_record.selected_tables, [])
        selected_tables = self._normalize_selected_tables(selected_tables)
        # 3. 返回结果：输出当前函数最终结果。
        return Text2SQLConfigResponse(
            selected_tables=selected_tables,
            prompt_hint=config_record.prompt_hint or "",
        )

    def _get_scoped_or_legacy_config_record(self, db: Session):
        """中文备注：获取scoped or legacy config record相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `connection_key`。
        connection_key = self._get_active_connection_key(db)
        scoped_config = Text2SQLScopedConfigRepository(db).get_by_user_and_connection(
            GLOBAL_CONFIG_USER_ID,
            connection_key,
        )
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if scoped_config:
            return scoped_config
        # 3. 返回结果：输出当前函数最终结果。
        return Text2SQLConfigRepository(db).get_by_user_id(GLOBAL_CONFIG_USER_ID)

    def get_config(self, db: Session) -> Text2SQLConfigResponse:
        """中文备注：获取config相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `config_record`。
        config_record = self._get_scoped_or_legacy_config_record(db)
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if config_record:
            return self._build_response(config_record)

        # 默认无配置时，视为所有表开启。
        # 3. 核心处理：执行当前阶段的业务逻辑。
        try:
            default_tables = self.schema_service.list_table_names(db)
        except Exception:  # noqa: BLE001
            default_tables = []
        # 4. 返回结果：输出当前函数最终结果。
        return Text2SQLConfigResponse(
            selected_tables=default_tables,
            prompt_hint="",
        )

    def update_config(self, db: Session, request: UpdateText2SQLConfigRequest) -> Text2SQLConfigResponse:
        """中文备注：更新config相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 标准化处理：统一标识符和配置格式，避免后续匹配偏差。
        selected_tables = self._normalize_selected_tables(request.selected_tables)
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if selected_tables:
            resolved_tables, missing_tables = self.schema_service.validate_selected_tables(db, selected_tables)
        else:
            # 显式保存空列表表示“全部关闭”。
            resolved_tables, missing_tables = [], []
        # 3. 目标解析与合法性校验：解析输入范围并拦截非法数据。
        if missing_tables:
            raise ValueError(f"\u5f53\u524d\u6570\u636e\u5e93\u4e2d\u4e0d\u5b58\u5728\u8fd9\u4e9b\u8868: {', '.join(missing_tables)}")

        # 4. 变量构建：计算并更新 `prompt_hint`。
        prompt_hint = (request.prompt_hint or "").strip()
        connection_key = self._get_active_connection_key(db)
        Text2SQLScopedConfigRepository(db).upsert(
            user_id=GLOBAL_CONFIG_USER_ID,
            connection_key=connection_key,
            selected_tables=json.dumps(resolved_tables, ensure_ascii=False),
            prompt_hint=prompt_hint,
        )
        # 5. 返回结果：输出当前函数最终结果。
        return self.get_config(db)

    def get_runtime_config(self, db: Session) -> dict:
        """中文备注：获取runtime config相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `config`。
        config = self.get_config(db)
        # 2. 返回结果：输出当前函数最终结果。
        return {
            "selected_tables": config.selected_tables,
            "prompt_hint": config.prompt_hint,
        }
