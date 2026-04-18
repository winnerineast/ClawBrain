# design/memory_entities.md v1.0

## 1. Objective
Introduce **Entity Awareness & Attribute Tracking** to ClawBrain. This enhancement allows the system to recognize key entities (projects, people, technologies) and track their evolving attributes over time, providing a "Source of Truth" summary that complements semantic recall.
### 2.1 Flattened Entity Registry
Unlike a Knowledge Graph, the Entity Registry is a flat collection of key-value pairs scoped to an entity and session.
- **Record Structure**: `(SessionID, EntityName, Attribute, Value)`
- **ChromaDB ID**: `[session_id]_[entity_name]_[attribute_key]`
- **Temporal Linkage**: Every attribute value is linked to the `trace_id` where it was last mentioned, preserving the conversational timeline.

### 2.2 Async Extraction (Cognitive Plane)
Executed in the background via the internal cognitive HTTP client:
1. **Input**: Current interaction trace (User + Assistant).
2. **LLM Prompt (Recursive Extraction)**: 
   "Extract specific entity attributes from the dialogue. Return JSON: `[{"entity": "...", "key": "...", "value": "..."}]`. Only extract hard facts (versions, IPs, roles). Ignore general talk."
3. **Upsert**: Results are stored in a dedicated ChromaDB collection named `entities`. New values for the same key overwrite old ones.

## 3. Retrieval Enhancement
...

## 4. Benefit
...

## 5. Output Targets
- `src/memory/storage.py`: Initialize `entities` collection and add `upsert_fact`.
- `src/memory/entities.py`: Create the extraction orchestration class.
- `src/memory/router.py`: Inject entity facts into the prompt assembly.

1. Identify entities in the current user query.
2. Retrieve the latest attribute values from the Registry.
3. Inject these "Hard Facts" into a new context section: `=== ENTITY REGISTRY (HARD FACTS) ===`.

## 4. Benefit
- **Consistency**: Resolves conflicting information by always prioritizing the most recent attribute update.
- **Precision**: Provides exact answers for technical parameters (versions, IPs) that might be fuzzy in raw vector search.
