# design/utils_onboarding.md v1.0

## 1. Objective
Transform ClawBrain from a manual experimental project into a user-friendly tool by providing automated installation, environment discovery, and configuration. The goal is to allow a new user to go from `git clone` to a fully running server in under 60 seconds.

## 2. Functional Components

### 2.1 Universal `install.sh`
A shell script entry point for Linux and macOS that orchestrates the entire setup:
- **OS & Architecture Sensing**: Detects distro (Ubuntu/macOS/Arch), CPU architecture, and GPU availability.
- **Dependency Pre-flight**: Verifies Python 3.10+, Git, and necessary build tools.
- **Automated Bootstrap**:
    - Creates and updates the virtual environment (`venv`).
    - Installs dependencies from `requirements.txt`.
    - Handles ChromaDB-specific library dependencies (e.g., `onnxruntime`).

### 2.2 Setup Scout (The "Brain" of Discovery)
A Python-based utility (`src/utils/setup_scout.py`) that performs deep environmental probing:
- **LLM Service Discovery**: Scans for local instances of Ollama (11434) and LM Studio (1234).
- **Model Intelligence**: Retrieves the list of loaded models and identifies the best candidate for distillation (L3).
- **Knowledge Base Locating**: Searches standard directories for existing Obsidian Vaults to suggest for `CLAWBRAIN_VAULT_PATH`.
- **Resource Profiling**: Measures available system RAM and VRAM to suggest optimal `distill_threshold` and `max_context_chars`.

### 2.3 Auto-Configuration Engine
- Generates a `.env` file based on Scout's findings.
- **Idempotency**: Respects existing `.env` values, only appending or suggesting updates for missing critical keys.

### 2.4 ClawBrain Doctor (Diagnostics)
A command-line tool to verify system health:
- Tests connectivity to the Relay Plane and Cognitive Plane.
- Validates ChromaDB collection integrity.
- Outputs a high-fidelity environment report using the **Rule 3** Side-by-Side layout.

## 3. User Journey
1. User runs `./install.sh`.
2. Script detects Ollama and an Obsidian Vault in `~/Documents`.
3. Script configures `.env` automatically.
4. User is presented with a "Ready to Launch" message and the final run command.

## 4. Test & Verification Specification

### 4.1 Discovery Matrix
Verify that `setup_scout.py` behaves correctly in various environments:
- **Empty Environment**: Gracefully falls back to manual input prompts.
- **Multi-Service Environment**: Correctly prioritizes or lists multiple LLM providers.

### 4.2 Installation Stability
- **Idempotency**: Running `install.sh` multiple times must not corrupt data or double-install packages.
- **Permission Resilience**: Handles non-root environments and ensures `venv` paths are correct.

## 5. Output Targets
1. `install.sh`: Shell script wrapper.
2. `src/utils/setup_scout.py`: Discovery logic.
3. `src/utils/doctor.py`: Diagnostic utility.
4. `tests/test_p36_onboarding.py`: Verification suite.
