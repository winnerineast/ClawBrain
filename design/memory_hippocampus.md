# design/memory_hippocampus.md v1.7

## 1. 任务目标 (Objective)
从零实现 **ClawBrain Hippocampus (海马体)** 存储引擎。该引擎负责交互轨迹的无损持久化、大文件流式落盘以及基于 SQLite FTS5 的全文检索。同时，必须实现最高级别的字节级存证审计。核心改进：实现基于模型上下文窗口的动态分流阈值。

## 2. 核心架构与底层逻辑 (Architecture & Implementation Details)

### 2.1 存储目录与初始化
- 默认目录：`db_dir`，其下需创建 `blobs/` 子目录用于存放超大文件。
- 数据库文件：`db_dir/hippocampus.db`。
- **SQLite 表结构**：
  - `traces`: `trace_id` (TEXT PK), `timestamp` (REAL), `model` (TEXT), `is_blob` (INTEGER), `blob_path` (TEXT), `raw_content` (TEXT), `checksum` (TEXT)。
  - `search_idx`: FTS5 虚拟表，包含 `trace_id` (UNINDEXED) 和 `content`。

### 2.2 动态存储分流机制 (Dynamic Tiered Storage Logic)
- **入库方法 `save_trace(trace_id, payload, search_text="", threshold=None)`**：
  - 将 `payload` 序列化为 JSON 字符串，计算其字节长度。
  - **SHA-256 校验 (Fixed Bug 7)**：计算 JSON 字符串原始字节的 SHA-256 哈希值（十六进制字符串格式）。
  - **动态阈值**：不再硬编码 512KB。如果调用方提供了 `threshold` (字节数)，则使用该值作为分流判定标准；若未提供，则默认回退至 512KB。
  - **时间戳 (Fixed Bug 5)**：入库时必须使用 `time.time()` 记录真实时间。
  - **分流逻辑**：
    - **如果长度 > threshold**：将 JSON 字符串写入 `blobs/{trace_id}.json`。数据库 `is_blob` 设为 1，`blob_path` 设为绝对路径，`raw_content` 置空。
    - **如果长度 <= threshold**：数据库 `is_blob` 设为 0，`blob_path` 置空，`raw_content` 存入 JSON 字符串。
  - 将 `checksum` 存入 `traces` 表。
  - 如果 `search_text` 不为空，则插入 `search_idx` 表建立全文索引。
  - **返回契约**：必须返回字典 `{"trace_id": str, "is_blob": bool, "blob_path": str, "size": int, "checksum": str}`。

### 2.3 全文搜索安全化 (Safe Search Engine)
- **查询方法 `search(query: str) -> List[str]`**：
  - 必须对传入的 `query` 字符串使用双引号包裹 (如 `f'"{query}"'`)，防止 FTS5 解析异常。
  - 如果仍发生 `OperationalError`，需捕获并返回空列表 `[]`。

### 2.5 FTS 降级回退策略 (P15 新增)
- **背景**：精确短语匹配（整句加引号）召回率极低；用户输入自然语言时命中率接近零。
- **两级搜索策略**：
  - **Level 1 (精确短语)**：先执行 `content MATCH '"完整 query 字符串"'`。若有结果，直接返回。
  - **Level 2 (关键词 AND)**：若 Level 1 结果为空，将 query 按空格切分，过滤长度 ≤ 2 的词与包含 FTS5 特殊符号（`"*^()[]{}`）的词，对剩余关键词各自加引号后拼为 `"词1" "词2" ...`（FTS5 AND 语义），最多取前 5 个关键词执行查询。
  - Level 2 同样需要捕获 `OperationalError`，失败则返回空列表。

### 2.4 数据提取接口 (New for Priority 1 & 2)
- **方法 `get_content(trace_id: str) -> Optional[str]`**：
  - 根据 ID 查询。如果是 `is_blob`，则从物理路径读取 JSON 字符串；否则直接返回 `raw_content` 内容。
- **方法 `get_recent_traces(limit: int) -> List[Dict]`**：
  - 执行 `SELECT * FROM traces ORDER BY timestamp DESC LIMIT ?`。将结果封装为字典列表返回，用于提纯准备。

## 3. 高保真审计与测试规范 (High-Fidelity TDD)

必须在 `tests/test_p7_hippocampus.py` 中实现具有极高透明度的“对比式审计日志 (Side-by-Side)”。

### 3.1 字节级落盘无损审计 (Byte-Level Integrity)
- **测试逻辑**：生成超过指定 `threshold` 的大字典数据并调用 `save_trace`。
- **审计要求**：
  - 测试代码必须读取返回的 `blob_path` 中的物理文件内容。
  - 分别计算“原始输入 JSON 字符串”和“从磁盘读回的字符串”的 **SHA-256 Checksum**。
  - **日志展示**：在 Side-by-Side 格式中，明确打印这两个 SHA-256 值。必须肉眼可见的完全一致。

### 3.2 召回精度审计 (Search Precision)
- **测试逻辑**：在数据库中插入包含特殊符号的金丝雀事实（如 `SILVER-FOX-42`），并插入数条无关噪音数据。
- **审计要求**：
  - 执行 `search("SILVER-FOX-42")`。
  - **日志展示**：在 Side-by-Side 格式中，EXPECTED 打印预期的 `trace_id`，ACTUAL 打印实际检索返回的 ID 列表内容（不能只打印 True/False）。

### 2.6 会话隔离存储 (P18 新增)
- **背景**：`search_idx` 无 session 字段，跨会话查询会相互污染；`traces` 无 context_id，无法按会话过滤历史。
- **Schema 变更**：
  - `traces` 表新增列 `context_id TEXT DEFAULT 'default'`（兼容性迁移：`ALTER TABLE` 失败则忽略）。
  - `search_idx` 新增 `context_id UNINDEXED` 列。由于 FTS5 虚拟表不支持 `ALTER TABLE`，需检测旧 schema：若查询 `context_id` 列报 `OperationalError`，则 `DROP TABLE IF EXISTS search_idx` 后重建。
- **API 变更**：
  - `save_trace(..., context_id: str = "default")`：将 `context_id` 写入 `traces` 和 `search_idx`。
  - `search(query, context_id: str = "default")`：在 `WHERE content MATCH ? AND context_id = ?` 中过滤，两级搜索均携带此过滤条件。
  - `get_recent_traces(limit, context_id: str = None)`：若传入 `context_id` 则加 `WHERE context_id = ?` 过滤。

## 4. 生成目标 (Output Targets)
1. `src/memory/storage.py`: 严格按照上述逻辑实现 SQLite 交互，支持动态阈值。
2. `tests/test_p7_hippocampus.py`: 实现强壮的校验逻辑与高保真输出。
