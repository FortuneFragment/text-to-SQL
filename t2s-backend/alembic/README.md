# Alembic 使用说明

在 `t2s-backend` 目录执行：

```bash
alembic upgrade head
```

新增迁移：

```bash
alembic revision --autogenerate -m "描述本次变更"
```

回滚一步：

```bash
alembic downgrade -1
```

说明：

- 服务启动阶段已不再自动建表。
- 数据库结构应统一通过 Alembic 迁移管理。
