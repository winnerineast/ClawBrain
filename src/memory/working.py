# Generated from design/memory_working.md v1.1
import time
import math
from typing import List, Dict, Any, Optional

class WorkingMemoryItem:
    def __init__(self, trace_id: str, content: str, timestamp: float = None):
        self.trace_id = trace_id
        self.content = content
        self.timestamp = timestamp or time.time()
        self.activation = 1.0

class WorkingMemory:
    """
    工作记忆实现。
    根据时间衰减和话题相关度动态管理消息驻留。
    """
    THRESHOLD = 0.3
    MAX_CAPACITY = 15
    DECAY_LAMBDA = 0.001 # 时间衰减常数

    def __init__(self):
        self.items: List[WorkingMemoryItem] = []

    def add_item(self, trace_id: str, content: str):
        # 初始注入
        new_item = WorkingMemoryItem(trace_id, content)
        self.items.append(new_item)
        self._refresh_activations(content)
        self._cleanup()

    def _refresh_activations(self, current_focus: str):
        """
        核心动力学算法：更新所有消息的激活值。
        A = TimeScore + RelevanceScore
        """
        now = time.time()
        for item in self.items:
            # 1. 计算时间远离度分值 (0.0 - 0.7)
            dt = now - item.timestamp
            time_score = 0.7 * math.exp(-self.DECAY_LAMBDA * dt)
            
            # 2. 计算话题相关度分值 (0.0 - 0.3)
            # 简化实现：通过关键词重合度
            rel_score = self._calculate_relevance(item.content, current_focus) * 0.3
            
            # 3. 综合激活值
            item.activation = time_score + rel_score

    def _calculate_relevance(self, past: str, current: str) -> float:
        if not past or not current: return 0.0
        # 简单的词频重叠
        words_past = set(past.lower().split())
        words_current = set(current.lower().split())
        common = words_past.intersection(words_current)
        if not words_current: return 0.0
        return len(common) / len(words_current)

    def _cleanup(self):
        """淘汰逻辑"""
        # 1. 移除低于阈值的
        self.items = [it for it in self.items if it.activation >= self.THRESHOLD]
        
        # 2. 超过物理容量时，移除激活值最低的
        if len(self.items) > self.MAX_CAPACITY:
            self.items.sort(key=lambda x: x.activation, reverse=True)
            self.items = self.items[:self.MAX_CAPACITY]

    def get_active_contents(self) -> List[str]:
        return [it.content for it in sorted(self.items, key=lambda x: x.timestamp)]
