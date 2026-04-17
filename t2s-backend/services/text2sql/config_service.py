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
    """管理表开关与提示词配置，并按连接隔离配置。"""
    def __init__(
        self,
        schema_service: Text2SQLSchemaService,
        connection_service: Text2SQLConnectionService,
    ):
        """初始化配置服务依赖。"""
        self.schema_service = schema_service
        self.connection_service = connection_service

    @staticmethod
    def _safe_loads(raw: str | None, default: list[str]) -> list[str]:
        """把 JSON 字符串安全解析为列表，失败时返回默认值。"""
        if not raw:
            return default
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return default
        if not isinstance(parsed, list):
            return default
        return [str(item) for item in parsed]

    @staticmethod
    def _normalize_selected_tables(selected_tables: list[str]) -> list[str]:
        """清洗表名列表并去重，保留原始顺序。"""
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in selected_tables:
            table_name = str(item).strip()
            if not table_name:
                continue
            key = table_name.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(table_name)
        return cleaned

    @staticmethod
    def _normalize_key_part(value: Any) -> str:
        """把连接键中的单个片段标准化为小写文本。"""
        return str(value or "").strip().lower()

    @classmethod
    def _build_connection_key(cls, connection: Text2SQLConnectionResponse) -> str:
        """根据连接参数拼出稳定的连接键。"""
        if not connection.configured:
            return _UNCONFIGURED_CONNECTION_KEY
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
        """读取当前生效连接，并返回对应连接键。"""
        connection = self.connection_service.get_public_connection(db)
        return self._build_connection_key(connection)

    def get_connection_key(self, db: Session) -> str:
        """对外提供当前连接键。"""
        return self._get_active_connection_key(db)

    def _build_response(self, config_record) -> Text2SQLConfigResponse:
        """把数据库记录转换成接口响应对象。"""
        if not config_record:
            return Text2SQLConfigResponse()
        selected_tables = self._safe_loads(config_record.selected_tables, [])
        selected_tables = self._normalize_selected_tables(selected_tables)
        return Text2SQLConfigResponse(
            selected_tables=selected_tables,
            prompt_hint=config_record.prompt_hint or "",
        )

    def _get_scoped_or_legacy_config_record(self, db: Session):
        """优先读取按连接配置，不存在时回退到旧版全局配置。"""
        connection_key = self._get_active_connection_key(db)
        scoped_config = Text2SQLScopedConfigRepository(db).get_by_user_and_connection(
            GLOBAL_CONFIG_USER_ID,
            connection_key,
        )
        if scoped_config:
            return scoped_config
        return Text2SQLConfigRepository(db).get_by_user_id(GLOBAL_CONFIG_USER_ID)

    def get_config(self, db: Session) -> Text2SQLConfigResponse:
        """读取当前连接下的配置。"""
        config_record = self._get_scoped_or_legacy_config_record(db)
        if config_record:
            return self._build_response(config_record)

        # 默认无配置时，视为所有表开启。
        try:
            default_tables = self.schema_service.list_table_names(db)
        except Exception:  # noqa: BLE001
            default_tables = []
        return Text2SQLConfigResponse(
            selected_tables=default_tables,
            prompt_hint="",
        )

    def update_config(self, db: Session, request: UpdateText2SQLConfigRequest) -> Text2SQLConfigResponse:
        """保存当前连接下的表开关与提示词。"""
        selected_tables = self._normalize_selected_tables(request.selected_tables)
        if selected_tables:
            resolved_tables, missing_tables = self.schema_service.validate_selected_tables(db, selected_tables)
        else:
            # 显式保存空列表表示“全部关闭”。
            resolved_tables, missing_tables = [], []
        if missing_tables:
            raise ValueError(f"当前数据库中不存在这些表: {', '.join(missing_tables)}")
        prompt_hint = (request.prompt_hint or "").strip()
        connection_key = self._get_active_connection_key(db)
        Text2SQLScopedConfigRepository(db).upsert(
            user_id=GLOBAL_CONFIG_USER_ID,
            connection_key=connection_key,
            selected_tables=json.dumps(resolved_tables, ensure_ascii=False),
            prompt_hint=prompt_hint,
        )
        return self.get_config(db)

    def get_runtime_config(self, db: Session) -> dict:
        """返回问答链路运行时需要的配置快照。"""
        config = self.get_config(db)
        return {
            "selected_tables": config.selected_tables,
            "prompt_hint": config.prompt_hint,
        }
