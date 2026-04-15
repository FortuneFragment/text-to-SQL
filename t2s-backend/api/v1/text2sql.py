from fastapi import APIRouter

from api.v1.text2sql_connection import router as connection_router
from api.v1.text2sql_qa import router as qa_router
from api.v1.text2sql_table import router as table_router

router = APIRouter(prefix="/text2sql", tags=["text2sql"])
router.include_router(connection_router)
router.include_router(table_router)
router.include_router(qa_router)
