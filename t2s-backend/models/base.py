from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """声明所有 ORM 模型共享的基类。"""
    pass