# design/gateway.md v1.16

## 1. 系统愿景 (Objective)
生成名为 **ClawBrain Gateway** 的高性能异步 LLM 网关。该网关作为“外挂大脑”，在不侵入客户端的前提下实现多协议路由、模型准入审计、上下文压缩优化以及全局资源生命周期管理。

## 2. 核心架构与逻辑 (Architecture & Logic)

### 2.1 协议入口与路由 (Ingress & Routing)
- **FastAPI 核心**：使用 APIRouter 管理路径。
- **协议路由**：
  - `POST /api/chat` -> 路由至 `OllamaAdapter`。
  - `POST /v1/chat/completions` -> 路由至 `OpenAIAdapter` (Stub)。
- **生命周期 (Lifespan)**：必须使用 `lifespan` 钩子初始化全局 `ModelScout` 和 `Adapters`。

### 2.2 模型准入引擎 (ModelScout)
- **TIER 评级准则**：
  - `TIER_1_NATIVE`: 参数 >= 7B 且 `ollama show` 元数据包含 `TOOLS` 支持。允许全功能通行。
  - `TIER_2_REASONING`: 参数 >= 14B 但无原生工具支持。允许工具调用，但需注入补丁。
  - `TIER_3_BASIC`: 参数 < 7B。若请求包含 `tools` 字段，**必须拦截并返回 HTTP 422**。
- **缓存层**：内置 10 分钟 TTL 的 LRU 内存缓存，避免重复查询元数据。

### 2.3 拦截器流水线 (Interceptor Pipeline)
- **WhitespaceCompressor**：
  - 先使用正则 `(```[\s\S]*?```)` 提取并保护代码块。
  - 仅对非代码区域执行：2+ 空格变为 1，3+ 换行变为 2。
- **SafetyEnforcer**：
  - 为 TIER_2 模型在消息首位注入 `[SYSTEM ENFORCEMENT]: Respond ONLY in JSON.` 补丁。
  - 必须具备幂等性检查，防止重复注入。

### 2.4 后端适配器 (OllamaAdapter)
- **资源管理**：使用 **惰性初始化 (Lazy Init)** 的 `httpx.AsyncClient` 连接池，确保与 Event Loop 绑定。
- **流式容错**：透传后端流式数据前必须验证 `response.is_error`。后端异常时应生成 JSON 错误片段。

## 3. 测试驱动与审计规范 (TDD & Audit)

### 3.1 测试环境约束 (Critical)
- **生命周期对齐**：所有测试用例必须使用 `with TestClient(app) as client:` 语法，以确保触发 FastAPI 的 `lifespan` 初始化逻辑。

### 3.2 验证维度
- **精确匹配**：集成测试必须进行逐字符比对。
- **审计日志**：日志必须包含 `Input` (repr)、`Expected` (repr) 和 `Actual` (repr)。

## 4. 生成目标 (Output Targets)
- `src/main.py`: 入口与 Lifespan。
- `src/scout.py`: 评级引擎与缓存。
- `src/pipeline.py`: 压缩与增强流水线。
- `src/adapters/ollama.py`: 适配器实现。
- `tests/test_p5_e2e.py`: 遵循生命周期规范的 E2E 测试脚本。
