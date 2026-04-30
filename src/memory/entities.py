# Generated from design/memory_entities.md v1.0
import json
import logging
from typing import List, Dict, Any, Optional
from src.utils.llm_client import LLMClient, LLMFactory

logger = logging.getLogger("GATEWAY.MEMORY.ENTITIES")

class EntityExtractor:
    """
    Cognitive Entity Attribute Extractor.
    Mines hard facts (versions, IPs, roles) from conversational traces using LLM.
    """
    SYSTEM_PROMPT = """
    You are a precise Entity Fact Miner. Your goal is to extract hard, technical facts from a dialogue and return them as a JSON list.
    
    FACT TYPES TO EXTRACT:
    1. Versions (e.g., "Python 3.12", "v1.5")
    2. Infrastructure (e.g., "IP 127.0.0.1", "Port 5432")
    3. Project Roles (e.g., "Alice is the Lead", "Backend uses FastAPI")
    4. Technical Decisions (e.g., "Database is PostgreSQL")

    JSON FORMAT:
    [{"entity": "Entity Name", "key": "Attribute Key", "value": "Fact Value"}]

    RULES:
    1. Only extract HARD facts. Ignore general greetings, questions, or vague talk.
    2. If a fact is an update to a previous one, extract it clearly.
    3. Return ONLY the JSON array. No preamble, no explanation.
    4. If no facts are found, return [].
    """

    def __init__(self, hippo, llm: Optional[LLMClient] = None):
        self.hippo = hippo
        self.llm = llm or LLMFactory.from_env()

    async def extract_and_store(self, session_id: str, trace_id: str, payload: Dict[str, Any]):
        """Extract attributes from a single trace and upsert them to Hippo."""
        # 1. Build corpus from trace
        corpus = []
        stimulus = payload.get("stimulus") if "stimulus" in payload else payload
        msgs = stimulus.get("messages", [])
        for m in msgs:
            corpus.append(f"User: {m.get('content', '')}")
        
        reaction = payload.get("reaction")
        if reaction:
            corpus.append(f"Assistant: {reaction.get('content', '')}")
        
        if not corpus: return
        
        dialogue_text = "\n".join(corpus)
        
        # 2. Dispatch to LLM
        try:
            result = await self.llm.generate(prompt=dialogue_text, system=self.SYSTEM_PROMPT)
            
            # Phase 61: Robust JSON Extraction (Issue #006)
            # LLMs with reasoning might output text + JSON. We extract the first [...] found.
            import re
            json_match = re.search(r'\[\s*\{.*\}\s*\]', result, re.DOTALL)
            if not json_match:
                logger.debug(f"[ENTITIES] No JSON array found in result for trace {trace_id}")
                return

            clean_json = json_match.group(0)
            facts = json.loads(clean_json)
            
            if not isinstance(facts, list):
                logger.warning(f"[ENTITIES] Expected list, got {type(facts)}")
                return

            # 3. Store in Hippo
            for f in facts:
                entity = f.get("entity")
                key = f.get("key")
                value = f.get("value")
                if entity and key and value:
                    self.hippo.upsert_fact(session_id, entity, key, value, trace_id=trace_id)
                    logger.debug(f"[ENTITIES] Stored: {entity} > {key}: {value}")

        except Exception as e:
            logger.error(f"[ENTITIES] Extraction failed for trace {trace_id}: {e}")
