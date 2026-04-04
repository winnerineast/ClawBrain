# design/memory_router.md v1.0

## 1. 任务目标 (Objective)
实现 **ClawBrain MemoryRouter (记忆路由)** 与 **CleanupManager (清理管理器)**。
作为系统的中央调度器，负责：
1. **统一摄入 (Ingestion)**：将原始 Payload 分解并分发至工作记忆与海马体。
2. **上下文检索 (Retrieval)**：综合三层记忆（活跃+摘要+召回）构造最终 Context。
3. **自动化清理 (Cleanup)**：强制执行 TTL 与容量约束。

## 2. 核心架构逻辑 (Architecture)

### 2.1 记忆路由引擎 (MemoryRouter)
- **方法 `ingest(payload: Dict)`**：
  - 调用 `SignalDecomposer` 获取意图与指纹。
  - 将 Trace 分别送入 `WorkingMemory` (实时激活) 和 `Hippocampus` (无损持久化)。
- **方法 `get_combined_context(current_focus: str)`**：
  - **L1 (Working)**：获取所有活跃消息。
  - **L3 (Neocortex)**：获取当前会话的语义摘要。
  - **L2 (Hippocampus)**：基于 `current_focus` 执行 FTS5 搜索，获取最相关的历史片段。
  - **合成规则**：Summary + Search_Hits + Active_Messages。

### 2.2 清理管理器 (CleanupManager)
- **海马体清理**：删除 7 天前的记录及关联 Blob。
- **工作记忆刷新**：每轮交互自动触发活跃度重算。

## 3. 高保真审计与测试规范 (TDD)

### 3.1 路由决策审计 (Routing Decision Audit)
- **验证点**：发送一个请求，验证其是否**同时**出现在了内存（WorkingMemory）和磁盘（Hippocampus）中。
- **日志展示**：Side-by-Side 展示 `Action: Ingest -> [L1: OK, L2: OK]`。

### 3.2 复合上下文合成审计 (Synthesis Audit)
- **验证点**：在有“历史摘要”和“活跃对话”的情况下发起检索。
- **审计展示**：左侧展示原始各层内容，右侧展示最终拼接给 LLM 的字符串，验证优先级顺序。

## 4. 生成目标
- `src/memory/router.py`: 中央调度器实现。
- `tests/test_p10_memory_router.py`: 路由与合成专项验收测试。
- `tests/data/p10_router.json`: 路由场景测试数据。
