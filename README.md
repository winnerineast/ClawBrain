# 🦞 ClawBrain: 为智能体工作流打造的“硅基海马体”

[English](./README_EN.md) | 中文版

<p align="center">
  <img src="https://images.unsplash.com/photo-1507146426996-ef05306b995a?q=80&w=1000&auto=format&fit=crop" width="800" alt="ClawBrain Neural Gateway">
</p>

ClawBrain 是一个开源的 LLM 代理网关。它的核心价值在于：**作为 OpenClaw 的外挂大脑，它不仅解决多协议路由，更通过一套仿生记忆算法，在受限的本地显存（如 4090）环境下，实现上下文的高倍提纯与长程记忆召回。**

---

## 🧠 设计哲学：三子算法记忆系统
项目深受“虾叔理论”启发，并在工程上实现了三层动力学记忆架构：

### 1. 海马体 (Hippocampus) —— 情节记忆层
*   **工程实现**：`src/memory/storage.py` (SQLite FTS5 + Blob Storage)
*   **特性**：系统的“无损黑匣子”。100% 原始字节落盘，支持 10MB 级流式分流保护内存，提供毫秒级全文检索。

### 2. 新皮层 (Neocortex) —— 语义记忆层
*   **工程实现**：`src/memory/neocortex.py` (Asynchronous Distillation)
*   **特性**：系统的“知识提炼池”。通过异步后台任务，将琐碎情节泛化为 Bullet Points 事实清单，常驻于模型上下文边缘。

### 3. 工作记忆 (Working Memory) —— 活跃注意力层
*   **工程实现**：`src/memory/working.py` (Weighted OrderedDict)
*   **特性**：系统的“瞬时焦点”。基于 **“时间远离度”** 与 **“话题相关度”** 双因子动态计算激活值，确保注意力始终聚焦。

---

## 🔄 支持的模型托管与提供商 (Supported Hosting)
ClawBrain 通过通用协议翻译层，支持以下主流平台：

- **本地私有化 (Local)**:
  - **Ollama**: 默认后端，支持全量审计。
  - **LM Studio**: 通过 OpenAI 兼容协议接入。
  - **vLLM / SGLang**: 适用于高并发生产环境。
- **云端 API (Cloud)**:
  - **OpenAI (GPT-4o/o1)**: 官方 REST 接口。
  - **DeepSeek**: 兼容 OpenAI 格式的高性价比方案。
  - **Anthropic (Claude 3.5)**: 原生 API 支持（开发中）。
  - **OpenRouter / Together AI**: 聚合类网关。

---

## ⚙️ 配置挂载 (Mounting & Configuration)

### 1. 网络入口 (Entry Point)
ClawBrain 默认监听本地端口 **`11435`**。
- **Default Base URL**: `http://127.0.0.1:11435`

### 2. 客户端接入示例 (以 OpenClaw 为例)
修改 `~/.openclaw/openclaw.json`，将 Provider 的 `baseUrl` 指向 ClawBrain：

```json
"models": {
  "providers": {
    "ollama": {
      "baseUrl": "http://127.0.0.1:11435", // 流量由此进入神经网关
      "api": "ollama",
      "apiKey": "OLLAMA_API_KEY"
    }
  }
}
```

### 3. 模型适配器路由 (Model Prefixes)
你可以通过模型名前缀动态指定后端：
- `ollama/gemma4:e4b`：路由至本地 Ollama (11434)。
- `lmstudio/llama-3`：路由至本地 LM Studio (1234)。
- `openai/gpt-4o`：路由至 OpenAI 官方云端。

---

## 🚀 核心技术特性
- 🔄 **通用协议翻译网关**：内置协议探测器，实现 OpenAI/Ollama 跨协议无缝路由。
- ✂️ **上下文高倍提纯**：基于正则的代码块保护压缩算法，精准剥离冗余噪音。
- 🛡️ **契约式准入控制 (TIER)**：自动识别模型等级，硬性拦截能力不足的工具调用。
- 🧪 **高保真审计体系**：遵循 **GEMINI.md** 法典，提供字节级 Hash 校验记录。

---

## 🛠️ 安装指南

```bash
git clone https://github.com/winnerineast/ClawBrain.git
cd ClawBrain && python3 -m venv venv
source venv/bin/activate && pip install -r requirements.txt
```

---
<p align="right">由 GEMINI CLI Agent 依据项目源码 v1.23 生成</p>
