# design/memory_neocortex.md v1.1

## 1. 任务目标 (Objective)
从零实现 **ClawBrain Neocortex (新皮层)** 引擎。该引擎负责将海马体中的冗长情节记忆异步整合为精炼的语义记忆（知识摘要），同时必须具备“可见的语义审计”能力。

## 2. 核心架构逻辑 (Architecture)

### 2.1 数据与存储模型
- **依赖配置**：`db_dir` (用于定位 `hippocampus.db`)，`ollama_url` (默认 `http://127.0.0.1:11434`)。
- **存储表结构 (`neocortex_summaries`)**：
  - `context_id` (TEXT PRIMARY KEY)
  - `summary_text` (TEXT)
  - `last_updated` (REAL)
  - `hebbian_weight` (REAL DEFAULT 1.0)
- **初始化逻辑**：必须在实例化时自动创建上述 SQLite 表。

### 2.2 语义提纯引擎 (Distillation Engine)
- **方法签名**：`async def distill(context_id: str, traces: List[Dict[str, Any]]) -> str`
- **逻辑流转**：
  1. 遍历输入的 `traces` 列表，提取所有的 User 和 Assistant 对话内容，拼接成长文本。
  2. 构造指令 Prompt："请总结以下对话中的核心技术决策、用户偏好和已解决的问题。以精炼的 Bullet Points 形式输出，严禁废话。"
  3. 使用 `httpx.AsyncClient` 调用 `ollama_url/api/generate`，指定 `gemma4:e4b`，传入合并后的 Prompt。
  4. 将返回的 `response` 提取出来，存入/更新 `neocortex_summaries` 表。
  5. 异常处理：如果请求失败，返回描述性的错误字符串，不抛出阻断异常。

### 2.3 记忆唤醒接口
- **方法签名**：`def get_summary(context_id: str) -> Optional[str]`
- 负责从 SQLite 读取当前会话最新的摘要内容。

## 3. 高保真审计与测试规范 (High-Fidelity TDD)

必须在 `tests/test_p9_neocortex.py` 中实现高度结构化的语义对比日志。

### 3.1 核心事实提纯验证 (Semantic Delta Audit)
- **测试数据**：提供包含 3 条无用沟通与 1 条核心事实（如 "Database version is 15.2" 或类似特殊参数）的复杂交互数组。
- **审计要求**：
  - **精准断言**：测试脚本不仅要判断摘要长度是否缩小，还要通过预设的一组“金丝雀事实关键词”（Canary Facts Array）去检查摘要中是否遗漏。
  - **日志展示**：在 Side-by-Side 格式中，左侧 `EXPECTED EVIDENCE` 列出**必须包含的关键事实清单**，右侧 `ACTUAL EVIDENCE` 必须输出摘要中**是否保留了该事实的打点确认（[x] or [ ]）**。

## 4. 生成目标 (Output Targets)
1. `src/memory/neocortex.py`: 新皮层逻辑与存储。
2. `tests/test_p9_neocortex.py`: 实现强壮的语义校验逻辑与高保真输出。
