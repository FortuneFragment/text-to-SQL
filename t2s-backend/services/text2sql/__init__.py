from services.text2sql.config_service import Text2SQLConfigService
from services.text2sql.connection_service import Text2SQLConnectionService
from services.text2sql.facade_service import Text2SQLFacadeService
from services.text2sql.log_service import Text2SQLLogService
from services.text2sql.relation_service import Text2SQLRelationService
from services.text2sql.schema_annotation_import_service import Text2SQLSchemaAnnotationImportService
from services.text2sql.code_dict_import_service import Text2SQLCodeDictImportService
from services.text2sql.schema_service import Text2SQLSchemaService

connection_service = Text2SQLConnectionService()
schema_service = Text2SQLSchemaService(connection_service)
config_service = Text2SQLConfigService(schema_service, connection_service)
relation_service = Text2SQLRelationService(schema_service, config_service)
schema_annotation_import_service = Text2SQLSchemaAnnotationImportService(config_service)
code_dict_import_service = Text2SQLCodeDictImportService(config_service)
log_service = Text2SQLLogService()
facade_service = Text2SQLFacadeService(
    connection_service=connection_service,
    schema_service=schema_service,
    config_service=config_service,
    relation_service=relation_service,
    log_service=log_service,
)

__all__ = [
    "connection_service",
    "schema_service",
    "config_service",
    "relation_service",
    "schema_annotation_import_service",
    "code_dict_import_service",
    "log_service",
    "facade_service",
    "Text2SQLConnectionService",
    "Text2SQLSchemaService",
    "Text2SQLConfigService",
    "Text2SQLRelationService",
    "Text2SQLSchemaAnnotationImportService",
    "Text2SQLCodeDictImportService",
    "Text2SQLLogService",
    "Text2SQLFacadeService",
]
