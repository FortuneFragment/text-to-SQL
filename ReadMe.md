# 项目启动说明

## 1. 启动后端服务

进入后端项目目录：

```bash
cd t2s-backend
```

### 1.1 创建虚拟环境

```bash
python -m venv venv
```

### 1.2 激活虚拟环境

Windows PowerShell / CMD：

```bash
.\venv\Scripts\Activate
```

### 1.3 安装依赖

```bash
pip install -r requirements.txt
```

### 数据库初始化（首次部署）

配置好 `t2s-backend/.env` 中的 MySQL 连接后执行：

```bash
alembic upgrade head
```

项目只保留一个完整基线迁移；该命令会一次性创建当前版本需要的全部数据表，无需按历史版本逐个执行。

### 1.4 启动后端

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

后端服务默认运行在：

```text
http://localhost:8000
```

---

## 2. 启动 Celery 异步任务

打开一个新的终端窗口，进入后端项目目录：

```bash
cd t2s-backend
```

激活虚拟环境：

```bash
.\venv\Scripts\Activate
```

启动 Celery Worker：

```bash
.\venv\Scripts\celery.exe -A tasks.celery_app:celery_app worker -Q text2sql-kb --loglevel=INFO
```

其中：

* `-A tasks.celery_app:celery_app`：指定 Celery 应用实例
* `-Q text2sql-kb`：监听 `text2sql-kb` 队列
* `--loglevel=INFO`：设置日志级别为 `INFO`

### 2.1 生产环境启动 Celery Beat

生产环境需要额外启动 Celery Beat，用于执行定时任务。

打开一个新的终端窗口：

```bash
cd t2s-backend
```

激活虚拟环境：

```bash
.\venv\Scripts\Activate
```

启动 Celery Beat：

```bash
celery -A tasks.celery_app:celery_app beat --loglevel=INFO
```

---

## 3. 启动前端服务

进入前端项目目录：

```bash
cd t2s-frontend
```

### 3.1 安装依赖

```bash
npm install
```

### 3.2 启动开发环境

```bash
npm run dev
```

启动成功后，根据终端输出的地址访问前端页面，通常为：

```text
http://localhost:5173
```

---

## 4. 本地开发启动顺序

本地开发建议分别打开三个终端窗口，并按照以下顺序启动：

1. 后端服务
2. Celery Worker
3. 前端服务

生产环境还需要额外启动：

4. Celery Beat
