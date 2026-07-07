from typing import Any

from sqlalchemy.orm import Session

from repositories.text2sql_scoped_config_repo import Text2SQLScopedConfigRepository
from schemas.text2sql import Text2SQLConfigResponse, Text2SQLConnectionResponse, UpdateText2SQLConfigRequest
from services.text2sql.connection_service import Text2SQLConnectionService
from services.text2sql.schema_service import Text2SQLSchemaService
from services.text2sql.sql_dialect import default_port_for


GLOBAL_CONFIG_USER_ID = 1
_UNCONFIGURED_CONNECTION_KEY = "unconfigured"


class Text2SQLConfigService:
    """Manage prompt hints scoped to the active database connection."""

    def __init__(
        self,
        schema_service: Text2SQLSchemaService,
        connection_service: Text2SQLConnectionService,
    ):
        self.schema_service = schema_service
        self.connection_service = connection_service

    @staticmethod
    def _normalize_key_part(value: Any) -> str:
        return str(value or "").strip().lower()

    @classmethod
    def _build_connection_key(cls, connection: Text2SQLConnectionResponse) -> str:
        if not connection.configured:
            return _UNCONFIGURED_CONNECTION_KEY
        return "|".join(
            [
                cls._normalize_key_part(connection.db_type or "sqlserver"),
                cls._normalize_key_part(connection.host),
                str(int(connection.port or default_port_for(connection.db_type))),
                cls._normalize_key_part(connection.database),
                cls._normalize_key_part(getattr(connection, "db_schema", "")),
                cls._normalize_key_part(connection.username),
            ]
        )

    def _get_active_connection_key(self, db: Session) -> str:
        connection = self.connection_service.get_public_connection(db)
        return self._build_connection_key(connection)

    def get_connection_key(self, db: Session, user_id: int | None = None) -> str:
        return self._get_active_connection_key(db)

    @staticmethod
    def _build_response(config_record) -> Text2SQLConfigResponse:
        if not config_record:
            return Text2SQLConfigResponse()
        return Text2SQLConfigResponse(prompt_hint=config_record.prompt_hint or "")

    @staticmethod
    def _resolve_user_id(user_id: int | None) -> int:
        return max(1, int(user_id or GLOBAL_CONFIG_USER_ID))

    def _get_scoped_config_record(self, db: Session, user_id: int | None = None):
        resolved_user_id = self._resolve_user_id(user_id)
        connection_key = self._get_active_connection_key(db)
        return Text2SQLScopedConfigRepository(db).get_by_user_and_connection(
            resolved_user_id,
            connection_key,
        )

    def get_config(self, db: Session, user_id: int | None = None) -> Text2SQLConfigResponse:
        config_record = self._get_scoped_config_record(db, user_id=user_id)
        if config_record:
            return self._build_response(config_record)
        return Text2SQLConfigResponse(prompt_hint="")

    def update_config(
        self,
        db: Session,
        request: UpdateText2SQLConfigRequest,
        user_id: int | None = None,
    ) -> Text2SQLConfigResponse:
        resolved_user_id = self._resolve_user_id(user_id)
        prompt_hint = (request.prompt_hint or "").strip()
        connection_key = self._get_active_connection_key(db)
        Text2SQLScopedConfigRepository(db).upsert(
            user_id=resolved_user_id,
            connection_key=connection_key,
            prompt_hint=prompt_hint,
        )
        return self.get_config(db, user_id=resolved_user_id)

    def get_runtime_config(self, db: Session, user_id: int | None = None) -> dict:
        config = self.get_config(db, user_id=user_id)
        return {
            "prompt_hint": config.prompt_hint,
        }
