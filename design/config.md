# design/config.md v1.0

## 1. 任务目标 (Objective)
实现 ClawBrain 提供商注册表的**热加载**能力。目前 `ProviderRegistry` 和本地模型白名单完全硬编码，新增模型或提供商须修改源码并重启。本模块通过环境变量实现零改码扩展。

## 2. 核心架构逻辑 (Architecture)

### 2.1 扩展提供商注册（环境变量注入）
- **环境变量 `CLAWBRAIN_EXTRA_PROVIDERS`**：JSON 字符串，格式：
  ```json
  {"together": {"base_url": "https://api.together.xyz", "protocol": "openai"}}
  ```
  启动时由 `ProviderRegistry.__init__` 解析并合并进 `self.providers`。解析失败静默跳过（记 WARNING 日志）。

### 2.2 本地模型白名单扩展（环境变量注入）
- **环境变量 `CLAWBRAIN_LOCAL_MODELS`**：JSON 字符串，格式：
  ```json
  {"llama3:8b": "ollama", "mistral:7b": "ollama"}
  ```
  启动时合并进 `self.known_no_prefix_models`。解析失败静默跳过。

### 2.3 Session 隔离警告
- 当请求未携带 `x-clawbrain-session` Header，`context_id` 回退为 `"default"` 时，网关必须打印：
  `[SESSION] No session header — using 'default'. Set 'x-clawbrain-session' for isolation.`
- 这是警告日志，不阻断请求。

## 3. 高保真审计与测试规范 (TDD)

### 3.1 环境变量注入验证
- 通过 `os.environ` 注入 `CLAWBRAIN_EXTRA_PROVIDERS` 和 `CLAWBRAIN_LOCAL_MODELS`，实例化 `ProviderRegistry`，断言新提供商和新模型均可被 `resolve_provider` 正确路由。

### 3.2 非法 JSON 容错
- 注入格式错误的 JSON 字符串，验证系统正常启动，仅打印 WARNING，不抛出异常。

## 4. 生成目标
- `src/gateway/registry.py`: 增加启动时环境变量解析逻辑。
- `src/main.py`: 增加 session 隔离警告日志。
- `tests/test_p16_config.py`: 环境变量注入与容错验证。
