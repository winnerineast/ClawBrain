# design/memory_router.md v1.8

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

## 4. 生成目标
- `src/memory/router.py`, `src/memory/storage.py`, `tests/test_p10_memory_router.py`。
