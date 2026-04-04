# design/gateway.md v1.8

## 1. 任务目标 (Objective)
生成名为 **ClawBrain Gateway** 的 LLM 网关。重点解决：长文本压缩与代码块缩进保护的冲突。

## 2. 核心架构设计约束 (Technical Constraints)

### 2.1 WhitespaceCompressor 实现准则
- **核心逻辑**：必须先使用非贪婪正则 `(```[\s\S]*?```)` 将文本切分为“代码块”和“非代码块”。
- **保护机制**：对于命中代码块模式的片段，禁止执行任何空格压缩操作。
- **压缩标准**：仅对非代码块区域执行：2+ 空格变为 1，3+ 换行变为 2。

### 2.2 ModelScout & SafetyEnforcer
- **判定逻辑**：维持 7B/14B TIER 判定。
- **幂等性要求**：SafetyEnforcer 在注入 Patch 前必须检查是否已存在，防止多轮对话重复注入。

## 3. 自动化测试与审计规范 (Updated)

### 3.1 测试数据生成 (Mandatory)
- **禁止手动拼接 JSON 字符串**：生成测试数据脚本时，必须使用 Python 的 `json.dump` 确保 Wiki 等复杂长文本的转义字符被正确处理。

### 3.2 审计精度 (Mandatory)
- **代码块验证**：必须包含针对“多层缩进（4空格及以上）”的精确匹配 Assert。
- **Wiki 长文本验证**：验证压缩后的文本长度减少量，并确认无非法转义引发的解析错误。

## 4. 自动化报告 (Rule 8 & 9)
[保持 JSON 报告与关联日志路径的定义]

## 5. 生成目标 (Output Targets)
[保持原列表：src/main.py, src/models.py, src/scout.py, src/pipeline.py, tests/...]
