# design/gateway.md v1.34

## 1. 任务目标 (Objective)
全量实现 ClawBrain Gateway 对主流 LLM 提供商（Google Gemini, Mistral, xAI, OpenRouter 等）的协议适配。构建一个真正的“万能神经翻译器”，确保所有在 README 中承诺的平台都能通过 ClawBrain 进行记忆增强。同时，全量补齐结构化日志系统，确保每一项神经活动均具备透明度。

## 2. 核心架构逻辑 (Architecture)

### 2.1 协议方言扩展 (Extended Dialects)
- **Google (Gemini)**：将 `messages` 转换为 `contents` 数组，将 `role: assistant` 映射为 `model`，将 `system` 消息映射为顶层 `system_instruction`。
- **Anthropic (Claude)**：剥离 `role: system` 到顶层 `system` 字段；执行角色交替正规化（合并连续重复角色）；强制补全 `max_tokens` (默认 4096)。
- **OpenAI 兼容簇 (DeepSeek, Mistral, Grok, vLLM, OpenRouter)**：统一处理模型前缀剥离。针对 OpenRouter，自动注入必要的 Web 标识 Header。

### 2.2 提供商注册表扩展 (Registry & Routing Security)
- `ProviderRegistry` 必须包含内置映射：google, mistral, xai, openrouter, together, ollama, lmstudio, openai, deepseek。
- **路由安全性 (Fixed)**：如果请求的模型无法被 `resolve_provider` 识别（即不包含有效前缀且不是原生 ollama 格式），系统**必须严禁任何形式的静默回退**。`resolve_provider` 必须返回 `(None, None)`，由上层抛出 **HTTP 501 Not Implemented**。禁止将此类请求发往任何后端适配器以防止协议错配导致的 404 错误。

### 2.3 动态协议探测与标准化 (Fixed)
- **ProtocolDetector**：必须能够拦截所有 HTTP 请求，通过分析 Payload 结构自动推断输入协议类型（Ollama/OpenAI）。
- **标准化逻辑补强**：必须显式地从原始 Payload 的顶层、`options` 或 `extra_body` 中提取 `tools`、`tool_choice`、`stream` 及 `options` 字段并填入 `StandardRequest`。严禁在转换过程中丢失关键元数据，以支持后续的准入拦截逻辑。

### 2.4 结构化日志系统 (Logging System)
- **全局配置**：系统必须使用统一的 `logging` 模块，格式为：`[TIMESTAMP] [MODULE] [LEVEL] MESSAGE | {METADATA}`。
- **强制埋点**：[DETECTOR], [PIPELINE], [MODEL_QUAL], [HP_STOR] (子 Logger), [ADAPTER]。

## 3. 高保真审计与测试规范 (TDD & High-Fidelity Audit)

### 3.1 跨平台翻译对齐审计
- **场景 A: Google Gemini 转换**；**场景 B: OpenRouter 透传**；**场景 C: 角色交替合并 (Anthropic)**；**场景 D: LM Studio 真实环境 E2E 验证**。

### 3.2 审计展示与日志验收 (Enhanced)
- **对比展示**：日志必须 Side-by-Side 展示 `Internal Standard` -> `Provider Specific Dialect`。
- **异步确证**：针对异步存储或流式请求，测试代码必须具备 **1.5s 以上** 的显式等待机制。
- **语义召回断言 (Fixed Bug)**：在马拉松长对话测试中，系统不仅要打印审计结果，还必须执行**硬断言**。模型回答必须包含金丝雀关键词（如 `Health Check` 或 `Observability`），若匹配结果为 `NO`，测试必须立即判定为失败（AssertionError），禁止“Match NO 却 PASSED”的现象。

## 4. 生成目标
- `src/main.py`, `src/gateway/detector.py`, `src/gateway/registry.py`: 保持 v1.33 逻辑。
- `tests/test_p5_e2e.py`: 强化马拉松召回的硬断言逻辑。
