# design/memory.md v1.8

## 1. 系统愿景 (Objective)
生成 **ClawBrain Neural Memory System**。该系统通过三层记忆架构实现交互的对称存储、异常容错、信号降噪以及大数据量冲击防御。

## 2. 核心架构与逻辑 (Architecture & Logic)

### 2.1 交互状态机 (Interaction State Machine)
- **两阶段提交模型**：
  - `PENDING` (STIMULUS_RECEIVED): 接收到 Input 时初始化。
  - `COMMITTED` (REACTION_COMPLETED): 接收到 Output 时关联并固化。
  - `ORPHAN` (INCOMPLETE_INTENT): 超过 300 秒无响应的输入。
- **原子单位**：使用 `InteractionTrace` 对象，必须成对存储 `(Stimulus, Reaction)`。

### 2.2 信号分解器 (SignalDecomposer)
- **指纹识别 (Schema Fingerprinting)**：通过对请求结构（排除消息内容）进行 MD5 Hash，识别重复的协议模板。
- **意图提取 (Core Intent)**：从 `messages` 数组中精准剥离最后一条 `role: user` 的文本内容。

### 2.3 存储与生命周期 (Layers)
- **工作记忆 (L1)**：内存 `OrderedDict`，支持基于时间常数的权重衰减。
- **海马体 (L2)**：无损 SQLite FTS5 存储。单次 > 512KB 时流式写盘。
- **新皮层 (L3)**：后台执行的语义摘要与规则泛化。

## 3. 测试与审计规范 (TDD & Audit)

### 3.1 核心验证点 (Mandatory)
- **状态流转**：验证从 `PENDING` 到 `COMMITTED` 的正确性。
- **孤儿识别**：验证超时记录被标记为 `ORPHAN`。
- **信号审计**：验证 `SignalDecomposer` 对相同结构的 Hash 一致性，以及对 User 意图提取的准确性。

### 3.2 审计日志标准
- 遵循 **Rule 3** 的 Side-by-Side 布局。
- 日志必须展示：`Raw Payload -> Fingerprint -> Extracted Intent`。

## 4. 生成目标 (Output Targets)
- `src/memory/core.py`: 状态机与引擎。
- `src/memory/signals.py`: 信号解构与指纹识别。
- `tests/test_p6_memory_resilience.py`: 覆盖状态机与信号审计的全量测试。
