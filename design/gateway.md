# design/gateway.md v1.17

## 1. 系统愿景 (Objective)
生成 **ClawBrain Gateway**。作为 LLM 的质量守门员，通过“准入要素”判定模型等级，并强制执行对应的“行为 KPI”，确保 OpenClaw 自动化链路的可靠性。

## 2. 模型分级准入体系 (Model Qualification Framework)

### 2.1 准入要素 (Tier Elements)
网关必须基于以下三个硬性要素进行综合判定：
1. **参数规模 (Scale)**：从模型标签（如 7b, 14b, 31b）或元数据提取。
2. **架构能力 (Brain)**：通过模型族（如 qwen2.5, gemma4）识别其推理上限。
3. **协议支持 (Protocol)**：元数据中是否声明 `TOOLS` 支持。

### 2.2 级别界定与行为 KPI (Tier Definitions & KPIs)

| 等级 (Tier) | 准入要素 (Elements) | 预期行为 KPI (KPIs) | 网关动作 (Action) |
| :--- | :--- | :--- | :--- |
| **TIER_1_EXPERT** | 参数 $\ge$ 20B 或 (参数 $\ge$ 7B 且支持 Tools) | 工具调用成功率 > 98%；支持多步推理。 | **全速通行**：无修饰透传所有请求。 |
| **TIER_2_LEGACY** | 7B $\le$ 参数 < 20B 且不支持原生 Tools | 工具调用常伴随前导词；易发生格式偏移。 | **指令增强**：强制注入系统级 JSON 约束补丁。 |
| **TIER_3_BASIC** | 参数 < 7B | 逻辑链极短；极高概率在工具调用中产生幻觉。 | **强制拦截**：检测到 `tools` 字段立即返回 **422**。 |

## 3. 核心架构逻辑 (Core Logic)

### 3.1 确定性评级引擎 (Scout Engine)
- **规则优先**：内置 `KnownModels` 映射表。`qwen2.5:latest` (4.7B) 必须被硬性标记为 `TIER_3`。
- **异常收口**：Scout 内部的所有网络或解析异常必须被 `try-except` 捕获，并默认降级为 `TIER_3` 以保障安全。

### 3.2 稳定流式转发 (Reliable Stream)
- **生命周期**：由 FastAPI `lifespan` 提供全局单例 `httpx.AsyncClient`。
- **状态校验**：转发前校验 `response.is_success`。

## 4. 测试与审计规范 (TDD)
- **E2E 拦截审计**：`qwen2.5:latest` 带工具请求必须产生 422 响应。
- **审计证据**：日志必须明确打印：`[MODEL_QUAL] Model: <name> | Elements: [params, tools] | Assigned: <Tier> | KPI Action: <Block/Enforce/Pass>`。

## 5. 生成目标
- `src/main.py`, `src/scout.py`, `src/pipeline.py`, `src/adapters/ollama.py`, `tests/test_p5_e2e.py`。
