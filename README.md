# 🦞 ClawBrain: 你的智能体工作流“硅基海马体”

[English](./README_EN.md) | 中文版

<p align="center">
  <img src="https://images.unsplash.com/photo-1507146426996-ef05306b995a?q=80&w=1000&auto=format&fit=crop" width="800" alt="ClawBrain Neural Gateway">
</p>

<p align="center">
  <strong>不侵入代码，不妥协性能。为 OpenClaw 打造的确定性、高密度 LLM 神经网关。</strong>
</p>

---

## 🌟 核心愿景 (Vision)
ClawBrain 是一个仿生学设计的 LLM 代理网关。它作为客户端（如 OpenClaw）与底层模型之间的“硅基海马体”，通过**三层动力学记忆系统**和**上下文动态提纯**，让你的 AI 能够像人类一样拥有长期记忆、短期注意力和瞬时反应力。

## 🚀 核心特性 (Key Features)
- 🧠 **三代三子记忆系统 (Neural Memory)**：模拟生物大脑的分层架构——海马体（情节记录）、新皮层（语义泛化）、工作记忆（活跃注意力）。
- ✂️ **上下文高倍提纯 (Context Distillation)**：基于正则的无损压缩技术，在 100% 保护代码缩进的前提下，大幅削减冗余 Token，提升 4090 运行效率。
- 🛡️ **模型准入契约 (TIER Control)**：自动识别模型等级，硬性拦截能力不足的工具调用，确保 Agent 自动化链路不因模型幻觉而崩溃。
- 🔄 **协议对等路由 (Universal Routing)**：原生支持 Ollama 协议，无缝适配 OpenAI 及其它主流接口。

---

## 🛠️ 安装指南 (Installation)

```bash
# 克隆仓库
git clone https://github.com/winnerineast/ClawBrain.git
cd ClawBrain

# 初始化虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

## ⚙️ 配置挂载 (Mounting to OpenClaw)

修改 OpenClaw 配置文件 `~/.openclaw/openclaw.json`，让 Agent 接入“外挂大脑”：

```json
"ollama": {
  "baseUrl": "http://127.0.0.1:11435",  // 路由至 ClawBrain 神经网关
  "api": "ollama"
}
```

---

## 🧪 自动化审计 (Audit)
项目遵循 **GEMINI.md** 宪法，所有核心功能均通过 Side-by-Side 证据审计，确保逻辑 100% 确定。

```bash
# 执行全量验收测试
export PYTHONPATH=$PYTHONPATH:.
pytest tests/
```

---
<p align="right">由 GEMINI CLI Agent v1.19 驱动生成</p>
