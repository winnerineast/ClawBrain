# design/memory_working.md v1.2

## 1. 任务目标 (Objective)
从零实现 **ClawBrain WorkingMemory (工作记忆)**。核心逻辑：基于时间远离度 (Temporal Decay) 与话题相关度 (Thematic Relevance) 动态计算消息的驻留权重，模拟人类注意力的聚焦机制。同时，必须实现高保真时间线审计。

## 2. 核心架构逻辑 (Architecture)

### 2.1 结构模型
- **WorkingMemoryItem**:
  - `trace_id` (str): 唯一交互 ID。
  - `content` (str): 消息内容。
  - `timestamp` (float): 入库时间。
  - `activation` (float): 初始值为 1.0。
- **WorkingMemory 管理器**:
  - `THRESHOLD`: 默认 0.3（淘汰阈值）。
  - `MAX_CAPACITY`: 默认 15 条。
  - `DECAY_LAMBDA`: 时间衰减常数，如 0.001。

### 2.2 动力学算法 (Dual-Factor Activation)
- 每次 `_refresh_activations(current_focus: str)` 时，重新计算内存中所有 Item 的激活值 $A$：
  - **TimeScore**: $0.7 \times \exp(-\lambda \times \Delta t)$，其中 $\Delta t$ 是当前时间与消息入库时间的差值。
  - **RelevanceScore**: 计算 `item.content` 与 `current_focus` 的简单词频覆盖率 (Intersection / Length of Current Words)，最大权重 0.3。
  - $A = TimeScore + RelevanceScore$

### 2.3 驻留策略 (Eviction)
- 每次刷新后执行 `_cleanup()`：
  - 第一步：移除 $A < 0.3$ 的所有记录。
  - 第二步：如果剩余记录数超过 `MAX_CAPACITY`，按 $A$ 降序排列，仅保留前 `MAX_CAPACITY` 条，其余丢弃。

## 3. 高保真审计与测试规范 (High-Fidelity TDD)

必须在 `tests/test_p8_working_memory.py` 中实现高透明度的对比式审计日志。

### 3.1 衰减时间线审计 (Decay Timeline Audit)
- **测试逻辑**：模拟一个记忆节点在 $T_0, T_{1000}$ 的激活值变化。
- **审计要求**：
  - **日志展示**：在 Side-by-Side 格式中，明确打印 `T_0 Activation` 和 `T_1000 Activation` 的浮点数值，必须证明其发生了显著的数值衰减。

### 3.2 语义唤醒审计 (Relevance Awakening Audit)
- **测试逻辑**：
  - 存入关于 "Database" 的记录，时间拨退 2000 秒。
  - 第一次刷新输入无关词 "Weather"，记录激活值 $A_1$。
  - 第二次刷新输入相关词 "Database"，记录激活值 $A_2$。
- **审计要求**：
  - **日志展示**：明确打印 $A_1$（未唤醒）和 $A_2$（被唤醒）的数值对比，必须在日志中体现 $A_2 > A_1$。

## 4. 生成目标 (Output Targets)
1. `src/memory/working.py`: 工作记忆逻辑实现。
2. `tests/test_p8_working_memory.py`: 实现强壮的校验逻辑与高保真输出。
