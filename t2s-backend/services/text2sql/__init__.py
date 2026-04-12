from services.text2sql.config_service import Text2SQLConfigService
from services.text2sql.connection_service import Text2SQLConnectionService
from services.text2sql.facade_service import Text2SQLFacadeService
from services.text2sql.log_service import Text2SQLLogService
from services.text2sql.schema_service import Text2SQLSchemaService

connection_service = Text2SQLConnectionService()
schema_service = Text2SQLSchemaService(connection_service)
config_service = Text2SQLConfigService(schema_service, connection_service)
log_service = Text2SQLLogService()
facade_service = Text2SQLFacadeService(
    connection_service=connection_service,
    schema_service=schema_service,
    config_service=config_service,
    log_service=log_service,
)

__all__ = [
    "connection_service",
    "schema_service",
    "config_service",
    "log_service",
    "facade_service",
    "Text2SQLConnectionService",
    "Text2SQLSchemaService",
    "Text2SQLConfigService",
    "Text2SQLLogService",
    "Text2SQLFacadeService",
]

