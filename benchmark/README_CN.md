# ClawBrain 基准测试：量化认知增量 (Cognitive Delta)

## 为什么要进行基准测试？

大语言模型（LLM）的记忆能力极难衡量。单元测试只能确认代码不崩溃，日志只能显示数据已保存，但它们无法回答最关键的问题：**这真的让 AI 变得更聪明了吗？**

ClawBrain 的价值由 **增量（Delta）** 定义——即与标准、无状态的 LLM 交互相比，智能体在检索事实和随时间维持上下文能力上的可衡量提升。本基准测试套件提供了证明这一价值的客观证据。

## 双层验证策略

为了同时确保技术精确性和实际应用价值，基准测试分为两个层级：

### Tier 1：基础架构完整性（直接 API 测试）
*   **方法**：直接驱动 ClawBrain 的 `/internal/*` 端点，绕过 LLM。
*   **目的**：验证 **检索与上下文预算（Context Budgeting）** 逻辑在数学上的正确性。
*   **指标**：确认正确的事实被注入到 Prompt 增强部分，且未超过 Token 预算。该测试是确定性的且运行迅速。

### Tier 2：认知有效性（真实端到端测试）
*   **方法**：驱动完整技术栈：`OpenClaw CLI` → `ClawBrain 插件` → `本地 LLM`。
*   **目的**：衡量 **端到端（End-to-End）实用性**。它不仅检查事实是否出现在 Prompt 中，还检查 LLM 是否成功解析了这些记忆并给出了正确的回答。
*   **指标**：模型回答中的实际召回率，以及在对话噪音中的健壮性。

## 认知测试维度

我们不仅测试“记忆力”，还针对智能体在生产环境中面临的特定认知失效点进行压力测试：

| 维度 | 挑战描述 |
|-----------|-----------|
| **召回距离 (Recall Distance)** | 在 100 轮以上的无关闲聊后，是否还能记住某个特定事实。 |
| **事实演进 (Fact Evolution)** | 当用户改变主意时（例如：“服务器从 5432 端口搬到了 5433”），修正记忆的能力。 |
| **噪音健壮性 (Noise Robustness)** | 在充满技术术语的“草堆”中精准提取“针”一样的关键事实。 |
| **会话隔离 (Session Isolation)** | 确保用户 A 的私有数据永远不会泄露给用户 B 的上下文（必须 100% 通过）。 |
| **多事实综合 (Multi-Fact Synthesis)** | 回答需要结合 2-5 个不同历史事实的问题。 |

## 快速开始

```bash
# 1. 从种子库生成测试用例
python3 benchmark/run_benchmark.py generate

# 2. 设置 OpenClaw 基准测试配置文件 (创建 ~/.openclaw-benchmark-on/off)
# 此命令将 'on' 配置为使用 'clawbrain' 引擎，'off' 配置为使用 'legacy' 引擎
python3 benchmark/run_benchmark.py setup-profiles

# 3. 运行 Tier 1 基准测试 (快速，需要 ClawBrain 服务已启动)
PYTHONPATH=. ./venv/bin/python3 benchmark/run_benchmark.py run --tier 1

# 4. 运行 Tier 2 基准测试 (较慢，需要安装 OpenClaw + 本地模型 gemma4:e4b)
# 使用 ~/.openclaw-benchmark-on 和 ~/.openclaw-benchmark-off 配置文件运行
PYTHONPATH=. ./venv/bin/python3 benchmark/run_benchmark.py run --tier 2

# 5. 查看最新的综合评估报告
python3 benchmark/run_benchmark.py report
```

## Tier 2 环境说明

为了确保测试环境的纯净，Tier 2 使用专门的 OpenClaw 配置文件和工作区：

- **配置文件 (Profiles)**:
  - `benchmark-on`: 位于 `~/.openclaw-benchmark-on/`，配置 `contextEngine` 为 `clawbrain`。
  - `benchmark-off`: 位于 `~/.openclaw-benchmark-off/`，使用原生的 `legacy` 引擎。
- **工作区 (Workspaces)**:
  - `benchmark-on` 使用独立的 `~/.openclaw/workspace-benchmark-on`。
  - `benchmark-off` 使用独立的 `~/.openclaw/workspace-benchmark-off`。
- **默认模型**: 基准测试默认使用 `ollama/gemma4:e4b`。请在运行前确保已在 Ollama 中拉取此模型。


---
*本基准测试是一个动态系统。随着 ClawBrain 的进化（例如引入向量嵌入 Vector Embeddings），这些指标将提供护栏，确保每一次“改进”都是真实的认知提升。*
