# Generated from design/memory_working.md v1.2
import time
import math
from typing import List

class WorkingMemoryItem:
    def __init__(self, trace_id: str, content: str, timestamp: float = None):
        self.trace_id = trace_id
        self.content = content
        self.timestamp = timestamp or time.time()
        self.activation = 1.0

class WorkingMemory:
    """
    ClawBrain 工作记忆。
    基于时间衰减与话题相关度的高保真动力学模型。
    """
    THRESHOLD = 0.3
    MAX_CAPACITY = 15
    DECAY_LAMBDA = 0.001

    def __init__(self):
        self.items: List[WorkingMemoryItem] = []

    def add_item(self, trace_id: str, content: str):
        new_item = WorkingMemoryItem(trace_id, content)
        self.items.append(new_item)
        self._refresh_activations(content)
        self._cleanup()

    def _refresh_activations(self, current_focus: str):
        now = time.time()
        for item in self.items:
            dt = max(0, now - item.timestamp)
            time_score = 0.7 * math.exp(-self.DECAY_LAMBDA * dt)
            
            rel_score = self._calculate_relevance(item.content, current_focus) * 0.3
            
            item.activation = time_score + rel_score

    def _calculate_relevance(self, past: str, current: str) -> float:
        if not past or not current: return 0.0
        words_past = set(past.lower().split())
        words_current = set(current.lower().split())
        if not words_current: return 0.0
        
        common = words_past.intersection(words_current)
        return len(common) / len(words_current)

    def _cleanup(self):
        self.items = [it for it in self.items if it.activation >= self.THRESHOLD]
        if len(self.items) > self.MAX_CAPACITY:
            self.items.sort(key=lambda x: x.activation, reverse=True)
            self.items = self.items[:self.MAX_CAPACITY]

    def get_active_contents(self) -> List[str]:
        return [it.content for it in sorted(self.items, key=lambda x: x.timestamp)]
