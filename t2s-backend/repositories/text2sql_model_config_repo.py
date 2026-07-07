from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy import desc
from sqlalchemy.orm import Session

from models.text2sql_model_config import Text2SQLModelConfig


class Text2SQLModelConfigRepository:
    _extra_params_column_checked: bool = False
    _extra_params_column_available: bool = True

    def __init__(self, db: Session):
        self.db = db
        self.ensure_extra_params_column()

    def ensure_extra_params_column(self) -> bool:
        cls = self.__class__
        if cls._extra_params_column_checked:
            return cls._extra_params_column_available

        cls._extra_params_column_checked = True
        cls._extra_params_column_available = True
        try:
            bind = self.db.get_bind()
            inspector = inspect(bind)
            if not inspector.has_table(Text2SQLModelConfig.__tablename__):
                return False
            columns = {
                str(column.get("name") or "").lower()
                for column in inspector.get_columns(Text2SQLModelConfig.__tablename__)
            }
            if "extra_params" in columns:
                return True

            self.db.execute(text("ALTER TABLE text2sql_model_config ADD COLUMN extra_params TEXT"))
            self.db.commit()
            return True
        except Exception:  # noqa: BLE001
            self.db.rollback()
            cls._extra_params_column_available = False
            return False

    def get_by_id(self, config_id: int) -> Text2SQLModelConfig | None:
        return (
            self.db.query(Text2SQLModelConfig)
            .filter(
                Text2SQLModelConfig.id == int(config_id),
                Text2SQLModelConfig.is_deleted == False,  # noqa: E712
            )
            .first()
        )

    def list_all(self, kind: str | None = None) -> list[Text2SQLModelConfig]:
        query = self.db.query(Text2SQLModelConfig).filter(Text2SQLModelConfig.is_deleted == False)  # noqa: E712
        if kind:
            query = query.filter(Text2SQLModelConfig.kind == str(kind))
        return query.order_by(Text2SQLModelConfig.kind.asc(), desc(Text2SQLModelConfig.is_active), Text2SQLModelConfig.id.asc()).all()

    def get_active(self, kind: str) -> Text2SQLModelConfig | None:
        return (
            self.db.query(Text2SQLModelConfig)
            .filter(
                Text2SQLModelConfig.kind == str(kind),
                Text2SQLModelConfig.is_active == True,  # noqa: E712
                Text2SQLModelConfig.is_deleted == False,  # noqa: E712
            )
            .order_by(desc(Text2SQLModelConfig.updated_at), desc(Text2SQLModelConfig.id))
            .first()
        )

    def create(self, entity: Text2SQLModelConfig) -> Text2SQLModelConfig:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, entity: Text2SQLModelConfig) -> Text2SQLModelConfig:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def clear_active(self, kind: str) -> None:
        (
            self.db.query(Text2SQLModelConfig)
            .filter(
                Text2SQLModelConfig.kind == str(kind),
                Text2SQLModelConfig.is_deleted == False,  # noqa: E712
            )
            .update({Text2SQLModelConfig.is_active: False}, synchronize_session=False)
        )
        self.db.commit()

    def activate(self, entity: Text2SQLModelConfig) -> Text2SQLModelConfig:
        self.clear_active(entity.kind)
        entity.is_active = True
        return self.update(entity)

    def soft_delete(self, entity: Text2SQLModelConfig) -> None:
        entity.is_active = False
        entity.is_deleted = True
        self.db.add(entity)
        self.db.commit()
