# design/memory_integration.md v1.4

## 1. 任务目标 (Objective)
全量集成神经记忆系统。确保网关在真实运行环境下（如对接真实的 Ollama 实例），能够自动执行记忆存证与上下文增强。

## 2. 核心架构设计 (Integration Architecture)

### 2.1 记忆路由器增强 (MemoryRouter)
- **自洽初始化**：构造函数必须接收 `db_dir` 并透传至子模块。
- **状态恢复**：启动时自动加载最近 15 条消息。

### 2.2 通用网关集成 (Main Gateway Integration)
- **生命周期**：挂载全局 `MemoryRouter`。支持从 `CLAWBRAIN_DB_DIR` 读取路径。
- **请求增强**：将增强文本注入为请求消息流的首个 `role: system` 消息。
- **响应闭环 (Fixed)**：无论后端响应成功还是失败（只要有 JSON 返回），网关必须尝试捕获响应并执行 `ingest()`，以确保即使在调试阶段也能记录交互轨迹。

## 3. 高保真审计与集成测试规范 (TDD)

### 3.1 真实全链路记忆回响审计 (Real-Environment Smoke Test)
- **场景**：
  1. 向网关发送第一条消息："The project codename is 'NEURAL-X'."
  2. 客户端发送第二条消息："Recall the codename."
- **环境要求**：测试必须在真实的 Ollama (11434) 环境下运行。
- **验证点**：
  - 测试脚本必须先通过 `ollama pull` 确保 `gemma4:e4b` (或指定的金丝雀模型) 存在。
  - 第二次请求发往网关时，网关注入的 System Prompt 必须包含第一轮的秘密内容。
- **隔离要求**：必须通过 `CLAWBRAIN_DB_DIR` 环境变量隔离测试数据库。

## 4. 生成目标
- `src/main.py`: 确保即便后端 404，只要有有效 Payload 也尝试记录。
- `tests/test_p11_integration.py`: 移除所有 Mock，改为真实的 E2E 交互。
