# design/gateway.md v1.25

## 1. 任务目标 (Objective)
重构 ClawBrain Gateway 为 **“透明神经中继”**。
核心原则：**凭证透传，零重复配置**。网关仅负责识别路由并执行记忆增强，所有鉴权信息（API Key）由客户端提供并由网关透明转发。

## 2. 核心架构逻辑 (Architecture)

### 2.1 凭证透传机制 (Header Pass-through)
- **动作**：网关必须从客户端请求中提取所有的 `headers`（特别是 `Authorization` 和 `Content-Type`）。
- **转发**：在向真实后端（Upstream）发起请求时，必须原样附加这些 Headers。
- **优势**：ClawBrain 无需存储任何 API Key，降低了安全风险并简化了配置。

### 2.2 智能路由注册表 (Smart Upstream Registry)
- **Registry 职责**：仅维护 `Provider Name -> Target Base URL` 的映射。
- **内置映射**：
  - `ollama` -> `http://127.0.0.1:11434`
  - `lmstudio` -> `http://127.0.0.1:1234`
  - `openai` -> `https://api.openai.com`
  - `deepseek` -> `https://api.deepseek.com`
  - `anthropic` -> `https://api.anthropic.com`
- **动态分发**：根据 `model` 前缀动态切换请求的 `host`。

### 2.3 处理管道 (Pipeline & Memory)
[保持 v1.24 的统一处理逻辑：Scout, Memory, Compressor]

## 3. 测试与审计规范 (TDD)

### 3.1 凭证透传专项审计 (Credential Transparency Audit)
- **验证点**：
  1. 模拟客户端发送带 `Authorization: Bearer MOCK-KEY` 的请求。
  2. 验证 ClawBrain 发往真实后端的请求中，Header 是否完整保留了 `MOCK-KEY`。
- **审计展示**：Side-by-Side 展示 `Incoming Header` -> `Forwarded Header`。

## 4. 生成目标
- `src/gateway/registry.py`: 仅保留 URL 映射逻辑。
- `src/main.py`: 实现全量 Header 透传逻辑。
- `README.md` & `README_EN.md`: 更新为“零配置挂载”说明。
