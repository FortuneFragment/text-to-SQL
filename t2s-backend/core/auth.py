from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from repositories.system_admin_repo import SystemAdminRepository
from repositories.system_user_repo import SystemUserRepository
from services.auth.session_service import session_service


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
):
    token = request.cookies.get(
        settings.SESSION_COOKIE_NAME
    )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录",
        )

    user_id = session_service.get_user_id(token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效",
        )

    user = SystemUserRepository(db).get_by_id(user_id)

    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不可用",
        )

    return user


def is_info_admin(db: Session, uni_code: str) -> bool:
    if (
        settings.ENVIRONMENT == "development"
        and settings.ENABLE_DEV_LOGIN
        and uni_code == "dev-info-admin"
    ):
        return True

    # 第一批管理员可以由环境变量初始化
    if uni_code in settings.BOOTSTRAP_ADMIN_UNICODES:
        return True

    return SystemAdminRepository(db).is_enabled(uni_code)


def require_info_admin(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not is_info_admin(db, current_user.uni_code):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅信息处管理员可以访问",
        )

    return current_user
