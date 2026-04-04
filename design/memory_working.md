# design/memory_working.md v1.1

## 1. 任务目标 (Objective)
实现 **ClawBrain WorkingMemory (工作记忆)**。
核心逻辑：基于 **时间远离程度 (Temporal Distance)** 与 **话题相关程度 (Thematic Relevance)** 动态计算消息的驻留权重，模拟人类大脑的注意力聚焦机制。

## 2. 核心架构逻辑 (Architecture)

### 2.1 双驱动激活模型 (Dual-Factor Activation)
每一条进入工作记忆的消息都拥有一个实时激活值 $A$，计算公式如下：
$$A = (W_{time} \times \text{Decay}(\Delta t)) + (W_{rel} \times \text{Similarity}(\text{CurrentInput}, \text{PastMsg}))$$

- **因子 1：时间远离度 (Temporal Proximity)**：
  - 使用指数衰减：$e^{-\lambda \Delta t}$。
  - 逻辑：离当前时刻越远，该因子的贡献度越低。
- **因子 2：话题相关度 (Thematic Relevance)**：
  - 逻辑：通过关键词重合度或指纹关联计算。
  - 效果：即便消息在时间上很远，只要它与当前用户正在讨论的话题高度相关，其激活值会被显著“唤醒” (Re-activation)。

### 2.2 驻留与淘汰策略 (Eviction Policy)
- **动态长度**：工作记忆不再固定长度，而是保留所有激活值 $A \ge \text{Threshold}$ (默认 0.3) 的消息。
- **强制约束**：若所有消息均处于高活跃状态，保留上限仍受限于 15 条记录，优先淘汰 $A$ 值最低的。

## 3. 自动化测试与审计规范 (TDD)

### 3.1 精准审计场景
- **时间衰减验证**：存入消息后模拟时间流逝，验证其激活值随 $\Delta t$ 线性/指数下降。
- **相关性唤醒验证**：
  1. 存入关于“PostgreSQL”的消息。
  2. 模拟经过 30 分钟（时间分值变低）。
  3. 输入关于“SQL 性能”的新消息。
  4. **审计要求**：验证旧的 PostgreSQL 消息激活值是否因相关性而回升。
- **噪音沉底验证**：存入一条无关的垃圾信息，验证它在下一轮请求中因时间远离且无相关性而被快速移除。

### 3.2 审计日志标准 (Rule 8)
- 日志必须展示：`Msg_ID -> [Time_Score | Rel_Score] -> Total_Activation -> Action: [Keep|Evict]`。

## 4. 生成目标
- `src/memory/working.py`: 工作记忆逻辑实现。
- `tests/test_p8_working_memory.py`: 双维度动力学专项审计测试。
