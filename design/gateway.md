# design/gateway.md v1.11

## 1. 任务目标 (Objective)
生成名为 **ClawBrain Protocol Router** 的核心分发组件。
系统必须根据入口路径 (Endpoint Path) 自动路由至对应的原生协议适配器，严禁进行跨协议的破坏性转换。

## 2. 核心架构设计 (Architecture)

### 2.1 路径分发规则 (Endpoint Routing)
- **Ollama 栈 (Path: /api/*)**:
  - 路由至 `OllamaAdapter`。
  - 职责：解析 Ollama 原生 JSON，调用 Pipeline 处理 `messages` 内容，转发至底层 Ollama。
- **OpenAI 栈 (Path: /v1/*)**:
  - 路由至 `OpenAIAdapter`。
  - 职责：解析 OpenAI 原生 JSON，调用 Pipeline 处理 `messages` 内容，转发至 OpenAI 兼容后端。

### 2.2 适配器接口修正 (Updated BaseAdapter)
- 适配器不再接收统一模型，而是接收 **FastAPI Request** 对象或其原始 JSON。
- 每一个适配器独立负责其协议下的 `chat()`, `generate()`, `tags()` 实现。

## 3. 自动化测试规格 (TDD Requirements)

### 3.1 协议隔离验证 (Mandatory)
- **Ollama 链路测试**：发送 `/api/chat`，验证只有 `OllamaAdapter` 被触发，且保留了 `options` 字段。
- **OpenAI 链路测试**：发送 `/v1/chat/completions`，验证只有 `OpenAIAdapter` 被触发。

### 3.2 路由容错
- 验证非法路径请求是否被正确拦截。

## 4. 审计标准 (Rule 8)
- 审计日志必须记录：`Entry Path` -> `Selected Adapter` -> `Target Backend`。

## 5. 生成目标 (Output Targets)
- `src/main.py`: 实现基于路径的分发逻辑。
- `src/adapters/ollama.py`: Ollama 原生协议适配。
- `src/adapters/openai.py`: OpenAI 原生协议适配 (Stub)。
- `tests/test_p4_router.py`: 路径分发与协议隔离审计。
