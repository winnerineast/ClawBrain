# design/memory_entities.md v1.0

## 1. Objective
Introduce **Entity Awareness & Attribute Tracking** to ClawBrain. This enhancement allows the system to recognize key entities (projects, people, technologies) and track their evolving attributes over time, providing a "Source of Truth" summary that complements semantic recall.

## 2. Core Concepts

### 2.1 Flattened Entity Registry
Unlike a Knowledge Graph, the Entity Registry is a flat collection of key-value pairs scoped to an entity and session.
- **Record Structure**: `(SessionID, EntityName, Attribute, Value)`
- **Temporal Linkage**: Every attribute value is linked to the `trace_id` where it was last mentioned, preserving the conversational timeline.

### 2.2 Async Extraction (Cognitive Plane)
Executed in the background via the internal cognitive HTTP client:
1. **Input**: Current interaction trace (User + Assistant).
2. **LLM Prompt**: "Extract any specific facts about entities mentioned. E.g., Version numbers, role assignments, or project status."
3. **Upsert**: Results are stored in a dedicated ChromaDB collection named `entities`.

## 3. Retrieval Enhancement
In `get_combined_context`, the system will perform an **Entity Lookup**:
1. Identify entities in the current user query.
2. Retrieve the latest attribute values from the Registry.
3. Inject these "Hard Facts" into a new context section: `=== ENTITY REGISTRY (HARD FACTS) ===`.

## 4. Benefit
- **Consistency**: Resolves conflicting information by always prioritizing the most recent attribute update.
- **Precision**: Provides exact answers for technical parameters (versions, IPs) that might be fuzzy in raw vector search.
