from fastapi import APIRouter

from api.v1.text2sql_connection import router as connection_router
from api.v1.text2sql_file import router as file_router
from api.v1.text2sql_kb import router as kb_router
from api.v1.text2sql_qa import alias_router as query_alias_router
from api.v1.text2sql_qa import router as qa_router
from api.v1.text2sql_relation import router as relation_router
from api.v1.text2sql_schema_annotation import router as schema_annotation_router
from api.v1.text2sql_code_dict import router as code_dict_router
from api.v1.text2sql_model_config import router as model_config_router
from api.v1.text2sql_table import router as table_router
from api.v1.text2sql_task import router as task_router

router = APIRouter(prefix="/text2sql", tags=["text2sql"])
router.include_router(connection_router)
router.include_router(table_router)
router.include_router(relation_router)
router.include_router(schema_annotation_router)
router.include_router(code_dict_router)
router.include_router(model_config_router)
router.include_router(qa_router)
router.include_router(query_alias_router)
router.include_router(task_router)
router.include_router(kb_router)
router.include_router(file_router)
