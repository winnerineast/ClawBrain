# design/docker.md v1.0

## 1. 任务目标 (Objective)
为 ClawBrain 提供生产级 Docker 部署方案。目标：单命令启动（`docker compose up -d`），数据持久化，所有运行时参数通过 env var 注入，不硬编码任何路径或密钥。

## 2. 核心架构决策 (Architecture Decisions)

### 2.1 Dockerfile
- **基础镜像**：`python:3.12-slim`（最小化攻击面，与本机 Python 3.12.3 对齐）
- **工作目录**：`/app`
- **依赖安装**：仅复制 `requirements.txt` 先安装，利用 Docker 层缓存（源码变动不触发重装）
- **运行用户**：创建非 root 用户 `clawbrain`（uid=1000），以最小权限运行
- **启动命令**：`uvicorn src.main:app --host 0.0.0.0 --port 11435 --workers 1`
  - `workers=1`：保证单进程内 in-memory WorkingMemory 会话状态一致（多进程会导致各进程 WM 不共享）
  - 如需水平扩展，须先将 WorkingMemory 迁移至 Redis；现阶段单进程即可

### 2.2 docker-compose.yml
- **服务**：单一 `clawbrain` 服务
- **端口映射**：`11435:11435`（与 README 承诺对齐）
- **数据卷**：`./data:/app/data`（SQLite DB + blobs 持久化到宿主机，容器重启不丢数据）
- **env_file**：`.env`（用户在此配置 API 密钥等敏感信息，不进入镜像）
- **restart policy**：`unless-stopped`（宿主重启自动拉起）
- **healthcheck**：`curl -f http://localhost:11435/health`，30s 间隔，3 次重试

### 2.3 环境变量清单（全量）
| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `CLAWBRAIN_DB_DIR` | `/app/data` | SQLite DB 与 blobs 目录（容器内路径）|
| `CLAWBRAIN_MAX_CONTEXT_CHARS` | `2000` | 上下文预算字符数上限 |
| `CLAWBRAIN_TRACE_TTL_DAYS` | `30` | trace 记录 TTL（0=禁用）|
| `CLAWBRAIN_EXTRA_PROVIDERS` | _(空)_ | JSON 字符串，注入额外 Provider |
| `CLAWBRAIN_LOCAL_MODELS` | _(空)_ | JSON 字符串，注入本地模型白名单 |

### 2.4 .env.example
提供 `.env.example` 模板，列出所有可配变量，敏感值用占位符。`.env` 加入 `.gitignore`（已存在）。

### 2.5 .dockerignore
排除：`venv/`, `__pycache__/`, `tests/`, `data/`, `.env`, `*.pyc`, `.git/`
目的：最小化构建上下文，data 目录通过 volume 挂载而非打包进镜像。

## 3. 生成目标 (Output Targets)
- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `.dockerignore`
