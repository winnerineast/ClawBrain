# design/model_decoupling.md v1.0

## 1. Objective
Establish a **Universal LLM Abstraction Layer** for ClawBrain. This module must shield higher-level cognitive components (Neocortex, PageIndex, RoomDetector) from the technical discrepancies of various LLM hosters (Ollama, LM Studio, OMLX, vLLM, sglang, etc.) while providing intelligent, resource-aware model selection.

## 2. Functional Specification

### 2.1 Standardized Interfaces
- **ChatClient**: Provides `generate(prompt, system, **kwargs)` and `chat(messages, **kwargs)`.
    - Automatically handles endpoint variations (e.g., `/api/generate` for Ollama, `/v1/chat/completions` for OpenAI-compatible).
    - Standardizes parameter names (e.g., `num_predict` vs `max_tokens`).
- **EmbedClient**: Provides `embed(texts)`.
    - Standardizes vector embedding requests across providers.

### 2.2 Intelligent Environment Adaptation
The module must perform a multi-stage discovery process:
1.  **Hardware Profiling**:
    - **OS Detection**: Identify macOS (Darwin) vs Ubuntu (Linux).
    - **VRAM/Memory**: Detect Apple Silicon Unified Memory or NVIDIA VRAM.
2.  **Hoster Discovery**:
    - Port-scan local services: OMLX (8080), LM Studio (1234), Ollama (11434), vLLM (8000), sglang (30000).
3.  **Model Inventory**:
    - Query active hosters for installed models.
    - Categorize models by size (e.g., 1.5B, 8B, 35B) and capabilities (Chat vs Embed).

### 2.3 Role-Based Model Selection
The `LLMScheduler` assigns models based on the detected hardware tier and the task's functional requirements:
- **`worker` Role (High-volume/Indexing)**:
    - Target: Absolute smallest functional chat model (e.g., 1.5B - 3B).
    - Goal: Maximize speed and stability for recursive summarization.
- **`brain` Role (Decision/Reasoning)**:
    - Target: Largest model the hardware can comfortably run (Tier 1: 35B-70B, Tier 2: 8B-14B, Tier 3: 3B).
    - Goal: Maximize cognitive precision.
- **`embedding` Role**:
    - Target: Dedicated local embedding model (e.g., `nomic-embed`) if available.

### 2.4 Resilience & Health
- **Strict Response Validation**: Intercept empty LLM responses and signal them as errors to trigger upstream retries.
- **Pre-flight Health Checks**: Before selecting a model, perform a minimal handshake (`Say OK`) to ensure the model is actually loaded and responding.

## 3. Implementation Targets
- `src/utils/llm_client.py`: Universal abstraction and scheduler.
- `src/memory/neocortex.py`: Update to use `LLMFactory`.
- `src/memory/page_indexer.py`: Update to use `LLMScheduler`.
- `src/memory/router.py`: Update to use unified clients.
