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
    def __init__(
        self,
        schema_service: Text2SQLSchemaService,
        connection_service: Text2SQLConnectionService,
    ):
        self.schema_service = schema_service
        self.connection_service = connection_service

    @staticmethod
    def _safe_loads(raw: str | None, default: list[str]) -> list[str]:
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
        return str(value or "").strip().lower()

    @classmethod
    def _build_connection_key(cls, connection: Text2SQLConnectionResponse) -> str:
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
        connection = self.connection_service.get_public_connection(db)
        return self._build_connection_key(connection)

    def _build_response(self, config_record) -> Text2SQLConfigResponse:
        if not config_record:
            return Text2SQLConfigResponse()

        selected_tables = self._safe_loads(config_record.selected_tables, [])
        selected_tables = self._normalize_selected_tables(selected_tables)
        return Text2SQLConfigResponse(
            selected_tables=selected_tables,
            prompt_hint=config_record.prompt_hint or "",
        )

    def get_config(self, db: Session) -> Text2SQLConfigResponse:
        connection_key = self._get_active_connection_key(db)
        scoped_config = Text2SQLScopedConfigRepository(db).get_by_user_and_connection(
            GLOBAL_CONFIG_USER_ID,
            connection_key,
        )
        if scoped_config:
            return self._build_response(scoped_config)

        legacy_config = Text2SQLConfigRepository(db).get_by_user_id(GLOBAL_CONFIG_USER_ID)
        return self._build_response(legacy_config)

    def update_config(self, db: Session, request: UpdateText2SQLConfigRequest) -> Text2SQLConfigResponse:
        selected_tables = self._normalize_selected_tables(request.selected_tables)
        resolved_tables, missing_tables = self.schema_service.validate_selected_tables(db, selected_tables)
        if missing_tables:
            raise ValueError(f"\u5f53\u524d\u6570\u636e\u5e93\u4e2d\u4e0d\u5b58\u5728\u8fd9\u4e9b\u8868: {', '.join(missing_tables)}")

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
        config = self.get_config(db)
        return {
            "selected_tables": config.selected_tables,
            "prompt_hint": config.prompt_hint,
        }
