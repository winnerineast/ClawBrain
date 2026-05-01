# ClawBrain 基准测试：量化认知增量 (Cognitive Delta)

[English](./README.md)

## 为什么进行基准测试？

LLM 记忆极难衡量。单元测试可以确认代码不崩溃，日志可以显示数据已保存，但它们无法回答最关键的问题：**这真的让 AI 变得更聪明了吗？**

ClawBrain 的价值由 **Delta (增量)** 定义——即与标准的无状态 LLM 交互相比，智能体在一段时间内召回事实和维持上下文的能力是否有可衡量的提升。本基准测试套件提供了证明这一价值所需的客观证据。

## 两层验证策略

为了确保技术精确性和实际效用，基准测试分为两层：

### 第 1 层：基础设施完整性 (直接 API)
*   **方法**：直接驱动 ClawBrain 的 `/internal/*` 接口，绕过 LLM。
*   **目的**：验证 **检索和上下文预算** 逻辑的数学正确性。
*   **指标**：验证正确的事实是否被注入到提示词中，且不超过 Token 预算。这是确定性的且速度很快。

### 第 2 层：认知有效性 (真实端到端)
*   **方法**：驱动完整堆栈：`OpenClaw CLI` → `ClawBrain 插件` → `本地 LLM`。
*   **目的**：衡量 **端到端效用**。它不仅检查事实是否在提示词中，还检查 LLM 是否成功解析了该记忆并提供了正确的答案。
*   **指标**：模型响应中的实际召回率以及对对话噪音的鲁棒性。

## 认知维度

我们不只是测试“记忆”；我们压力测试智能体在生产中面临的具体认知失败点：

| 维度 | 挑战 |
|-----------|-----------|
| **召回距离 (Recall Distance)** | 在 100 轮以上的无关闲聊后记住一个特定事实。 |
| **事实演进 (Fact Evolution)** | 当用户改变主意时纠正记忆（例如，“服务器从端口 5432 移动到了 5433”）。 |
| **噪音鲁棒性 (Noise Robustness)** | 从技术术语的“草谈”中提取出“针”一样的事实。 |
| **会话隔离 (Session Isolation)** | 确保用户 A 的私有数据永远不会泄露到用户 B 的上下文中（要求 100% 通过）。 |
| **多事实综合 (Multi-Fact Synthesis)** | 回回答需要结合 2-5 个不同历史事实的问题。 |
| **弃权控制 (Abstention) (v1.1)** | **幻觉控制**：衡量智能体对未植入的事实说“我不知道”的能力。 |
| **别名解析 (Alias Resolution) (v1.1)** | **个性化引用**：将昵称（“建筑师”）映射回正式系统事实。 |
| **时序冲突 (Chronicle Conflict) (v1.1)** | **时序推理**：通过优先处理最近的日期/版本来解决冲突事实。 |

## 环境设置与故障排除

### 1. 必备条件
- **Ollama**：必须运行，用于 **认知评审 (Cognitive Judge)** 和 **主题检测** 功能。
  ```bash
  ollama serve
  ollama pull gemma4:e4b
  ```
- **虚拟环境**：所有命令必须使用项目的 `venv`。

### 2. 运行服务器
基准测试运行器连接到一个正在运行的 ClawBrain 实例。在单独的终端中启动它：
```bash
# 在 ClawBrain 根目录下
source venv/bin/activate
export CLAWBRAIN_URL=http://127.0.0.1:11435
python3 -m uvicorn src.main:app --host 127.0.0.1 --port 11435
```

### 3. 排除 "Internal Server Error" 故障
如果在高吞吐量测试期间在服务器日志中遇到 `Internal error: Error finding id`：
- **原因**：这表示 ChromaDB HNSW 索引与底层存储之间存在异步脱节。
- **解决方案**：系统现在包含 **Phase 65 平滑回退机制**，如果检测到索引延迟，会自动切换到元数据扫描。无需手动操作，尽管在索引稳定之前，结果可能会显示较低的“认知增量”。
- **手动重置**：要从 100% 干净的状态开始：
  ```bash
  pkill -9 -f uvicorn
  rm -rf data/chroma/
  ```

## 快速启动

```bash
# 1. 从种子库生成测试用例
python3 benchmark/run_benchmark.py generate

# 2. 设置 OpenClaw 配置文件 (创建 ~/.openclaw-benchmark-on/off)
python3 benchmark/run_benchmark.py setup-profiles

# 3. 运行第 1 层测试 (快速，需要运行 ClawBrain 服务器)
export CLAWBRAIN_URL=http://127.0.0.1:11435
python3 benchmark/run_benchmark.py run --tier 1

# 4. 运行第 2 层测试 (较慢，需要 OpenClaw + 本地模型 gemma4:e4b)
python3 benchmark/run_benchmark.py run --tier 2

# 5. 查看最新的综合报告
python3 benchmark/run_benchmark.py report
```

---
*根据 design/benchmark.md v1.2 / Phase 65 更新生成。*
