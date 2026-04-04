# Generated from design/gateway.md v1.8
import re
from src.models import StandardRequest
from src.scout import ModelTier

class WhitespaceCompressor:
    """
    基于 design/gateway.md v1.8 实现的高精度压缩引擎。
    先切分代码块，再对非代码块区域执行底噪去除。
    """
    @staticmethod
    def compress(text: str) -> str:
        if not text:
            return text
        
        # 遵循 2.1 准则：先捕获代码块，保持缩进无损
        pattern = r'(```[\s\S]*?```)'
        # 使用括号捕获组，split 会保留分隔符
        parts = re.split(pattern, text)
        processed_parts = []
        
        for part in parts:
            if part.startswith('```') and part.endswith('```'):
                # 命中保护逻辑
                processed_parts.append(part)
            else:
                # 2.1 准则：仅处理非代码块区域
                # 将 2+ 空格变为 1
                temp = re.sub(r' {2,}', ' ', part)
                # 将 3+ 换行变为 2
                temp = re.sub(r'\n{3,}', '\n\n', temp)
                processed_parts.append(temp)
        
        return "".join(processed_parts)

class SafetyEnforcer:
    TIER2_PATCH = "\n\n[SYSTEM ENFORCEMENT]: You must respond ONLY in valid JSON format. Do not add any conversational preamble or postscript."

    @classmethod
    def apply(cls, request: StandardRequest, tier: ModelTier):
        if tier == ModelTier.TIER_2 and request.messages:
            # 遵循 2.2 准则：幂等性检查
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
