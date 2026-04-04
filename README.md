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
*   **实事求是**：它是系统的“无损黑匣子”。无论输入多大，100% 原始字节落盘。对于超过 512KB 的巨量文档，自动执行流式分流以保护内存。支持毫秒级的全文检索。

### 2. 新皮层 (Neocortex) —— 语义记忆层
*   **工程实现**：`src/memory/neocortex.py` (Asynchronous Distillation)
*   **实事求是**：它是系统的“知识提炼池”。通过异步调用轻量级 LLM，将海马体中的琐碎情节泛化为 Bullet Points 形式的事实清单，常驻于模型上下文的边缘。

### 3. 工作记忆 (Working Memory) —— 活跃注意力层
*   **工程实现**：`src/memory/working.py` (Weighted OrderedDict)
*   **实事求是**：它是系统的“瞬时焦点”。基于 **“时间远离度”** 与 **“话题相关度”** 双因子动态计算分值。最近聊过的、以及与当前话题相关的消息会被赋予高激活值（Activation），确保注意力始终聚焦。

---

## 🚀 核心技术特性
- 🔄 **通用协议翻译网关**：内置协议探测器与方言翻译器，支持从本地 Ollama、LM Studio 到云端 30+ 种 Provider 的无缝路由。
- ✂️ **上下文高倍提纯**：基于正则的代码块保护压缩算法，精准剥离 Prefix 噪音，释放模型窗口。
- 🛡️ **契约式准入控制 (TIER)**：根据参数量与协议支持自动分级，硬性拦截能力不足的小模型误用工具。
- 🧪 **高保真审计体系**：遵循 **GEMINI.md** 法典，提供字节级 Hash 校验与数学推导全记录日志。

---

## 🛠️ 安装指南

```bash
git clone https://github.com/winnerineast/ClawBrain.git
cd ClawBrain && python3 -m venv venv
source venv/bin/activate && pip install -r requirements.txt
```

## ⚙️ 配置挂载

在 OpenClaw (`openclaw.json`) 中将 `baseUrl` 指向 `11435` 即可激活神经增强模式。

---
<p align="right">由 GEMINI CLI Agent 依据项目源码 v1.23 生成</p>
