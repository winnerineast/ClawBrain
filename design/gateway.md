# design/gateway.md v1.29

## 1. 任务目标 (Objective)
全量实现 ClawBrain Gateway 对主流 LLM 提供商（Google Gemini, Mistral, xAI, OpenRouter 等）的协议适配。构建一个真正的“万能神经翻译器”，确保所有在 README 中承诺的平台都能通过 ClawBrain 进行记忆增强。同时，全量补齐结构化日志系统，确保每一项神经活动均具备透明度。

## 2. 核心架构逻辑 (Architecture)

### 2.1 协议方言扩展 (Extended Dialects)
- **Google (Gemini)**：
  - **翻译器 (`to_google`)**：将 `messages` 转换为 `contents` 数组，将 `role: assistant` 映射为 `model`，将 `system` 消息映射为顶层 `system_instruction`。
- **Anthropic (Claude)**：
  - **翻译器 (`to_anthropic`)**：剥离 `role: system` 到顶层 `system` 字段；执行角色交替正规化（合并连续重复角色）；强制补全 `max_tokens` (默认 4096)。
- **OpenAI 兼容簇 (DeepSeek, Mistral, Grok, vLLM, OpenRouter)**：
  - **翻译器 (`to_openai`)**：统一处理模型前缀剥离。针对 OpenRouter，自动注入必要的 Web 标识 Header（如 `HTTP-Referer`）。

### 2.2 提供商注册表扩展 (Registry)
- `ProviderRegistry` 必须包含以下内置映射：
  - `google` -> `https://generativelanguage.googleapis.com`
  - `mistral` -> `https://api.mistral.ai`
  - `xai` -> `https://api.xai.com`
  - `openrouter` -> `https://openrouter.ai/api`
  - `together` -> `https://api.together.xyz`

### 2.3 动态协议探测
- `ProtocolDetector` 必须能够拦截所有 HTTP 请求，通过分析 Payload 结构自动推断输入协议类型（Ollama/OpenAI）。

### 2.4 结构化日志系统 (Logging System)
- **全局配置**：系统必须使用统一的 `logging` 模块，格式为：`[TIMESTAMP] [MODULE] [LEVEL] MESSAGE | {METADATA}`。
- **强制埋点**：
  - **[DETECTOR]**: 记录源协议类型、请求模型及会话 ID。
  - **[PIPELINE]**: 记录内容压缩前后的长度变化及压缩率。
  - **[MODEL_QUAL]**: 记录模型评级（TIER 1/2/3）及采取的动作（拦截/补丁/放行）。
  - **[HP_STOR]**: 记录海马体存储动作。必须使用 `logging.getLogger("GATEWAY.MEMORY")` 声明子 Logger，以确保其日志能够正确冒泡至 root logger 并被全局监听器（如 pytest）捕获。
  - **[ADAPTER]**: 记录转发的目标提供商、翻译方言及 API Key 探测状态。

## 3. 高保真审计与测试规范 (TDD & High-Fidelity Audit)

### 3.1 跨平台翻译对齐审计
- **场景 A: Google Gemini 转换**：验证 `role: assistant` 是否被正确翻译为 `role: model`。
- **场景 B: OpenRouter 透传**：验证模型名是否被正确剥离前缀。
- **场景 C: 角色交替合并 (Anthropic)**：验证连续 User 消息的合并逻辑。

### 3.2 审计展示与日志验收
- **对比展示**：日志必须 Side-by-Side 展示 `Internal Standard` -> `Provider Specific Dialect`。
- **完备性验收 (Fixed)**：单次请求的审计日志中必须完整、顺序出现 2.4 节定义的所有关键埋点标签。由于存储动作可能是异步的，测试代码必须具备显式的等待机制（如 `asyncio.sleep`），确保所有后台日志均已被监听器捕获后再执行断言。

## 4. 生成目标
- `src/main.py`: 集成全局日志配置与全量埋点。
- `src/gateway/detector.py`: 补齐探测阶段日志.
- `src/gateway/translator.py`: 补齐翻译阶段日志.
- `src/gateway/registry.py`: 保持提供商全量映射.
- `src/memory/router.py`: 使用子 Logger 确保日志传播.
- `tests/test_p12_universal_routing.py`: 包含异步等待机制的日志完备性专项验收。
