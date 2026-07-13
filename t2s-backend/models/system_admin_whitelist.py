from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class SystemAdminWhitelist(Base):
    __tablename__ = "system_admin_whitelist"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    uni_code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    remark: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
