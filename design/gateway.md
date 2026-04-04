# design/gateway.md v1.7

## 1. 任务目标 (Objective)
生成一个名为 **ClawBrain Gateway** 的异步高性能 LLM 网关。
该网关作为“外挂大脑”，负责多协议兼容、模型准入控制及上下文优化。

## 2. 核心架构设计 (Architecture)
[保持 v1.6 的模块化设计：Converter, Scout, Compressor, Enforcer, Adapter]

## 3. 详细测试矩阵 (Testing Matrix)
[保持 v1.6 的全量功能覆盖测试点]

## 4. 自动化报告与审计证据 (Reporting & Audit)
根据 GEMINI.md 准则 8，每次测试运行必须产出两个关联文件：

### 4.1 JSON 报告 (`results/test_report.json`)
结构如下：
```json
[
  {
    "test_id": "...",
    "status": "PASS|FAIL",
    "module": "...",
    "latency_ms": 123,
    "evidence_log": "results/test_report.log"
  }
]
```

### 4.2 审计日志 (`results/test_report.log`)
该文件必须包含：
- 测试数据的完整 Snapshot。
- 每一个 Assert 动作前后的实际输出数据。
- 模拟后端（Mock）返回的原始 Payload。
- 异常堆栈（如有）。

## 5. 生成目标 (Output Targets)
[保持 v1.6 列表]
