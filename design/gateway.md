# design/gateway.md v1.23

## 1. 任务目标 (Objective)
重构 **ClawBrain Gateway** 的路由与适配层，构建一个支持 30+ 主流 LLM 提供商（Ollama, vLLM, DeepSeek, Claude, OpenRouter 等）的**通用协议翻译网关 (Universal Translation Gateway)**。在保持神经记忆系统（压缩、注入、准入）正常工作的前提下，实现极高可扩展性的 Provider 接入机制。

## 2. 核心架构重构 (Architecture Redesign)

### 2.1 动态协议探测与标准化 (Ingress Standardization)
- **ProtocolDetector (协议探测器)**：
  - 拦截所有 HTTP 请求，通过分析 Payload 结构（如是否存在 `model` 字段、`messages` 格式是否为 OpenAI/Anthropic 标准）自动推断输入协议类型。
- **Standardization (标准化)**：
  - 将异构的输入（如 Ollama 格式或 Anthropic 格式）统一转化为内部对象 `StandardInteractionRequest`。
  - **核心准则**：`MemoryRouter`、`Pipeline` 和 `ModelScout` 等所有核心逻辑**仅针对** `StandardInteractionRequest` 进行操作（如注入系统提示词、压缩空格），实现业务逻辑与底层协议的完全解耦。

### 2.2 提供商路由与方言翻译 (Provider Routing & Translation)
- **ProviderRegistry (动态注册表)**：
  - 废弃硬编码的 Adapter 实例。系统根据配置动态加载提供商信息（包含 BaseURL, API Key, 默认协议类型等）。
- **DialectTranslators (方言翻译器)**：
  - 根据请求指定的 `Target Provider`（通常通过模型名前缀如 `deepseek/` 或 `openrouter/` 解析得出），调用对应的翻译器。
  - 将处理后的 `StandardInteractionRequest` 翻译为目标 Provider 认可的原生 JSON Payload (例如转换为 Anthropic 的 `system` 顶层字段 + `messages` 数组格式)。

### 2.3 统一流式响应与反向翻译 (Egress Stream Handling)
- 适配器必须具备**双向翻译能力**。
- 如果客户端使用 OpenAI 格式发起请求，但目标后端是 Ollama：
  1. 网关将请求翻译为 Ollama 格式发往后端。
  2. 网关接收 Ollama 的 NDJSON 流式响应。
  3. **反向翻译**：网关必须将 NDJSON 实时解析，并重新包装为客户端期望的 OpenAI SSE (`data: {...}`) 格式返回。
- 在流结束时，统一提取完整内容，交由 `MemoryRouter.ingest()` 进行闭环存证。

### 2.4 模型准入引擎 (ModelScout)
- 对于云端 API（如 OpenAI, DeepSeek），通常具备极强的能力。`ModelScout` 需支持基于 Provider 前缀的默认放行策略（例如 `openai/*` 默认视为 TIER_1），同时保留对本地模型（如 `ollama/*`）的细粒度参数量探测。

## 3. 测试与审计规范 (TDD & High-Fidelity Audit)

### 3.1 跨协议透传审计 (Fixed Mock Logic)
- **场景**：客户端发送 OpenAI 格式请求，指定目标为 `ollama/gemma4:e4b`。
- **Mock 规范约束 (Fixed)**：由于 `httpx.Response.json()` 是同步方法，在编写测试的 Mock 时，`mock_post.return_value` 对应的 Response 对象必须配置其 `json` 方法返回纯 JSON 数据而非协程（避免使用 AsyncMock 装饰同步方法）。这确保了网关在闭环存储执行 `json.dumps()` 时不发生序列化错误。
- **验证点**：
  1. 验证内部是否成功转换为 `StandardInteractionRequest` 并完成了记忆注入（包含 TIER_2 补丁）。
  2. 验证发往 Ollama 的 Payload 是否符合 Ollama 协议要求。
  3. 验证返回给客户端的流式数据是否被正确反向翻译回 OpenAI 的 SSE 格式。
- **审计展示**：日志必须明确打印 `Incoming Protocol -> Internal Standard -> Target Dialect` 的转换链路凭证。

## 4. 生成目标
- `src/gateway/detector.py`: 协议探测与标准化逻辑。
- `src/gateway/translator.py`: 各提供商的方言翻译与流式反向包装逻辑。
- `src/gateway/registry.py`: 动态提供商注册表。
- `src/main.py`: 重构后的统一入口。
- `tests/test_p12_universal_routing.py`: 跨协议路由与翻译专项验收测试。
