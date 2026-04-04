# design/gateway.md v1.19

## 1. 任务目标 (Objective)
强化多轮对话测试的透明度。实现“对话流分解审计”，确保长上下文链路的每一环都可见、可查。

## 2. 核心架构设计
[保持 v1.18 逻辑]

## 3. 对话流分解审计规范 (Marathon Breakdown Standard)

### 3.1 轮次索引展示 (Round Indexing)
多轮对话测试（如 Phase 5 Marathon）的审计日志必须包含以下 Breakdown 列表：
- 打印发送给网关的总轮数。
- 抽样展示：打印第 1 轮、第 10 轮、第 20 轮的 User Content 摘要，以证明上下文完整性。

### 3.2 跨轮次召回验证 (Cross-Round Recall)
- **EXPECTED**: 明确指出模型需要从哪一轮（例如 Round 1 或 Round 5）召回特定知识点。
- **ACTUAL**: 展示模型回复中包含该知识点的证据。

## 4. 生成目标
- 仅重构 `tests/test_p5_e2e.py` 的审计输出逻辑。
