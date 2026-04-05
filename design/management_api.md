# design/management_api.md v1.0

## 1. 任务目标 (Objective)
为 ClawBrain 增加三条**记忆管理端点**，允许外部工具查询、清空、手动触发特定 session 的记忆，解决当前记忆状态完全不可观测的问题。

## 2. 核心架构逻辑 (Architecture)

### 2.1 端点定义

#### GET `/v1/memory/{session_id}`
查询指定 session 的当前记忆状态。
- 返回 JSON：
  ```json
  {
    "session_id": "xxx",
    "neocortex_summary": "...",
    "working_memory_count": 5,
    "working_memory_preview": ["最近意图1", "最近意图2", "最近意图3"]
  }
  ```
- `neocortex_summary` 为 `None` 时返回 `null`。

#### DELETE `/v1/memory/{session_id}`
清除指定 session 的新皮层摘要（Neocortex summary）。
- 调用 `Neocortex.clear_summary(session_id)`。
- 返回：`{"status": "cleared", "session_id": "xxx"}`

#### POST `/v1/memory/{session_id}/distill`
手动触发指定 session 的异步提纯任务。
- 通过 `asyncio.create_task` 调用 `MemoryRouter._auto_distill_worker(session_id)`。
- 立即返回（不等待 LLM 完成）：`{"status": "distillation_triggered", "session_id": "xxx"}`

### 2.2 Neocortex 新增方法
- **`clear_summary(context_id: str)`**：执行 `DELETE FROM neocortex_summaries WHERE context_id = ?`。

## 3. 高保真审计与测试规范 (TDD)

### 3.1 GET 端点验证
- 先 ingest 若干记录，调用 GET，断言返回结构完整、`working_memory_count` 与实际一致。

### 3.2 DELETE 端点验证
- 先手动调用 `neo._save_summary` 写入数据，再调用 DELETE 端点，再调用 GET，断言 `neocortex_summary` 为 null。

### 3.3 POST 触发验证
- 调用 POST 端点，断言返回 200 且 `status == "distillation_triggered"`。

## 4. 生成目标
- `src/main.py`: 增加三条管理路由。
- `src/memory/neocortex.py`: 增加 `clear_summary` 方法。
- `tests/test_p17_management.py`: 三端点验收测试。
