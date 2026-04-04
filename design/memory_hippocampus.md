# design/memory_hippocampus.md v1.1

## 1. 任务目标 (Objective)
实现 **ClawBrain Hippocampus (海马体)** 存储引擎。支持大文件分流、全文检索及异常容错。

## 2. 核心架构逻辑 (Architecture)

### 2.1 存储返回契约 (Return Contract)
- `save_trace()` 必须返回一个包含以下字段的完整字典：
  - `trace_id`: 交互 ID。
  - `is_blob`: 布尔值，是否溢出到磁盘。
  - `blob_path`: 如果 `is_blob` 为 True，返回物理文件路径；否则为空字符串。
  - `size`: 原始数据字节数。

### 2.2 全文搜索安全化 (Search Sanitization)
- **风险**：SQLite FTS5 对特殊字符（如 `-`）极其敏感。
- **强制逻辑**：搜索执行前必须对查询词进行转义处理（建议对查询词加双引号包装），防止 SQL 注入及语法解析错误（如 `no such column`）。

## 3. 测试与审计规范 (TDD)
- **全量字段校验**：验证 `save_trace` 返回的所有 4 个契约字段。
- **复杂关键词搜索**：测试包含连字符、空格等特殊符号的搜索请求。

## 4. 生成目标
- `src/memory/storage.py`, `tests/test_p7_hippocampus.py`。
