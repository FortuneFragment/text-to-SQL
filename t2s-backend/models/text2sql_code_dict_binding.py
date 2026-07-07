from sqlalchemy import BigInteger, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Text2SQLCodeDictBinding(Base):
    """码值字段绑定：业务表字段 -> 字典 category_key。"""

    __tablename__ = "text2sql_code_dict_binding"
    __table_args__ = (
        UniqueConstraint(
            "connection_key",
            "table_name",
            "column_name",
            name="uq_t2s_code_dict_binding_conn_table_col",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    connection_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    table_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    column_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    category_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
