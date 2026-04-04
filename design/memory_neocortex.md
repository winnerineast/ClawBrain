# design/memory_neocortex.md v1.0

## 1. 任务目标 (Objective)
实现 **ClawBrain Neocortex (新皮层)**。负责将海马体 (L2) 中的情节记忆进行慢速整合，提炼为语义级别的“知识事实清单 (Knowledge Bullet Points)”，以节省上下文空间并提升长程逻辑一致性。

## 2. 核心架构逻辑 (Architecture)

### 2.1 触发机制 (Activation Triggers)
- **容量触发**：当 `WorkingMemory` 发生溢出（> 15 条记录）时。
- **时间触发**：每隔 6 小时自动扫描海马体中的新 Trace。

### 2.2 泛化算法 (Semantic Distillation)
- **输入**：选取海马体中最近的 N 条 `InteractionTrace`。
- **动作**：调用一个轻量级 LLM 请求（通过本地适配器转发），执行以下指令：
  > "请总结以下对话中的核心技术决策、用户偏好和已解决的问题。以精炼的 Bullet Points 形式输出。"
- **输出**：更新 `NeocortexStore` 中的语义摘要。

### 2.3 存储实现
- **Neocortex 表 (SQLite)**：
  - `context_id`: 关联会话。
  - `summary_text`: 凝练后的语义内容。
  - `hebbian_weight`: 活跃权重（被引用次数越多，权重越高）。

## 3. 测试与审计规范 (TDD)

### 3.1 语义提纯测试 (Distillation Audit)
- **输入**：20 轮关于“FastAPI 配置”的杂乱对话。
- **验证**：调用 `Neocortex.distill()` 后，输出应包含关键词 "FastAPI" 且字符长度减少 80% 以上。
- **金丝雀召回**：验证压缩后的摘要是否保留了第 5 轮中埋入的特殊版本号。

### 3.2 审计日志标准 (Rule 8)
- 日志必须展示：`Action: Distill -> Raw_Tokens: <val> -> Summarized_Tokens: <val> -> Compression_Ratio: <%>`。

## 4. 生成目标
- `src/memory/neocortex.py`: 语义提取逻辑。
- `tests/test_p9_neocortex.py`: 摘要精度与召回审计测试。
