# 🦞 ClawBrain: 为智能体工作流打造的“硅基海马体”

[English](./README_EN.md) | 中文版

<p align="center">
  <img src="https://images.unsplash.com/photo-1507146426996-ef05306b995a?q=80&w=1000&auto=format&fit=crop" width="800" alt="ClawBrain Neural Gateway">
</p>

ClawBrain 是一个仿生学设计的 LLM 代理网关。它作为 OpenClaw 与底层模型之间的“硅基海马体”，通过**三层动力学记忆系统**和**上下文动态提纯**，让你的 AI 能够像人类一样拥有长期记忆、短期注意力和瞬时反应力。

---

## ⚙️ 配置挂载 (Mirror Configuration)

ClawBrain 采用“透明镜像”配置逻辑。你只需要在客户端（如 OpenClaw）中将原本的地址替换为 ClawBrain，并在 ClawBrain 中配置真实的上游凭证。

### 1. 客户端侧配置 (Client Side)
将你的 `openclaw.json` 或其它客户端的 `baseUrl` 指向本地端口 **`11435`**：

```json
"ollama": {
  "baseUrl": "http://127.0.0.1:11435", // 指向 ClawBrain，不再直连后端
  "api": "ollama"
}
```

### 2. 网关侧配置 (ClawBrain Side)
在 ClawBrain 根目录的 `.env` 文件中配置真实的上游 (Upstream) 目标。系统会自动完成鉴权注入与协议转换。

```env
# 基础网关设置
GATEWAY_PORT=11435

# --- 上游提供商配置 (Upstream Credentials) ---

# Ollama 本地实例
PROVIDER_OLLAMA_URL=http://127.0.0.1:11434

# LM Studio 本地实例
PROVIDER_LMSTUDIO_URL=http://127.0.0.1:1234

# 云端 OpenAI (自动处理 Bearer Token 注入)
PROVIDER_OPENAI_URL=https://api.openai.com
PROVIDER_OPENAI_KEY=sk-your-openai-key-here

# 云端 DeepSeek
PROVIDER_DEEPSEEK_URL=https://api.deepseek.com
PROVIDER_DEEPSEEK_KEY=sk-your-deepseek-key-here
```

### 3. 模型路由规则 (Routing)
根据你在客户端使用的模型名前缀，ClawBrain 会自动选择对应的上游：
- `ollama/gemma4:e4b` $\rightarrow$ 路由至本地 11434 端口。
- `lmstudio/llama-3` $\rightarrow$ 路由至本地 1234 端口。
- `deepseek/deepseek-chat` $\rightarrow$ 路由至云端，并自动带上 API Key。

---

## 🚀 核心技术特性
- 🧠 **三代三子算法记忆系统**：海马体（无损情节）、新皮层（异步语义）、工作记忆（双因子注意力）。
- 🛡️ **契约式准入控制 (TIER)**：自动拦截 7B 以下小模型的复杂工具请求，保障 Agent 链路稳定。
- 🔄 **通用协议翻译层**：完美模拟并转换 OpenAI/Ollama 异构协议及其流式数据。

---

## 🛠️ 安装指南

```bash
# 初始化
git clone https://github.com/winnerineast/ClawBrain.git
cd ClawBrain && python3 -m venv venv
source venv/bin/activate && pip install -r requirements.txt

# 启动 (确保已配置 .env)
uvicorn src.main:app --host 127.0.0.1 --port 11435
```

---
<p align="right">由 GEMINI CLI Agent 依据项目源码 v1.24 生成</p>
