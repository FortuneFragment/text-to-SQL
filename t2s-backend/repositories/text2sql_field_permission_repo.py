from __future__ import annotations

from sqlalchemy.orm import Session

from models.text2sql_field_permission import Text2SQLFieldPermission


class Text2SQLFieldPermissionRepository:
    """负责字段开关配置的持久化。"""

    def __init__(self, db: Session):
        """注入数据库会话。"""
        self.db = db

    def list_by_user_and_connection(
        self,
        user_id: int,
        connection_key: str,
        table_name: str | None = None,
    ) -> list[Text2SQLFieldPermission]:
        """按用户和连接读取字段权限记录，可按表过滤。"""
        query = self.db.query(Text2SQLFieldPermission).filter(
            Text2SQLFieldPermission.user_id == user_id,
            Text2SQLFieldPermission.connection_key == connection_key,
        )
        if table_name:
            query = query.filter(Text2SQLFieldPermission.table_name == table_name)
        return query.all()

    def replace_table_permissions(
        self,
        *,
        user_id: int,
        connection_key: str,
        table_name: str,
        permissions: dict[str, bool],
    ) -> list[Text2SQLFieldPermission]:
        """替换某张表的字段权限配置。"""
        (
            self.db.query(Text2SQLFieldPermission)
            .filter(
                Text2SQLFieldPermission.user_id == user_id,
                Text2SQLFieldPermission.connection_key == connection_key,
                Text2SQLFieldPermission.table_name == table_name,
            )
            .delete(synchronize_session=False)
        )
        records: list[Text2SQLFieldPermission] = []
        for column_name, query_enabled in permissions.items():
            record = Text2SQLFieldPermission(
                user_id=user_id,
                connection_key=connection_key,
                table_name=table_name,
                column_name=column_name,
                query_enabled=bool(query_enabled),
            )
            self.db.add(record)
            records.append(record)
        self.db.commit()
        for record in records:
            self.db.refresh(record)
        return records
