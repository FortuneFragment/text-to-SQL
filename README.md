# Text2SQL Workspace

## 项目说明
本仓库包含一个 Text2SQL 后端（FastAPI）和一个前端（Vue + Vite），用于连接外部数据库、配置可查询表并执行自然语言问答。

## 目录结构
- `t2s-backend`：后端服务
- `t2s-frontend`：前端页面

## 环境要求
- Python 3.10+
- Node.js 18+
- Docker（可选，用于 MySQL / Redis / MinIO / Milvus）

## 后端启动（手动激活虚拟环境）
按当前项目约定，后端启动步骤如下：

```powershell
cd t2s-backend

# 首次使用可创建虚拟环境（已有可跳过）
python -m venv venv

# 手动进入虚拟环境
.\venv\Scripts\activate

# 安装依赖
pip install -r requirement.txt

# 启动后端
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 前端启动
```powershell
cd t2s-frontend
npm install
npm run dev
```

## Docker 启动（MySQL + Redis + MinIO + Milvus）
```powershell
cd t2s-backend
docker compose up -d
```

如需启动 Celery Worker（本地进程）：

```powershell
cd t2s-backend
.\venv\Scripts\activate
celery -A tasks.celery_app.celery_app worker -l info -Q text2sql-kb
```

说明：如果是首次启动，需要手动创建数据库：

```powershell
docker exec -it text2sql_mysql mysql -uroot -proot -e "CREATE DATABASE IF NOT EXISTS text2sql_system DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE DATABASE IF NOT EXISTS text2sql_biz DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

## 文档切分异步任务（Celery + Milvus）
提交任务：

```http
POST /api/v1/text2sql/task/document/ingest
```

支持三种输入方式（任选其一）：
- `text`：直接提交文档文本
- `local_path`：读取后端机器本地文件
- `object_name` + `bucket_name`：从 MinIO 读取对象

查询状态：

```http
GET /api/v1/text2sql/task/{task_id}
```


