# design/memory_vault.md v1.0

## 1. Objective
Enable ClawBrain to integrate local external knowledge bases, specifically Obsidian vaults, as a prioritized "Source of Truth". This feature allows the AI agent to access structured project notes and documentation alongside interaction memory, utilizing a high-performance incremental indexing system.

## 2. Architecture: The "External Cognitive Plane"

### 2.1 Component: Vault Indexer
A background worker running in the Cognitive Plane that manages the lifecycle of external markdown files.
- **Incremental Logic**: Implements a "Metadata-First" strategy using file modification times (mtime) and SHA-256 content hashing to minimize redundant embedding calls.
- **Storage**: Chunks are stored in a dedicated ChromaDB collection named `vault_knowledge`.
- **State Management**: Persists indexer state in `vault_state.json` to track processed files across restarts.

### 2.2 Configuration
- `CLAWBRAIN_VAULT_PATH`: Absolute path to the local Obsidian vault.
- `CLAWBRAIN_VAULT_SCAN_INTERVAL`: Seconds between background scans (default: 300).

## 3. Test Specification (Rigorous Verification)

### 3.1 Change Detection Matrix
To verify the "mtime + hash" logic, the test suite must execute the following scenarios to ensure performance (skipping unnecessary work) and correctness (identifying actual content changes).

| Case ID | Action | Expected mtime | Expected Hash | Expected Behavior | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC_ZERO** | Initial Scan | New | New | **Full Indexing** | Establish baseline state. |
| **TC_STALE** | Idle | Unchanged | Unchanged | **Total Skip** | Verify mtime filter efficiency (no hash computed). |
| **TC_TOUCH** | `touch -m` file | **Changed** | **Unchanged** | **Skip after Hash** | **Core Test**: Prevent redundant indexing when metadata changes but content is identical. |
| **TC_REAL** | Edit & Save | **Changed** | **Changed** | **Re-index** | Verify standard update flow. |
| **TC_GHOST** | Edit & Revert mtime | **Unchanged** | **Changed** | **Skip (Risk)** | Documented limitation: mtime is the primary gate for performance. |

### 3.2 Test Data Preparation: The "Hardened Vault Mock"
Tests will use `tests/data/vault_generator.py` to programmatically create a mock environment that manipulates filesystem metadata:

1. **Metadata Manipulation**: Use `os.utime()` to forge modification timestamps without changing file bytes.
2. **Structural Depth**: Include nested directories (`/Projects/A/spec.md`) and cross-links (`[[Note B]]`).
3. **Chunking Stress**: A 50KB markdown file with deep headers (`#` to `####`) to verify `heading_path` propagation in metadata.
4. **Volume Test**: 100+ small files to measure the overhead of the mtime scanning pass.

### 3.3 Integration Audit (Rule 3 Layout)
Audit logs must provide side-by-side evidence of the decision-making process:
- **Indexer Audit**: `FILENAME | MTIME_MATCH (Y/N) | HASH_MATCH (Y/N) | EMBEDDING_TRIGGERED (Y/N)`
- **Retrieval Audit**: `QUERY | VAULT_HIT (Y/N) | SOURCE_FILE | SIMILARITY_SCORE`

## 4. Retrieval Logic (get_combined_context)
1. **Priority**: Vault Knowledge is injected between L3 (Neocortex) and L1 (Working Memory).
2. **Search**: Performs a vector search on the `vault_knowledge` collection using the user's current intent.
3. **Format**: Outputted under the header `=== EXTERNAL KNOWLEDGE (VAULT) ===`.

## 5. Output Targets
1. `src/memory/vault_indexer.py`: The incremental scanning engine.
2. `src/memory/router.py`: Integration into the assembly pipeline.
3. `tests/data/vault_generator.py`: Reproducible test environment setup.
4. `tests/test_p35_vault_integration.py`: The TDD verification suite.
