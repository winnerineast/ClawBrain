# Generated from design/gateway.md v1.38
import json
from typing import Dict, Any, AsyncGenerator, List
from src.models import StandardRequest

class DialectTranslator:
    """
    Universal Dialect Translator.
    Responsible for converting StandardRequest into each provider's native format.
    """
    
    @staticmethod
    def extract_query(protocol: str, payload: Dict[str, Any]) -> str:
        """Extract the latest user query intent from various protocols."""
        messages = payload.get("messages", [])
        if not messages:
            # api/generate might be in prompt mode
            return payload.get("prompt", "")
            
        # Search backwards for the last user message
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    @staticmethod
    def inject_context(protocol: str, payload: Dict[str, Any], context: str) -> Dict[str, Any]:
        """Inject memory context into system prompts."""
        if not context:
            return payload
            
        messages = payload.get("messages", [])
        
        # Search for system message
        system_msg = next((m for m in messages if m.get("role") == "system"), None)
        
        if system_msg:
            # Append to existing system message
            system_msg["content"] = f"{context}\n\n{system_msg['content']}"
        else:
            # Insert new system message at the top
            messages.insert(0, {"role": "system", "content": context})
            payload["messages"] = messages
            
        # If in prompt mode (api/generate)
        if "prompt" in payload and not messages:
            payload["prompt"] = f"{context}\n\n{payload['prompt']}"
            
        return payload

    @staticmethod
    def to_ollama(request: StandardRequest) -> Dict[str, Any]:
        return request.model_dump(exclude_none=True)

    @staticmethod
    def to_openai(request: StandardRequest) -> Dict[str, Any]:
        """
        Translate to standard OpenAI format.
        Rule 2.1 Correction: Only strip the first prefix (gateway identifier), keeping the model's internal path.
        Resolves LM Studio 400 errors.
        """
        payload = request.model_dump(exclude_none=True)
        model_name = payload.get("model", "")
        if "/" in model_name:
            # lmstudio/nvidia/model -> nvidia/model
            payload["model"] = model_name.split("/", 1)[1]
            
        payload.pop("options", None)
        return payload

    @staticmethod
    def to_anthropic(request: StandardRequest) -> Dict[str, Any]:
        """Translate to Anthropic (Claude) format."""
        raw = request.model_dump(exclude_none=True)
        messages = raw.get("messages", [])
        
        system_parts = []
        normalized = []
        
        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(msg.get("content", ""))
            else:
                if normalized and normalized[-1]["role"] == msg["role"]:
                    normalized[-1]["content"] += "\n" + msg.get("content", "")
                else:
                    normalized.append({"role": msg["role"], "content": msg.get("content", "")})
        
        # Rule 2.1 Correction: Only strip the first prefix
        model_name = raw.get("model", "")
        target_model = model_name.split("/", 1)[1] if "/" in model_name else model_name

        anthropic_body = {
            "model": target_model,
            "max_tokens": raw.get("max_tokens") or 4096,
            "messages": normalized,
            "stream": raw.get("stream", False)
        }
        if system_parts:
            anthropic_body["system"] = "\n".join(system_parts)
        return anthropic_body

    @staticmethod
    def to_google(request: StandardRequest) -> Dict[str, Any]:
        """Translate to Google Gemini format."""
        raw = request.model_dump(exclude_none=True)
        messages = raw.get("messages", [])
        
        contents = []
        system_instruction = ""
        
        for msg in messages:
            if msg.get("role") == "system":
                system_instruction += msg.get("content", "") + "\n"
            else:
                role = "model" if msg.get("role") == "assistant" else "user"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.get("content", "")}]
                })
        
        google_body = {
            "contents": contents,
            "generationConfig": {
                "temperature": raw.get("temperature", 0.7),
                "maxOutputTokens": raw.get("max_tokens", 4096)
            }
        }
        if system_instruction:
            google_body["system_instruction"] = {"parts": [{"text": system_instruction.strip()}]}
            
        return google_body

    @staticmethod
    async def reverse_stream_ollama_to_openai(response_stream: AsyncGenerator[bytes, None]) -> AsyncGenerator[str, None]:
        async for chunk in response_stream:
            if not chunk: continue
            try:
                data = json.loads(chunk)
                openai_chunk = {
                    "id": "chatcmpl-claw", "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {"content": data.get("message", {}).get("content", "")}}]
                }
                yield f"data: {json.dumps(openai_chunk)}\n\n"
                if data.get("done"): yield "data: [DONE]\n\n"
            except: pass
