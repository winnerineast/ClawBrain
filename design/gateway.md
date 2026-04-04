# design/gateway.md v1.26

## 1. 任务目标 (Objective)
全量实现 ClawBrain Gateway 对主流 LLM 提供商（Google Gemini, Mistral, xAI, OpenRouter 等）的协议适配。构建一个真正的“万能神经翻译器”，确保所有在 README 中承诺的平台都能通过 ClawBrain 进行记忆增强。

## 2. 核心架构逻辑 (Universal Translation)

### 2.1 协议方言扩展 (Extended Dialects)
- **Google (Gemini)**：
  - **翻译器 (`to_google`)**：将 `messages` 转换为 `contents` 数组，将 `role: assistant` 映射为 `model`，将 `system` 消息映射为顶层 `system_instruction`。
- **Anthropic (Claude)**：
  - [保持 v1.25 逻辑：System 剥离 + 角色交替合并 + max_tokens 补全]。
- **OpenAI 兼容簇 (DeepSeek, Mistral, Grok, vLLM, OpenRouter)**：
  - **翻译器 (`to_openai`)**：统一处理模型前缀剥离。针对 OpenRouter，自动注入必要的 Web 标识 Header（如 `HTTP-Referer`）。

### 2.2 提供商注册表扩展 (Registry)
- `ProviderRegistry` 必须包含以下内置映射：
  - `google` -> `https://generativelanguage.googleapis.com`
  - `mistral` -> `https://api.mistral.ai`
  - `xai` -> `https://api.xai.com`
  - `openrouter` -> `https://openrouter.ai/api`
  - `together` -> `https://api.together.xyz`

### 2.3 智能协议探测
- `ProtocolDetector` 应能识别更多的输入方言（如果客户端直接以 Google 格式发送请求）。

## 3. 高保真审计与测试规范 (TDD)

### 3.1 跨平台翻译对齐审计
- **场景 A: Google Gemini 转换**：验证 `role: assistant` 是否被正确翻译为 `role: model`。
- **场景 B: OpenRouter 透传**：验证模型名是否被正确剥离前缀。
- **场景 C: 角色交替合并 (Anthropic)**：继续验证连续 User 消息的合并逻辑。

### 3.2 审计展示
- 日志必须 Side-by-Side 展示 `Internal Standard` -> `Provider Specific Dialect`。

## 4. 生成目标
- `src/gateway/translator.py`: 包含 Google, OpenAI, Anthropic, Ollama 全量翻译逻辑。
- `src/gateway/registry.py`: 包含完整的提供商列表。
- `tests/test_p13_universal_dialects.py`: 跨平台方言转换专项验收测试。
