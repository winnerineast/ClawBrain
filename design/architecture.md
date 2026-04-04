# design/architecture.md v1.0

## 1. 项目愿景 (Vision)
ClawBrain 是一个轻量级、非侵入式、高性能的通用 LLM 网关代理。它作为 OpenClaw（或其他 AI 客户端）与底层 LLM（如 Ollama, OpenAI, vLLM）之间的“外挂大脑”和“Token 节流阀”。

它的核心使命是：**在不修改客户端代码的前提下，最大化利用有限的上下文窗口，并提供灵活的模型路由。**

## 2. 核心系统模块 (Core Modules)

整个系统将被拆分为以下几个独立且可解耦的模块，后续将逐一通过独立的 Prompt 进行代码生成：

### 模块 A: 核心网关代理 (Core Proxy Gateway)
- **职责**：充当 HTTP 服务器，提供 OpenAI API / Ollama API 兼容的端点。
- **功能**：
  - 接收来自 OpenClaw 的请求。
  - 解析 HTTP 请求体（JSON）。
  - 支持 SSE (Server-Sent Events) 流式响应透传。
  - 将处理后的请求转发给真实的 Backend LLM，并将响应原样返回给客户端。

### 模块 B: 上下文提纯器 (Context Distiller / Optimizer)
- **职责**：对请求中的 `messages` 和 `prompt` 进行“瘦身”。
- **功能**：
  - **空白压缩**：使用正则剔除代码块和文本中多余的连续空格、制表符和换行符，且保证代码语义不被破坏。
  - **去重逻辑**：识别并移除多轮对话中重复注入的冗长 Tool Schema 或 System Prompt。
  - **安全截断**：当预估 Token 接近上限（如 64k）时，根据优先级安全丢弃最旧的非关键中间日志。

### 模块 C: 智能路由网关 (Smart Router)
- **职责**：决定将请求发往哪个物理后端。
- **功能**：
  - 根据请求中的 `model` 字段，将请求路由到本地 Ollama (如 `gemma4:e4b`) 或远端 API (如 OpenAI, DeepSeek)。
  - 支持环境变量配置不同后端的 `BaseURL` 和 `API_KEY`。

### 模块 D: 外挂记忆引擎 (External Memory / RAG) - [规划中]
- **职责**：为短上下文模型提供长效记忆池。
- **功能**：
  - 检索相关知识并注入 System Prompt。

## 3. 实施路线图 (Implementation Roadmap)

- **Phase 1**: 生成 `Module A` (基础网关) + `Module C` (基础转发路由)。确保连通性。
- **Phase 2**: 生成 `Module B` (上下文压缩器)，并集成到网关中。
- **Phase 3**: 为所有核心逻辑生成测试报告（nisi 格式）。
- **Phase 4**: 扩展多模型、多后端支持。
