# Text2SQL Workspace

## 项目说明
本仓库包含一个 Text2SQL 后端（FastAPI）和一个前端（Vue + Vite），用于连接外部数据库、配置可查询表并执行自然语言问答。

## 目录结构
- `t2s-backend`：后端服务
- `t2s-frontend`：前端页面

## 环境要求
- Python 3.10+
- Node.js 18+
- Docker（可选，仅用于 MySQL / Redis）

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

## Docker 启动（仅 MySQL + Redis）
```powershell
cd t2s-backend
docker compose up -d
```

说明：当前 `docker-compose.yml` 已移除 `./mysql/init` 挂载，不会自动初始化数据库脚本。
如果是首次启动，需要手动创建数据库：

```powershell
docker exec -it text2sql_mysql mysql -uroot -proot -e "CREATE DATABASE IF NOT EXISTS text2sql_system DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE DATABASE IF NOT EXISTS text2sql_biz DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

## 推送到 GitHub
```powershell
git init
git add .
git commit -m "init project"
git branch -M main
git remote add origin <你的仓库地址>
git push -u origin main
```

## 说明
- 已在项目配置中关闭 PyCharm 终端自动激活虚拟环境。
- `.vscode` 已移除。
