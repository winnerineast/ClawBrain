# Generated from design/gateway.md v1.8
import re
from src.models import StandardRequest
from src.scout import ModelTier

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
