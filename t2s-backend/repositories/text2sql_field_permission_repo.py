from __future__ import annotations

from sqlalchemy.orm import Session

from models.text2sql_field_permission import Text2SQLFieldPermission


class Text2SQLFieldPermissionRepository:
    """中文备注：封装数据存储访问。
    类职责：聚合同类能力并提供统一调用入口。
    """
    def __init__(self, db: Session):
        """中文备注：处理对象生命周期中的 __init__ 特殊逻辑。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `self.db`。
        self.db = db

    def list_by_user_and_connection(
        self,
        user_id: int,
        connection_key: str,
        table_name: str | None = None,
    ) -> list[Text2SQLFieldPermission]:
        """中文备注：列出by user and connection相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 外部调用：执行数据库或接口调用并接收返回值。
        query = self.db.query(Text2SQLFieldPermission).filter(
            Text2SQLFieldPermission.user_id == user_id,
            Text2SQLFieldPermission.connection_key == connection_key,
        )
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if table_name:
            query = query.filter(Text2SQLFieldPermission.table_name == table_name)
        # 3. 返回结果：输出当前函数最终结果。
        return query.all()

    def replace_table_permissions(
        self,
        *,
        user_id: int,
        connection_key: str,
        table_name: str,
        permissions: dict[str, bool],
    ) -> list[Text2SQLFieldPermission]:
        """中文备注：处理table permissions相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 核心处理：执行当前阶段的业务逻辑。
        (
            self.db.query(Text2SQLFieldPermission)
            .filter(
                Text2SQLFieldPermission.user_id == user_id,
                Text2SQLFieldPermission.connection_key == connection_key,
                Text2SQLFieldPermission.table_name == table_name,
            )
            .delete(synchronize_session=False)
        )

        # 2. 变量构建：计算并更新 `records: list[Text2SQLFieldPermission]`。
        records: list[Text2SQLFieldPermission] = []
        # 3. 迭代处理：遍历集合并逐项构建结果。
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

        # 4. 外部调用：执行数据库或接口调用并接收返回值。
        self.db.commit()
        # 5. 迭代处理：遍历集合并逐项构建结果。
        for record in records:
            self.db.refresh(record)
        # 6. 返回结果：输出当前函数最终结果。
        return records
