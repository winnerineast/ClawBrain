# design/memory_working.md v1.3

## 1. 任务目标 (Objective)
从零实现 **ClawBrain WorkingMemory (工作记忆)**。必须实现具备“双因子动力学”的消息驻留模型，并在审计日志中完整披露计算公式与分值来源，确保注意力的聚焦与衰减逻辑 100% 可审计。

## 2. 核心架构逻辑 (Full Specifications)

### 2.1 数据结构
- **WorkingMemoryItem**: 包含 `trace_id`, `content`, `timestamp`, 以及实时 `activation`。
- **管理器约束**:
  - `MAX_CAPACITY`: 严格限制为 15 条记录。
  - `THRESHOLD`: 淘汰分界线为 0.3。
  - `DECAY_LAMBDA`: 时间衰减常数 0.001。

### 2.2 双因子数学模型 (The Mathematical Engine)
每一条消息的活跃度 $A$ 计算如下：
$$A = \text{TimeScore} + \text{RelevanceScore}$$
1. **TimeScore** (Max 0.7): $0.7 \times \exp(-0.001 \times \Delta t)$。
2. **RelevanceScore** (Max 0.3): $0.3 \times (\text{Common\_Words\_Count} / \text{Current\_Input\_Words\_Count})$。

### 2.3 动态清理逻辑
每次添加新消息后，必须执行：
1. **刷新**：重新计算内存中所有 Item 的激活值。
2. **阈值清理**：移除 $A < 0.3$ 的 Item。
3. **容量挤出**：若记录数 > 15，按 $A$ 从高到低排序，保留前 15 名。

## 3. 高保真审计与数学透明度规范 (High-Fidelity TDD)

测试脚本必须输出 **“带计算推导过程”** 的 Side-by-Side 日志。

### 3.1 时间衰减全记录 (Time Decay Trace)
- **要求**：打印 $\Delta t$ 及其带入公式后的中间值。
- **日志示例**：`T_diff: 1000s | Calc: 0.7 * exp(-0.001*1000) = 0.2575`。

### 3.2 话题唤醒明细 (Relevance Breakdown)
- **要求**：展示关键词匹配的详细证据。
- **日志示例**：`Match: {'database'} | Count: 1 | Focus_Len: 5 | Rel_Score: 0.3 * (1/5) = 0.06`。

### 3.3 状态对比展示 (Rule 8)
- 必须展示每一轮请求后，工作记忆中残留消息的 ID 列表及其对应的激活值。

## 4. 生成目标 (Output Targets)
1. `src/memory/working.py`: 支持计算过程返回的工作记忆逻辑。
2. `tests/test_p8_working_memory.py`: 高透明度验收测试。
