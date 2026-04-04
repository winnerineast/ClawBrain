# design/gateway_cloud.md v1.0

## 1. 任务目标 (Objective)
实现 ClawBrain 对 **Anthropic (Claude 3.5)** 和 **DeepSeek** 等云端提供商的原生支持。重点：验证“零配置透传”架构在异构协议（OpenAI vs Anthropic）转换下的稳定性和准确性。

## 2. 核心架构逻辑 (Architecture)

### 2.1 协议翻译增强 (Dialect Translation)
- **Anthropic 翻译器 (`to_anthropic`)**：
  - **结构映射**：将 `messages` 数组中的 `role: system` 条目剥离，转化为 Anthropic 要求的顶层 `system: "..."` 字段。
  - **流式对齐**：处理 Anthropic 特有的 `message_start`, `content_block_delta` 等 SSE 事件，统一包装为标准的 OpenAI 兼容 SSE 格式回传给客户端。
- **DeepSeek 支持**：由于 DeepSeek 兼容 OpenAI 格式，只需在 `registry.py` 中配置正确的 `base_url` 即可。

### 2.2 凭证透传与网络安全 (Security)
- **Header 镜像**：确保 `x-api-key` (Anthropic) 和 `Authorization` (OpenAI/DeepSeek) 能够根据目标自动选择并透传。
- **HTTPS 适配**：确保异步连接池能够正确处理云端 TLS 连接及超时重试（默认 60s）。

## 3. 高保真审计与集成测试规范 (TDD)

### 3.1 跨协议翻译审计 (Translation Audit)
- **场景**：客户端发送 OpenAI 格式请求，指定模型为 `anthropic/claude-3-5-sonnet`。
- **审计展示**：Side-by-Side 展示 `StandardRequest (System Message)` -> `Anthropic Payload (System Field)`。

### 3.2 云端流式透传审计
- **验证点**：模拟云端高延迟网络下的 SSE 流式返回，验证 ClawBrain 是否能实时反向包装并保持首字延迟（TTFT）不退化。

## 4. 生成目标
- `src/gateway/translator.py`: 增加 Anthropic 翻译逻辑。
- `src/gateway/registry.py`: 更新云端提供商映射。
- `tests/test_p13_cloud_adapters.py`: 云端适配专项集成测试。
