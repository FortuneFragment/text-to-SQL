from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from core.database import get_db
from schemas.model_config import (
    ModelConfigCreateRequest,
    ModelConfigActivationResponse,
    ModelConfigListResponse,
    ModelProviderListResponse,
    ModelConfigResponse,
    ModelConfigUpdateRequest,
)
from services.common.model_config_service import model_config_service

router = APIRouter(prefix="/model-config", tags=["text2sql-model-config"])
compat_router = APIRouter(prefix="/models", tags=["Model Config"])
logger = logging.getLogger(__name__)


def _success(data, message: str) -> dict:
    return {"code": 200, "message": message, "data": data}


@router.get("", response_model=ModelConfigListResponse)
def list_model_configs(kind: str | None = Query(default=None), db: Session = Depends(get_db)):
    try:
        return ModelConfigListResponse(items=model_config_service.list_configs(db, kind=kind))
    except ValueError as exc:
        logger.exception("list model configs validation failed")
        raise HTTPException(status_code=400, detail="模型配置类型无效") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("list model configs failed")
        raise HTTPException(status_code=400, detail="获取模型配置失败，请稍后重试") from exc


@router.get("/providers", response_model=ModelProviderListResponse)
def list_model_providers():
    return ModelProviderListResponse(items=model_config_service.get_providers_info())


@router.get("/{config_id}", response_model=ModelConfigResponse)
def get_model_config(config_id: int, db: Session = Depends(get_db)):
    try:
        return model_config_service.get_config(db, config_id)
    except ValueError as exc:
        logger.exception("get model config validation failed")
        raise HTTPException(status_code=404, detail="模型配置不存在") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("get model config failed")
        raise HTTPException(status_code=400, detail="获取模型配置失败，请稍后重试") from exc


@router.post("", response_model=ModelConfigResponse)
def create_model_config(payload: ModelConfigCreateRequest, db: Session = Depends(get_db)):
    try:
        return model_config_service.create_config(db, payload)
    except ValueError as exc:
        db.rollback()
        logger.exception("create model config validation failed")
        raise HTTPException(status_code=400, detail="模型配置保存失败，请检查配置项") from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("create model config failed")
        raise HTTPException(status_code=400, detail="模型配置保存失败，请稍后重试") from exc


@router.put("/{config_id}", response_model=ModelConfigResponse)
def update_model_config(
    config_id: int,
    payload: ModelConfigUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        return model_config_service.update_config(db, config_id, payload)
    except ValueError as exc:
        db.rollback()
        logger.exception("update model config validation failed")
        raise HTTPException(status_code=400, detail="模型配置保存失败，请检查配置项") from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("update model config failed")
        raise HTTPException(status_code=400, detail="模型配置保存失败，请稍后重试") from exc


@router.post("/{config_id}/activate", response_model=ModelConfigActivationResponse)
def activate_model_config(config_id: int, db: Session = Depends(get_db)):
    try:
        return model_config_service.activate_config(db, config_id)
    except ValueError as exc:
        db.rollback()
        logger.exception("activate model config validation failed")
        raise HTTPException(status_code=400, detail="模型配置启用失败，请检查配置项") from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("activate model config failed")
        raise HTTPException(status_code=400, detail="模型配置启用失败，请稍后重试") from exc


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model_config(config_id: int, db: Session = Depends(get_db)):
    try:
        model_config_service.delete_config(db, config_id)
    except ValueError as exc:
        db.rollback()
        logger.exception("delete model config validation failed")
        raise HTTPException(status_code=400, detail="模型配置删除失败") from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("delete model config failed")
        raise HTTPException(status_code=400, detail="模型配置删除失败，请稍后重试") from exc
    return None


@router.post("/rebuild-all-kbs")
def rebuild_all_knowledge_bases(db: Session = Depends(get_db)):
    try:
        return model_config_service.rebuild_all_knowledge_bases(db)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("rebuild all knowledge bases failed")
        raise HTTPException(status_code=400, detail="知识库重建任务提交失败，请稍后重试") from exc


@compat_router.get("")
async def compat_list_model_configs(
    model_type: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        return _success(
            [item.model_dump(mode="json") for item in model_config_service.list_configs(db, model_type)],
            "Fetched model configs",
        )
    except ValueError as exc:
        logger.exception("compat list model configs validation failed")
        raise HTTPException(status_code=400, detail="模型配置类型无效") from exc


@compat_router.get("/providers")
async def compat_list_model_providers():
    return _success(
        [item.model_dump(mode="json") for item in model_config_service.get_providers_info()],
        "Fetched model providers",
    )


@compat_router.get("/{config_id}")
async def compat_get_model_config(
    config_id: int = Path(...),
    db: Session = Depends(get_db),
):
    try:
        return _success(
            model_config_service.get_config(db, config_id).model_dump(mode="json"),
            "Fetched model config",
        )
    except ValueError as exc:
        logger.exception("compat get model config validation failed")
        raise HTTPException(status_code=404, detail="模型配置不存在") from exc


@compat_router.post("")
async def compat_create_model_config(
    payload: ModelConfigCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        return _success(
            model_config_service.create_config(db, payload).model_dump(mode="json"),
            "Model config created",
        )
    except ValueError as exc:
        db.rollback()
        logger.exception("compat create model config validation failed")
        raise HTTPException(status_code=400, detail="模型配置保存失败，请检查配置项") from exc


@compat_router.put("/{config_id}")
async def compat_update_model_config(
    payload: ModelConfigUpdateRequest,
    config_id: int = Path(...),
    db: Session = Depends(get_db),
):
    try:
        return _success(
            model_config_service.update_config(db, config_id, payload).model_dump(mode="json"),
            "Model config updated",
        )
    except ValueError as exc:
        db.rollback()
        logger.exception("compat update model config validation failed")
        raise HTTPException(status_code=400, detail="模型配置保存失败，请检查配置项") from exc


@compat_router.post("/{config_id}/activate")
async def compat_activate_model_config(
    config_id: int = Path(...),
    db: Session = Depends(get_db),
):
    try:
        result = model_config_service.activate_config(db, config_id)
        return _success(result.model_dump(mode="json"), result.warning or "Model activated")
    except ValueError as exc:
        db.rollback()
        logger.exception("compat activate model config validation failed")
        raise HTTPException(status_code=400, detail="模型配置启用失败，请检查配置项") from exc


@compat_router.delete("/{config_id}")
async def compat_delete_model_config(
    config_id: int = Path(...),
    db: Session = Depends(get_db),
):
    try:
        model_config_service.delete_config(db, config_id)
        return _success(None, "Model config deleted")
    except ValueError as exc:
        db.rollback()
        logger.exception("compat delete model config validation failed")
        raise HTTPException(status_code=400, detail="模型配置删除失败") from exc


@compat_router.post("/rebuild-all-kbs")
async def compat_rebuild_all_knowledge_bases(db: Session = Depends(get_db)):
    try:
        return _success(model_config_service.rebuild_all_knowledge_bases(db), "Rebuild tasks submitted")
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("compat rebuild all knowledge bases failed")
        raise HTTPException(status_code=400, detail="知识库重建任务提交失败，请稍后重试") from exc
