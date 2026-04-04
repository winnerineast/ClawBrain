# design/memory_hippocampus.md v1.2

## 1. 任务目标 (Objective)
从零实现 **ClawBrain Hippocampus (海马体)** 存储引擎。该引擎负责交互轨迹的无损持久化、大文件流式落盘以及基于 SQLite FTS5 的全文检索。同时，必须实现最高级别的字节级存证审计。

## 2. 核心架构与底层逻辑 (Architecture & Implementation Details)

### 2.1 存储目录与初始化
- 默认目录：`db_dir`，其下需创建 `blobs/` 子目录用于存放超大文件。
- 数据库文件：`db_dir/hippocampus.db`。
- **SQLite 表结构**：
  - `traces`: `trace_id` (TEXT PK), `timestamp` (REAL), `model` (TEXT), `is_blob` (INTEGER), `blob_path` (TEXT), `raw_content` (TEXT)。
  - `search_idx`: FTS5 虚拟表，包含 `trace_id` (UNINDEXED) 和 `content`。

### 2.2 存储分流机制 (Tiered Storage Logic)
- **BLOB_THRESHOLD**：硬编码为 512KB (`512 * 1024` 字节)。
- **入库方法 `save_trace(trace_id, payload, search_text="")`**：
  - 将 `payload` 序列化为 JSON 字符串，计算其字节长度。
  - **如果长度 > THRESHOLD**：将 JSON 字符串写入 `blobs/{trace_id}.json`。数据库 `is_blob` 设为 1，`blob_path` 设为绝对路径，`raw_content` 置空。
  - **如果长度 <= THRESHOLD**：数据库 `is_blob` 设为 0，`blob_path` 置空，`raw_content` 存入 JSON 字符串。
  - 如果 `search_text` 不为空，则插入 `search_idx` 表建立全文索引。
  - **返回契约 (Return Contract)**：必须返回字典 `{"trace_id": str, "is_blob": bool, "blob_path": str, "size": int}`。

### 2.3 全文搜索安全化 (Safe Search Engine)
- **查询方法 `search(query: str) -> List[str]`**：
  - 必须对传入的 `query` 字符串使用双引号包裹 (如 `f'"{query}"'`)，防止 FTS5 在解析包含连字符 `-` 或特殊符号的词语时抛出 `sqlite3.OperationalError: no such column`。
  - 如果仍发生 `OperationalError`，需捕获并返回空列表 `[]`。

## 3. 高保真审计与测试规范 (High-Fidelity TDD)

必须在 `tests/test_p7_hippocampus.py` 中实现具有极高透明度的“对比式审计日志 (Side-by-Side)”。

### 3.1 字节级落盘无损审计 (Byte-Level Integrity)
- **测试逻辑**：生成 1MB 的大字典数据并调用 `save_trace`。
- **审计要求**：
  - 测试代码必须读取返回的 `blob_path` 中的物理文件内容。
  - 分别计算“原始输入 JSON 字符串”和“从磁盘读回的字符串”的 **SHA-256 Checksum**。
  - **日志展示**：在 Side-by-Side 格式中，明确打印这两个 SHA-256 值。必须肉眼可见的完全一致。

### 3.2 召回精度审计 (Search Precision)
- **测试逻辑**：在数据库中插入包含特殊符号的金丝雀事实（如 `SILVER-FOX-42`），并插入数条无关噪音数据。
- **审计要求**：
  - 执行 `search("SILVER-FOX-42")`。
  - **日志展示**：在 Side-by-Side 格式中，EXPECTED 打印预期的 `trace_id`，ACTUAL 打印实际检索返回的 ID 列表内容（不能只打印 True/False）。

## 4. 生成目标 (Output Targets)
1. `src/memory/storage.py`: 严格按照上述逻辑实现 SQLite 交互。
2. `tests/test_p7_hippocampus.py`: 实现强壮的校验逻辑与高保真输出。
