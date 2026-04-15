from sqlalchemy.orm import Session

from models.text2sql_scoped_config import Text2SQLScopedConfig


class Text2SQLScopedConfigRepository:
    """中文备注：封装配置管理。
    类职责：聚合同类能力并提供统一调用入口。
    """
    def __init__(self, db: Session):
        """中文备注：处理对象生命周期中的 __init__ 特殊逻辑。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `self.db`。
        self.db = db

    def get_by_user_and_connection(self, user_id: int, connection_key: str) -> Text2SQLScopedConfig | None:
        """中文备注：获取by user and connection相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 返回结果：输出当前函数最终结果。
        return (
            self.db.query(Text2SQLScopedConfig)
            .filter(
                Text2SQLScopedConfig.user_id == user_id,
                Text2SQLScopedConfig.connection_key == connection_key,
                Text2SQLScopedConfig.is_deleted == False,  # noqa: E712
            )
            .first()
        )

    def upsert(
        self,
        *,
        user_id: int,
        connection_key: str,
        selected_tables: str | None,
        prompt_hint: str | None,
    ) -> Text2SQLScopedConfig:
        """中文备注：处理相关业务数据并返回结果。
        执行流程：先处理输入与上下文，再执行核心逻辑，最后返回结果或抛出异常。
        """
        # 1. 变量构建：计算并更新 `config`。
        config = self.get_by_user_and_connection(user_id, connection_key)
        # 2. 条件分支：根据当前状态选择不同处理路径。
        if config is None:
            config = Text2SQLScopedConfig(
                user_id=user_id,
                connection_key=connection_key,
                selected_tables=selected_tables,
                prompt_hint=prompt_hint,
                is_deleted=False,
            )
            self.db.add(config)
        else:
            config.selected_tables = selected_tables
            config.prompt_hint = prompt_hint
            config.is_deleted = False

        # 3. 外部调用：执行数据库或接口调用并接收返回值。
        self.db.commit()
        self.db.refresh(config)
        # 4. 返回结果：输出当前函数最终结果。
        return config
