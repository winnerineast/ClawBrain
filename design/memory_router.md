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

### 2.3 自适应提纯 (Auto-Distillation)
- 每次 `ingest` 成功后，计数器累加。
- 达到 `distill_threshold` 时，判定为“认知负荷达标”，触发后台 `Neocortex.distill()` 任务，将最近一个周期的碎片信息固化为语义事实。

## 3. 高保真审计规范 (TDD)

### 3.1 认知负荷触发审计 (Cognitive Load Audit)
- **验证点**：通过设置极低的 `distill_threshold`（如 3），验证系统是否在认知饱和时自动启动提纯。
- **日志展示**：`[MEMORY_DYNAMIC] Cognitive Load Reached -> Triggering Consolidation Epoch.`

### 3.2 动态分流精准度审计
- **验证点**：传入 1MB 数据，并设置 `offload_threshold=500KB`，验证分流 100% 触发。

## 4. 生成目标
- `src/memory/router.py`, `src/memory/storage.py`, `tests/test_p10_memory_router.py`。
