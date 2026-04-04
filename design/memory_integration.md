# design/memory_integration.md v1.1

## 1. 任务目标 (Objective)
全量集成神经记忆系统至网关。重点：确保 `MemoryRouter` 与 `OllamaAdapter` 深度绑定，实现每一轮对话的自动记忆摄入与上下文增强。

## 2. 核心架构设计 (Integration Details)

### 2.1 路由器增强 (MemoryRouter)
- **持久化恢复 (Fixed)**：构造函数必须正确导入 `json` 并在初始化时通过 `_hydrate()` 从 SQLite 恢复最近 15 条消息。
- **摄入接口**：`ingest()` 必须支持同时接收 `stimulus` 和 `reaction` 字典。

### 2.2 适配器集成 (OllamaAdapter)
- **上下文增强逻辑**：
  1. 在 `chat()` 开始处，调用 `MemoryRouter.get_combined_context()` 获取增强文本。
  2. **强制注入**：将该增强文本作为一条新的 `system` 消息，插入到 `body["messages"]` 的**最前端**。
- **闭环存储逻辑**：
  - 成功获取响应后，调用 `MemoryRouter.ingest(input_body, output_body)`。

### 2.3 入口生命周期 (Main)
- 在 `lifespan` 钩子中初始化全局 `MemoryRouter` 并挂载至 `app.state.memory_router`。

## 3. 高保真审计与测试规范 (TDD)

### 3.1 全链路记忆集成测试 (E2E Integration Audit)
- **场景**：
  1. 向网关发送消息 "Project ID is ALPHA-1"。
  2. 第二次发送消息 "What is my project ID?"。
- **验证**：第二次请求发送给后端 Ollama 的 Payload 中必须包含 "Project ID is ALPHA-1" 的记忆增强块。
- **审计展示**：Side-by-Side 展示 `User Input` -> `Enriched Context sent to Ollama`。

## 4. 生成目标
- `src/main.py`, `src/adapters/ollama.py`, `src/memory/router.py`, `tests/test_p11_integration.py`。
