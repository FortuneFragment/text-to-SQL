from sqlalchemy import BigInteger, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Text2SQLCodeDictValue(Base):
    """码值字典：category_key + code -> 中文释义。"""

    __tablename__ = "text2sql_code_dict_value"
    __table_args__ = (
        UniqueConstraint(
            "connection_key",
            "category_key",
            "code",
            name="uq_t2s_code_dict_value_conn_cat_code",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    connection_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    name: Mapped[str] = mapped_column(Text, nullable=False, default="")
