# design/memory_pageindex.md v1.3

## 1. Objective
Introduce the `PageIndexer` — a specialized cognitive module that implements vectorless, reasoning-based retrieval for large or complex documents. This module transforms hierarchical document structures (TOC) into a navigable reasoning tree, allowing ClawBrain to achieve extreme precision where traditional vector similarity fails.

## 2. Architecture: The "Cerebral Cortex" Module

### 2.1 Concept: Tree-Based Indexing
Unlike the `VaultIndexer` which chunks and embeds text, the `PageIndexer` builds a structured JSON tree representing the document's hierarchy.
- **Node Structure**:
  ```json
  {
    "id": "node_id",
    "title": "Section Title",
    "summary": "AI-generated summary of this section and its children",
    "page_range": [start, end],
    "children": [...]
  }
  ```

### 2.2 Component: PageIndexer
A background worker that supplements the `VaultIndexer`.
- **Trigger**: Files in the Vault > 5000 characters or `.pdf` extension.
- **Indexing Logic**:
  1. **Markdown**: Parse headers (`#`, `##`) to build the tree.
  2. **PDF (v1.3)**: Use `PyMuPDF` (fitz) to extract the Table of Contents (TOC). If no TOC exists, perform page-based segmentation.
  3. **Recursive Summarization**: Use `LLMClient` to generate summaries for each section and parent node.
  4. **JSON Persistence**: Store the tree in `data/pageindex/{file_hash}.json`.

### 2.3 Retrieval Logic (Reasoning Traversal)
1. **Breadth-First Reasoning**: LLM examines top-level summaries to identify relevant branches.
2. **Depth-First Descent**: LLM traverses down the chosen branch until a leaf node (specific page/section) is reached.
3. **Verification**: Leaf node content is fetched and verified against the query.

### 2.4 Configuration
- `CLAWBRAIN_PAGEINDEX_THRESHOLD`: Min file size to trigger PageIndex (default: 5000).
- `CLAWBRAIN_PAGEINDEX_MODEL`: LLM used for tree traversal (defaults to `CLAWBRAIN_DISTILL_MODEL`).

## 3. Test Specification (Functional Regression)

### 3.1 Tree Generation
- **Input**: A complex 10KB Markdown file with nested headers.
- **Expected**: A JSON file with a matching hierarchical depth and coherent summaries.

### 3.2 PDF Structural Parsing (v1.3)
- **Input**: A multi-page PDF with a standard TOC.
- **Expected**: `PageIndexer` successfully extracts the TOC and maps it to a `PageNode` tree with valid page ranges.

### 3.3 Traversal Precision
- **Input**: Query requiring facts from a specific deep section.
- **Expected**: Path trace shows LLM correctly choosing the sub-node and returning the exact page content.

## 4. Integration Logic (Hybrid Router)
The `MemoryRouter` will call `PageIndexer.reasoning_search(query)` when:
- Vector search returns a score below `0.7`.
- The query matches a "High Complexity" fingerprint (detected via `SignalDecomposer`).

## 5. Output Targets
- `src/memory/page_indexer.py`: Core logic for tree building and search.
- `src/memory/router.py`: Hybrid routing integration.
- `tests/test_p66_pageindex.py`: Regression tests.
