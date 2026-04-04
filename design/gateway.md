# design/gateway.md v1.6

## 1. 任务目标 (Objective)
生成一个名为 **ClawBrain Gateway** 的异步高性能 LLM 网关。
该网关作为“外挂大脑”，负责多协议兼容、模型准入控制及上下文优化。
**核心准则：每一个实现的功能模块必须有独立的、可验证的测试用例。**

## 2. 核心架构设计 (Architecture)

### 2.1 功能模块化 (Functional Components)
1. **RequestConverter**: 统一 OpenAI/Ollama 请求格式。
2. **ModelScout & ScoutCache**: 模型评级、能力获取及 LRU 缓存。
3. **WhitespaceCompressor**: 执行非代码区域的文本压缩。
4. **SafetyEnforcer**: 针对 TIER_2 模型执行指令注入增强。
5. **AdapterRegistry & OllamaAdapter**: 协议转发、流式处理及 Chunk 合并。

## 3. 详细测试矩阵 (Testing Matrix - Mandatory)

生成的 `tests/` 目录必须包含对以下每个功能的专项测试：

### 3.1 单元测试 (Unit Tests)
- **Converter 测试** (`tests/test_converter.py`):
  - `test_openai_to_standard`: 验证 OpenAI 格式转为网关标准格式。
  - `test_ollama_to_standard`: 验证 Ollama 格式转为网关标准格式。
- **Scout & Cache 测试** (`tests/test_scout.py`):
  - `test_tier_classification`: 给定不同元数据，验证 TIER 判定是否准确（7B/14B/TOOLS等）。
  - `test_cache_ttl_and_hit`: 验证缓存生效，且在超时后能触发重新查询。
- **Compressor 测试** (`tests/test_compressor.py`):
  - `test_plain_text_compression`: 验证多余空格/换行被移除。
  - `test_code_block_protection`: 验证 \` \` \` 代码块内的空格和缩进被完整保留（严禁误杀）。
- **Enforcer 测试** (`tests/test_enforcer.py`):
  - `test_prompt_injection_tier2`: 验证 TIER_2 模型请求中确实被注入了格式补丁。
  - `test_bypass_tier1`: 验证 TIER_1 模型请求未被注入多余指令。

### 3.2 集成与边缘测试 (Integration & Edge Cases)
- **网关全链路测试** (`tests/test_gateway_flow.py`):
  - `test_full_streaming_chat`: 模拟一次完整的流式对话转发，验证数据流完整性。
  - `test_tool_calling_passthrough`: 验证带有 `tools` 字段的请求全过程是否正常。
  - `test_denylist_interception`: 验证 TIER_3 模型包含 `tools` 时网关返回 422。
  - `test_backend_502_error`: 模拟后端崩溃，网关应返回 502。
  - `test_timeout_504_error`: 模拟 300s 以上未响应，网关应返回 504。

## 4. 自动化报告 (Reporting)
- 每次测试运行必须生成 `results/test_report.nisi` (JSON 格式)。
- 报告必须包含：`module_name`, `test_case`, `status`, `execution_time`, `input_snapshot`。

## 5. 代码合规性 (Compliance)
- **首行标记**：`# Generated from design/gateway.md v1.6`。
- **环境变量**：`REAL_OLLAMA_URL`, `GATEWAY_PORT`, `MAX_CONTEXT_WINDOW` (默认 65536)。

## 6. 生成目标 (Output Targets)
1. `src/main.py`: FastAPI 主逻辑。
2. `src/models.py`: Pydantic 数据结构。
3. `src/scout.py`, `src/pipeline.py`, `src/converter.py`: 功能模块。
4. `src/adapters/`: 协议适配器。
5. `tests/`: 包含上述所有专项测试文件。
