from datetime import datetime

from sqlalchemy import DateTime, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class SystemUser(Base):
    __tablename__ = "system_user"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    # 学校 OAuth 用户唯一标识
    uni_code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
    )

    email: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="",
    )

    # 只存脱敏后的身份、机构、身份类型
    external_roles: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
