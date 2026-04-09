# Generated from design/gateway.md v1.8 / Phase 25 / Phase 32
import re
import json
import asyncio
import logging
from typing import Dict, Any, AsyncGenerator, List
from src.models import StandardRequest
from src.scout import ModelTier
from src.memory.router import MemoryRouter

logger = logging.getLogger("GATEWAY.PIPELINE")

class WhitespaceCompressor:
    """
    High-precision compression engine based on design/gateway.md v1.8.
    Splits code blocks first, then performs noise reduction on non-code regions.
    """
    @staticmethod
    def compress(text: str) -> str:
        if not text:
            return text
        
        # Follow Rule 2.1: Capture code blocks first to preserve indentation lossless
        pattern = r'(```[\s\S]*?```)'
        # Using capturing group in re.split will keep delimiters
        parts = re.split(pattern, text)
        processed_parts = []
        
        for part in parts:
            if part.startswith('```') and part.endswith('```'):
                # Protection logic hit
                processed_parts.append(part)
            else:
                # Rule 2.1: Only process non-code block regions
                # Convert 2+ spaces to 1
                temp = re.sub(r' {2,}', ' ', part)
                # Convert 3+ newlines to 2
                temp = re.sub(r'\n{3,}', '\n\n', temp)
                processed_parts.append(temp)
        
        return "".join(processed_parts)

class SafetyEnforcer:
    TIER2_PATCH = "\n\n[SYSTEM ENFORCEMENT]: You must respond ONLY in valid JSON format. Do not add any conversational preamble or postscript."

    @classmethod
    def apply(cls, request: StandardRequest, tier: ModelTier):
        if tier in [ModelTier.TIER_2, ModelTier.TIER_3] and request.messages:
            # Rule 2.2: Idempotency check
            if cls.TIER2_PATCH not in request.messages[0].content:
                request.messages[0].content += cls.TIER2_PATCH
        return request

class Pipeline:
    def __init__(self):
        self.compressor = WhitespaceCompressor()
        self.enforcer = SafetyEnforcer()

    def run(self, request: StandardRequest, tier: ModelTier) -> StandardRequest:
        for msg in request.messages:
            if msg.content:
                msg.content = self.compressor.compress(msg.content)
        request = self.enforcer.apply(request, tier)
        return request

    async def post_turn_solidification(self, final_json: Dict[str, Any], protocol: str, session_id: str, mr: MemoryRouter, original_body: Dict[str, Any] = None):
        """P25: OpenClaw Loopback - Archive the turn after a successful response."""
        try:
            # 1. Extract assistant response content based on protocol
            assistant_content = ""
            if protocol == "ollama":
                assistant_content = final_json.get("message", {}).get("content", "")
            else:
                choices = final_json.get("choices", [])
                if choices:
                    assistant_content = choices[0].get("message", {}).get("content", "")

            if not assistant_content:
                return

            # 2. Reconstruct reaction object
            reaction = {"message": {"role": "assistant", "content": assistant_content}}

            # 3. Trigger ingest (L1 charge + L2 archive)
            # Use original_body as the stimulus
            if original_body:
                await mr.ingest(original_body, reaction=reaction, context_id=session_id)
                logger.info(f"[PIPELINE] Archived turn for session: {session_id}")
            
        except Exception as e:
            logger.error(f"Post-turn solidification failed: {e}")

    async def stream_relay(self, http_client, upstream_url, body, upstream_headers, session_id, mr) -> AsyncGenerator[bytes, None]:
        """Phase 32: Asynchronous streaming relay with turn capture."""
        assistant_chunks = []
        try:
            async with http_client.stream("POST", upstream_url, json=body, headers=upstream_headers) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk
                    # Capture assistant content from SSE chunks
                    # Note: This is a simplified parser for Ollama/OpenAI SSE
                    try:
                        text = chunk.decode("utf-8", errors="ignore").strip()
                        if text.startswith("data:"):
                            text = text[5:].strip()
                        if text and text != "[DONE]":
                            data = json.loads(text)
                            # Ollama format
                            if "message" in data:
                                assistant_chunks.append(data["message"].get("content", ""))
                            # OpenAI format
                            elif "choices" in data and data["choices"]:
                                delta = data["choices"][0].get("delta", {})
                                assistant_chunks.append(delta.get("content", ""))
                    except:
                        pass
            
            # After stream ends, archive the full turn
            assistant_final = "".join(assistant_chunks)
            if assistant_final:
                reaction = {"message": {"role": "assistant", "content": assistant_final}}
                # Note: ingest is async, we fire and forget or await
                asyncio.create_task(mr.ingest(body, reaction=reaction, context_id=session_id))
                logger.info(f"[STREAM] Captured and archived turn for session: {session_id}")
            
        except Exception as e:
            logger.error(f"Stream relay failed: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n".encode()
