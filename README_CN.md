# 🦞 ClawBrain: 智能体工作流的“硅基海马体”

[English](./README.md) | 中文版

<p align="center">
  <img src="https://images.unsplash.com/photo-1507146426996-ef05306b995a?q=80&w=1000&auto=format&fit=crop" width="800" alt="ClawBrain Neural Gateway">
</p>

ClawBrain 是专为 AI 智能体（特别是 [OpenClaw](https://github.com/openclaw/openclaw)）打造的**基础设施层记忆引擎**。它旨在为智能体提供一个持久、进化且高度精准的“大脑”。

它作为一个透明的神经中转站运行：在协议层自动捕获每一次交互，将零散的对话提纯为语义事实，并在最合适的时机将精准的上下文注入模型提示词——这一切都无需您编写代码或更改智能体的核心配置。

---

## 💎 ClawBrain 的优势：为什么要使用它？

大多数 AI 记忆系统要么太浅（依赖手动“保存”工具），要么太重（盲目注入海量文件）。ClawBrain 在网络层解决了这些挑战。

### 1. 100% 无感捕获 (基础设施 vs. 模型)
传统的记忆方式依赖模型“决定”去记住某些内容。在高认知负载下，模型经常忘记保存关键细节。ClawBrain 是**被动式**的：它在请求流过中转站时自动捕获 100% 的交互，确保万无一失。

### 2. 原生语义召回 (本地向量搜索)
不同于依赖关键字匹配的系统，ClawBrain 内置了 **ChromaDB 引擎**。它能理解意图。即使关键字不匹配，搜索“数据库”也能找回关于“Postgres”或“数据存储”的记录。

### 3. 精准预算控制 (堆栈数学)
ClawBrain 不会简单地将记忆塞进 Prompt。它使用**贪婪上下文预算策略**和**堆栈数学 (Stack Math)** 来精确计算每一层记忆的字符开销，确保上下文窗口被高效利用，且永不溢出。

### 4. 外部知识库集成 (Vault)
您的项目不仅存在于聊天记录中。ClawBrain 可以“挂载”您的 **Obsidian 库**，通过高性能的增量扫描（mtime + hash）将您现有的文档直接带入智能体的推理循环。

### 5. 不阻塞的健壮架构
通过**网络资源平面隔离**，ClawBrain 将高优先级的对话流量与后台“认知”任务（如事实提纯、库扫描）彻底分开。即使后台大脑正在全力运转，您的智能体对话依然保持 100% 的即时响应。

---

## 🚀 快速安装 (一分钟启动)

ClawBrain 提供全自动引导工具，可一键完成环境探测、服务发现和配置生成。

```bash
# 1. 克隆仓库
git clone https://github.com/winnerineast/ClawBrain.git
cd ClawBrain

# 2. 运行自动化安装脚本
# 脚本将自动探测 Ollama/LM Studio 和您的本地 Obsidian 库
./install.sh

# 3. 启动服务器
source venv/bin/activate
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 11435
```

---

## 🔌 集成与使用

### 选项 1：透明 HTTP 代理 (推荐)
将您智能体的 API `baseUrl` 指向 ClawBrain（端口 11435）。ClawBrain 将拦截请求，增强记忆，并转发给真实的 LLM 后端。

**OpenClaw Provider 配置示例：**
```json
"ollama": {
  "baseUrl": "http://127.0.0.1:11435",
  "apiKey": "optional"
}
```

### 选项 2：原生 OpenClaw 插件
ClawBrain 也可以作为原生的 Context Engine 插件运行：
```bash
openclaw plugins install -l ./packages/openclaw
```

### 🔐 会话隔离
通过发送一个简单的 HTTP Header，在不同项目或用户之间隔离记忆：
`x-clawbrain-session: project-alpha`

---

## 🧠 三层记忆架构

| 层级 | 组件 | 功能 |
|---|---|---|
| **L1** | **工作记忆** | 活跃注意力。保存最近几轮对话，随时间指数衰减。 |
| **L2** | **海马体** | 情节归档。基于 ChromaDB 的语义向量搜索。 |
| **L3** | **新皮层** | 语义事实。异步 LLM 提纯，将旧记忆转化为硬事实。 |
| **Ext** | **Vault** | 外部知识。本地 Obsidian Markdown 笔记的增量索引。 |

---

## 🛠️ 开发与验证

### 设计先行哲学
ClawBrain 遵循严格的**设计先行**工作流。所有架构变更必须在实施前记录于 `design/` 目录。核心章程请参考 `GEMINI.md`。

### 自动化验证 (真实环境回归)
运行我们的资源感知型回归测试集，确保系统稳定性：
```bash
# 净化环境、重置 GPU 资源并运行 91 项测试
./run_regression.sh
```

---
<p align="right">ClawBrain 团队 🦞 荣誉出品</p>
