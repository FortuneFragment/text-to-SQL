from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from repositories.system_user_repo import SystemUserRepository
from services.auth.session_service import session_service


router = APIRouter(
    prefix="/dev/auth",
    tags=["dev-auth"],
)


@router.post("/login")
def dev_login(
    response: Response,
    role: str = "chat_user",
    db: Session = Depends(get_db),
):
    if (
        settings.ENVIRONMENT != "development"
        or not settings.ENABLE_DEV_LOGIN
    ):
        raise HTTPException(status_code=404)

    if role not in {"chat_user", "info_admin"}:
        raise HTTPException(
            status_code=400,
            detail="无效角色",
        )

    uni_code = (
        "dev-info-admin"
        if role == "info_admin"
        else "dev-chat-user"
    )

    user = SystemUserRepository(db).upsert(
        uni_code=uni_code,
        name=(
            "本地管理员"
            if role == "info_admin"
            else "本地普通用户"
        ),
        email="",
        roles=[],
    )

    token = session_service.create(user.id)

    response.set_cookie(
        settings.SESSION_COOKIE_NAME,
        token,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )

    return {"ok": True}
