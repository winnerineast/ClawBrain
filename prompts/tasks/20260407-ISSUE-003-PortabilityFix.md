# Task: ISSUE-003 Portability Fix - Remove Hardcoded Absolute Paths

## 1. Objective
Replace all hardcoded `/home/nvidia/ClawBrain` paths with dynamic, relative, or environment-driven paths to ensure the project runs on any OS (Linux/macOS).

## 2. Remediation Plan

### Phase 32: Dynamic Base Paths in Source
- **Change**: Update `src/main.py`, `src/memory/router.py`, `src/memory/storage.py`, and `src/memory/neocortex.py`.
- **Logic**: Use `os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))` or similar dynamic resolution if `CLAWBRAIN_DB_DIR` is not set. Better yet, default to `./data` relative to the current working directory if not specified.

### Phase 33: Dynamic Test Directories
- **Change**: Update all files in `tests/` that hardcode `/home/nvidia`.
- **Logic**: Use paths relative to the test file or the project root. For example, `os.path.join(os.getcwd(), "tests/data/...")`.

### Phase 34: Design Document Alignment
- **Change**: Update `design/memory_router.md`, `design/memory_neocortex.md`, and others to remove hardcoded paths in default parameters.

## 3. Implementation Steps
1. Surgically update design documents.
2. Apply code changes to `src/` files.
3. Apply code changes to `tests/` files.
4. Run full regression tests to verify 100% success on the current macOS environment.

## 4. Verification Results
- Goal: `pytest tests/` should pass all non-live tests on macOS.
