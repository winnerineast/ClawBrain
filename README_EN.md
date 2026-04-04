# 🦞 ClawBrain: The Silicon Hippocampus for your Agentic Workflow

English | [中文版](./README.md)

<p align="center">
  <img src="https://images.unsplash.com/photo-1507146426996-ef05306b995a?q=80&w=1000&auto=format&fit=crop" width="800" alt="ClawBrain Neural Gateway">
</p>

<p align="center">
  <strong>Non-intrusive code, uncompromised performance. A deterministic, high-density LLM neural gateway for OpenClaw.</strong>
</p>

---

## 🌟 Vision
ClawBrain is a biomimetic LLM agent gateway. Acting as a "Silicon Hippocampus" between clients (like OpenClaw) and underlying models, it utilizes a **tri-layer dynamic memory system** and **context distillation** to empower your AI with human-like long-term memory, short-term attention, and instantaneous reflexes.

## 🚀 Key Features
- 🧠 **Tri-Layer Neural Memory**: Mimics the hierarchical architecture of the biological brain—Hippocampus (Episodic), Neocortex (Semantic), and Working Memory (Active Attention).
- ✂️ **High-Ratio Context Distillation**: Regex-based lossless compression that slashes redundant tokens while preserving 100% of code indentation, maximizing the efficiency of hardware like the RTX 4090.
- 🛡️ **Model Qualification Contract (TIER Control)**: Automatically classifies model capabilities and intercepts tool calls for underpowered models, ensuring agentic pipelines don't collapse due to hallucinations.
- 🔄 **Universal Protocol Routing**: Native support for the Ollama protocol with seamless adaptability for OpenAI and other mainstream interfaces.

---

## 🛠️ Installation

```bash
# Clone the repository
git clone https://github.com/winnerineast/ClawBrain.git
cd ClawBrain

# Initialize virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## ⚙️ Mounting to OpenClaw

Modify your OpenClaw configuration at `~/.openclaw/openclaw.json` to plug in the "External Brain":

```json
"ollama": {
  "baseUrl": "http://127.0.0.1:11435",  // Route to ClawBrain Neural Gateway
  "api": "ollama"
}
```

---

## 🧪 Automated Audit
The project adheres to the **GEMINI.md** constitution. All core functionalities are verified via Side-by-Side evidence auditing to ensure 100% logical determinism.

```bash
# Run full acceptance tests
export PYTHONPATH=$PYTHONPATH:.
pytest tests/
```

---
<p align="right">Driven by GEMINI CLI Agent v1.19</p>
