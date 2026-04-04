# Generated from design/gateway.md v1.7
import re
from typing import List
from src.models import Message, StandardRequest
from src.scout import ModelTier

class WhitespaceCompressor:
    """
    负责对文本进行压缩，剔除冗余空格和换行。
    必须保护 ` ` ` 代码块内的缩进不被破坏。
    """
    @staticmethod
    def compress(text: str) -> str:
        if not text:
            return text
        
        # 将文本分割为“普通文本”和“代码块”
        parts = re.split(r'((` ` `[\s\S]*?` ` `))', text)
        processed_parts = []
        
        for part in parts:
            if part.startswith('` ` `'):
                # 保护代码块
                processed_parts.append(part)
            else:
                # 压缩普通文本：将连续空格(2个以上)替换为1个，连续换行(3个以上)替换为2个
                temp = re.sub(r' {2,}', ' ', part)
                temp = re.sub(r'\n{3,}', '\n\n', temp)
                processed_parts.append(temp)
        
        return "".join(processed_parts)

class SafetyEnforcer:
    """
    针对不同层级的模型，动态增强指令稳定性。
    """
    TIER2_PATCH = "\n\n[SYSTEM ENFORCEMENT]: You must respond ONLY in valid JSON format. Do not add any conversational preamble or postscript."

    @classmethod
    def apply(cls, request: StandardRequest, tier: ModelTier):
        if tier == ModelTier.TIER_2:
            # 在 System Prompt 或第一条 User 消息后注入补丁
            if request.messages:
                request.messages[0].content += cls.TIER2_PATCH
        return request

class Pipeline:
    def __init__(self):
        self.compressor = WhitespaceCompressor()
        self.enforcer = SafetyEnforcer()

    def run(self, request: StandardRequest, tier: ModelTier) -> StandardRequest:
        # 1. 压缩所有消息内容
        for msg in request.messages:
            if msg.content:
                msg.content = self.compressor.compress(msg.content)
        
        # 2. 执行安全性增强
        request = self.enforcer.apply(request, tier)
        
        return request
