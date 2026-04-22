# Generated from design/gateway.md v1.42
import json
import logging
from typing import Dict, Any, List, Optional
from src.models import StandardRequest, Message, Tool

logger = logging.getLogger("GATEWAY.DETECTOR")

class ProtocolDetector:
    """
    Universal Protocol Detector.
    Responsible for standardizing various client protocols.
    Rule 2.3 Correction: Deep extraction of tools, options, stream, and other metadata.
    """
    
    @staticmethod
    def detect(path: str, body: Dict[str, Any]) -> str:
        """1. Detect Protocol"""
        if "/chat/completions" in path or "messages" in body:
            return "openai"
        if "/api/generate" in path:
            return "ollama"
        if "contents" in body:
            return "google"
        return "openai" # Default to OpenAI-compatible

    @staticmethod
    def to_standard(protocol: str, body: Dict[str, Any]) -> StandardRequest:
        """2. Deep Metadata Alignment"""
        # Rule 2.3: Extract from top-level, options, or extra_body
        options = body.get("options", {})
        extra = body.get("extra_body", {})
        
        tools = body.get("tools") or options.get("tools") or extra.get("tools")
        tool_choice = body.get("tool_choice") or options.get("tool_choice") or extra.get("tool_choice")
        stream = body.get("stream") or options.get("stream") or extra.get("stream") or False
        
        # Merge options (Ollama compatibility)
        merged_options = {**options}
        if "options" in extra:
            merged_options.update(extra["options"])
        
        # 3. Construct Standard Request
        req = StandardRequest(
            model=body.get("model", ""),
            messages=body.get("messages", []),
            stream=stream,
            temperature=body.get("temperature") or options.get("temperature"),
            max_tokens=body.get("max_tokens") or body.get("max_tokens_to_sample") or options.get("num_predict"),
            tools=tools,
            tool_choice=tool_choice,
            options=merged_options
        )
        
        # Force override to ensure metadata integrity
        if not req.messages and "prompt" in body:
            req.messages = [{"role": "user", "content": body["prompt"]}]
            
        return req
