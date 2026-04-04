# design/memory_integration.md v1.2

## 1. 任务目标 (Objective)
全量集成神经记忆系统至 **ClawBrain Universal Gateway**。确保网关在处理来自 30+ 提供商的请求时，能够自动执行“三子算法”记忆合成与存证，并支持基于模型窗口的动态分流。

## 2. 核心架构设计 (Integration Architecture)

### 2.1 记忆路由器增强 (MemoryRouter)
- **自洽初始化**：构造函数必须接收 `db_dir` 和 `distill_threshold`（语义整合周期），并透传至 `Hippocampus` 与 `Neocortex`。
- **状态恢复 (Hydration)**：启动时必须从 SQLite 自动加载最近 15 条消息进入 `WorkingMemory`。
- **摄入契约**：`ingest()` 必须支持 `payload` (Stimulus), `reaction` (Assistant Response) 以及 `offload_threshold` (动态分流阈值)。

### 2.2 通用网关集成 (Main Gateway Integration)
- **生命周期 (Lifespan)**：
  - 在 `lifespan` 中初始化全局 `MemoryRouter` 并挂载至 `app.state.memory_router`。
- **请求增强流 (Request Pipeline)**：
  1. 在 `_process_request` 中，网关根据目标模型的 **Context Window** 计算 `offload_threshold` (建议设为窗口的 10%)。
  2. 调用 `MemoryRouter.get_combined_context()` 获取增强文本。
  3. **强制注入**：将该增强文本作为 `role: system` 消息插入到请求消息流的最前端。
- **响应闭环流 (Response Completion)**：
  - 收到后端完整响应（非流式）或流式结束（流式）后，异步调用 `MemoryRouter.ingest()`。

### 2.3 异常隔离与降级
- 记忆系统的 IO 失败或 LLM 提炼失败不得中断网关的原始透传链路。

## 3. 高保真审计与集成测试规范 (TDD)

### 3.1 全链路记忆回响审计 (Memory Echo Audit)
- **场景**：
  1. 客户端发送第一条消息："The project codename is 'NEURAL-X'."
  2. 客户端发送第二条消息："Recall the codename."
- **验证**：第二次请求发往上游（如 Ollama）的 Payload 中必须包含第一条消息的记忆增强块。
- **审计展示**：Side-by-Side 展示 `Round 1 Response` -> `Round 2 Inbound Context Enhancement`。

## 4. 生成目标
- `src/main.py`: 全量集成 Memory 调度。
- `src/memory/router.py`: 确保符合最新整合周期的初始化。
- `tests/test_p11_integration.py`: 全链路集成审计测试。
