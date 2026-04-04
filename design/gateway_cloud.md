# design/gateway_cloud.md v1.1

## 1. 任务目标 (Objective)
实现 ClawBrain 对 **Anthropic (Claude 3.5)** 和 **DeepSeek** 等云端提供商的原生支持。重点：严格对齐 Anthropic 官方 Messages API 规格，确保在异构协议转换下的逻辑确定性。

## 2. 核心架构逻辑 (Architecture)

### 2.1 协议翻译增强 (Dialect Translation)
- **Anthropic 翻译器 (`to_anthropic`)**：
  - **System 剥离**：将 `messages` 数组中的所有 `role: system` 条目剥离，合并为 Anthropic 要求的顶层 `system` 字符串字段。
  - **必填项补全**：Anthropic 协议强制要求 `max_tokens`。若请求缺失，必须强制注入默认值 4096。
  - **角色交替规范 (Role Normalization)**：Anthropic 要求角色必须交替。翻译器必须自动合并连续的相同角色消息（如 user + user 聚合为单条 user），确保请求合规。
  - **流式对齐**：处理 Anthropic 特有的 SSE 事件（如 `content_block_delta`），反向翻译为标准 OpenAI 兼容格式。
- **DeepSeek 支持**：保持 OpenAI 格式透传逻辑。

### 2.2 凭证透传与网络安全 (Security)
- **Header 镜像**：针对 Anthropic 自动将 `Authorization` 转换为 `x-api-key`（如有必要）并原样透传凭证。
- **HTTPS 适配**：确保异步连接池支持云端 TLS 连接。

## 3. 高保真审计与集成测试规范 (TDD)

### 3.1 规格对齐审计 (Schema Compliance Audit)
- **场景 A: 角色合并验证**：发送带两条连续 user 消息的请求，验证 Anthropic 格式中已合并为一条。
- **场景 B: 必填字段验证**：验证 `max_tokens` 被准确补全。
- **场景 C: System 映射验证**：Side-by-Side 展示 `StandardRequest (System Message)` -> `Anthropic Payload (System Field)`。

### 3.2 云端流式透传审计
- **验证点**：模拟云端 SSE 返回，验证反向翻译后的 TTFT 稳定性。

## 4. 生成目标
- `src/gateway/translator.py`: 包含符合规格的翻译逻辑。
- `src/gateway/registry.py`: 更新提供商映射。
- `tests/test_p13_cloud_adapters.py`: 规格对齐专项验收测试。
