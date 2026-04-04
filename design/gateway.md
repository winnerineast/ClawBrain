# design/gateway.md v1.9

## 1. 任务目标 (Objective)
[保持 v1.8 目标]

## 2. 核心架构设计约束 (Technical Constraints)
[保持 v1.8 约束]

## 3. 自动化测试与审计规范 (Updated for Precision)

### 3.1 测试数据生成
[保持 v1.8 规范]

### 3.2 审计精度 (Mandatory Upgrade)
- **逐字符精确验证 (Exact Match Assertions)**：全链路集成测试（如 `test_full_pipeline`）严禁使用 `in` 或 `not in` 等模糊包含断言。
- **验证要求**：必须预先定义完整的“理论上压缩后且注入后的字符串”，并使用 `==` 进行 100% 匹配验证。
- **边界覆盖**：必须验证内容末尾的补丁注入是否产生了多余的空格或换行。

## 4. 自动化报告 (Rule 8 & 9)
[保持 JSON 报告与关联日志路径的定义]

## 5. 生成目标 (Output Targets)
[保持原列表]
