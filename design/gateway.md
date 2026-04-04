# design/gateway.md v1.21

## 1. 任务目标 (Objective)
生成 **ClawBrain Gateway**。这是一个高性能、可扩展的 LLM 代理网关，支持 Ollama、OpenAI 以及 **LM Studio** 协议。它集成了模型准入审计、上下文压缩优化以及神经记忆系统。

## 2. 核心架构设计 (Architecture)

### 2.1 协议路由与入口 (Ingress & Routing)
- **FastAPI 核心**：使用 `lifespan` 管理全局资源（MemoryRouter, Connection Pools）。
- **路由规则**：
  - `POST /api/chat` -> `OllamaAdapter` (Base: http://127.0.0.1:11434)
  - `GET /api/tags` -> `OllamaAdapter.list_models`
  - `POST /v1/chat/completions` -> `OpenAIAdapter` (或 `LMStudioAdapter` 根据模型前缀)
- **异常处理 (Fixed)**：网关在解析 JSON 或转发请求时，必须精确捕获异常。严禁将业务逻辑抛出的 `HTTPException` (如 501) 误捕获并转化为 400 错误。路由函数应仅捕获真正的 JSON 解析错误。

### 2.2 模型准入引擎 (ModelScout)
- **TIER 评级**：
  - `TIER_1_EXPERT`: 参数 >= 20B 或 (参数 >= 7B 且支持 Tools)。
  - `TIER_2_LEGACY`: 7B <= 参数 < 20B 且不支持原生 Tools。需注入 JSON 补丁。
  - `TIER_3_BASIC`: 参数 < 7B。拦截带 `tools` 的请求并返回 422。
- **已知模型库 (KnownModels)**：内置 `qwen2.5:latest` 为 TIER_3，`gemma4:e4b` 为 TIER_1。

### 2.3 优化流水线 (Pipeline)
- **WhitespaceCompressor**：使用正则 `(```[\s\S]*?```)` 保护代码块缩进，压缩非代码区域的冗余空格(2+)与换行(3+)。
- **SafetyEnforcer**：为 TIER_2 模型幂等注入系统约束补丁。

### 2.4 记忆系统集成 (Memory Integration)
- **上下文增强**：发送给后端前，调用 `MemoryRouter.get_combined_context` 获取增强文本，并作为首个 `system` 消息注入。
- **轨迹闭环**：收到响应后，调用 `MemoryRouter.ingest` 存入“刺激-反应”对。

### 2.5 适配器实现 (Adapters)
- **OllamaAdapter**：模拟 Ollama v1 协议，支持 NDJSON 流式处理。
- **LMStudioAdapter**：模拟 OpenAI 协议，对接本地 LM Studio (1234 端口)。
- **OpenAIAdapter**：官方接口适配器（当前版本返回 501）。
- **资源管理**：所有适配器必须复用全局 `httpx.AsyncClient` 连接池，采用惰性初始化。

## 3. 测试与审计规范 (TDD & Audit)

### 3.1 跨提供商集成测试 (E2E)
- **场景**：
  1. 使用 `lmstudio/model` 验证路由至 1234 端口。
  2. 使用 `openai/model` 或无前缀模型，验证路由至 OpenAIAdapter 并返回 501。
- **验证**：确保状态码与设计契约 100% 对齐（501 必须为 501）。

### 3.2 审计标准
- 日志遵循 **Rule 3 & 8**：Side-by-Side 展示 `User Input` vs `Enriched Context`。

## 4. 生成目标
- `src/main.py`, `src/adapters/ollama.py`, `src/adapters/lmstudio.py`, `src/adapters/openai.py`, `tests/test_p12_lmstudio.py`。
