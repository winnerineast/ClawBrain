# design/memory_router.md v1.10

## 1. 任务目标 (Objective)
实现 **ClawBrain MemoryRouter (记忆路由)**。作为大脑中枢，平衡“即时注意力”与“长程语义整合”。引入基于 Context 预算的动态分流与自适应提纯机制。

## 2. 核心架构逻辑 (Architecture)

### 2.1 依赖注入与整合周期 (Consolidation Epoch)
- **参数 `distill_threshold`**：定义为“语义整合周期”。
  - **物理意义**：它代表了从“情节”转向“知识”的临界点。
  - **推荐算法**：应设为 $ModelContext / AverageTraceSize$ 的 0.8 倍。对于 64k 窗口，默认 50 轮是一个平衡了“计算成本”与“记忆精度”的经验值。
- **参数 `db_dir`**：强制透传至存储层。

### 2.2 动态分流逻辑 (Dynamic Offloading)
- **方法 `ingest(payload, offload_threshold)`**：
  - **offload_threshold**：由网关根据当前 **模型实际上下文窗口** 动态传入。
  - **逻辑**：若单次输入超过该模型窗口的 10%（或自定义比例），强制执行磁盘分流，严禁挤占有限的推理空间。

### 2.3 复合上下文合成 (Retrieval - Fixed Bug 2)
- **方法 `get_combined_context(current_focus: str)`**：
  - **L3 (新皮层)**：获取语义摘要。
  - **L2 (海马体 - Fixed)**：通过 FTS5 获取 ID 列表，随后必须调用 `hippo.get_content(id)` **检索真实对话原文**。严禁向模型注入 UUID 列表。
  - **L1 (工作记忆)**：获取活跃消息。
  - **合成优先级**：Summary -> Content_Recall -> Active_Messages。

### 2.4 自适应提纯 (Auto-Distillation - Fixed Bug 1)
- 每次 `ingest` 成功后，计数器累加。
- 达到 `distill_threshold` 时，触发后台 `_auto_distill_worker`。
- **Worker 逻辑 (Fixed Structure)**：
  1. 调用 `hippo.get_recent_traces(limit=distill_threshold)` 获取原始数据库行。
  2. **数据转换 (Critical)**：遍历数据库行，将 `raw_content` 字符串解析为 JSON 字典。
  3. 将解析后的 `{stimulus, reaction}` 结构列表传给 `Neocortex.distill()`。
  4. 执行完毕后重置计数器并释放锁。

### 2.5 架构归一化 (Unification)
- **唯一中枢**：`MemoryRouter` 为系统唯一的记忆协调者。废弃并移除旧版的 `MemoryEngine` 逻辑。
- **职责范围**：涵盖信号分解（Decomposer）、即时缓存（WorkingMemory）、长程归档（Hippocampus）与异步提纯（Neocortex）。

## 3. 高保真审计规范 (TDD)

### 3.1 神经韧性审计 (Memory Resilience Audit)
- **要求**：必须验证 `SignalDecomposer` 对异构 Payload 的指纹提取一致性。
- **摄入闭环验证**：测试必须验证 `MemoryRouter.ingest` 能够同时触发 L1（激活）与 L2（落盘）动作。

### 3.2 认知负荷触发审计 (Cognitive Load Audit)
- **验证点**：通过设置极低的 `distill_threshold`（如 3），验证系统是否在认知饱和时自动启动提纯。
- **日志展示**：`[MEMORY_DYNAMIC] Cognitive Load Reached -> Triggering Consolidation Epoch.`

### 3.2 动态分流精准度审计
- **验证点**：传入 1MB 数据，并设置 `offload_threshold=500KB`，验证分流 100% 触发。

### 2.6 Context 注入预算控制 (P15 新增)
- **背景**：`get_combined_context` 无上限，长期运行后注入内容可能超出模型窗口，挤占有效对话空间。
- **环境变量 `CLAWBRAIN_MAX_CONTEXT_CHARS`**：默认 `2000`，控制注入给 LLM 的总记忆字符数上限。
- **优先级贪心分配策略**：按价值密度从高到低依次占用预算，不设固定比例。
  1. **L3 新皮层摘要优先**：先将 Neocortex summary 全量注入；若超出总预算则截断并追加 `...`。
  2. **L2 海马体次之**：用剩余预算按召回顺序逐条追加，某条内容超出剩余空间则停止。
  3. **L1 工作记忆最后**：用剩余预算注入活跃消息，超出则截断。
- **日志埋点**：`[CTX_BUDGET] Budget: N | Used(L3): N | Used(L2): N | Used(L1): N`。

### 2.7 工作记忆会话隔离 (P18 新增)
- **背景**：`WorkingMemory` 是全局单例，所有 session 共享同一注意力队列，A 会话的记忆会污染 B 会话的上下文。
- **修复方案**：`MemoryRouter` 将 `self.wm: WorkingMemory` 改为 `self._wm_sessions: Dict[str, WorkingMemory] = {}`，通过 `_get_wm(context_id)` 按需创建并缓存每个 session 的 WM 实例。
- **`ingest` 签名变更**：新增 `context_id: str = "default"` 参数，用于正确路由至对应 WM 实例，并传递给 `hippo.save_trace`。
- **`_hydrate` 变更**：启动时从 `traces` 表查询 `DISTINCT context_id`，对每个 session 分别调用 `hippo.get_recent_traces(limit=15, context_id=session)` 恢复对应 WM。
- **`get_combined_context` 变更**：调用 `_get_wm(context_id).get_active_contents()` 和 `hippo.search(query, context_id=context_id)`，确保全路径按 session 隔离。

## 4. 生成目标
- `src/memory/router.py`, `src/memory/storage.py`, `tests/test_p10_memory_router.py`。
