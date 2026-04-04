# Generated from design/memory_working.md v1.3
import time
import math
from typing import List, Dict, Any, Tuple

class WorkingMemoryItem:
    def __init__(self, trace_id: str, content: str, timestamp: float = None):
        self.trace_id = trace_id
        self.content = content
        self.timestamp = timestamp or time.time()
        self.activation = 1.0
        # 记录计算轨迹
        self.last_derivation = ""

class WorkingMemory:
    """
    ClawBrain 工作记忆。
    实现具备数学透明度的双因子动力学模型。
    """
    THRESHOLD = 0.3
    MAX_CAPACITY = 15
    DECAY_LAMBDA = 0.001

    def __init__(self):
        self.items: List[WorkingMemoryItem] = []

    def add_item(self, trace_id: str, content: str):
        # 1. 初始注入
        new_item = WorkingMemoryItem(trace_id, content)
        self.items.append(new_item)
        
        # 2. 全量刷新激活值
        self._refresh_activations(content)
        
        # 3. 按照规格书 2.3 执行清理
        self._cleanup()

    def _refresh_activations(self, current_focus: str):
        now = time.time()
        current_words = set(current_focus.lower().split())
        current_len = len(current_words) if current_words else 1

        for item in self.items:
            # --- 2.2 准则：TimeScore 计算 ---
            dt = max(0, now - item.timestamp)
            time_score = 0.7 * math.exp(-self.DECAY_LAMBDA * dt)
            
            # --- 2.2 准则：RelevanceScore 计算 ---
            item_words = set(item.content.lower().split())
            common = item_words.intersection(current_words)
            rel_score = 0.3 * (len(common) / current_len)
            
            # 更新激活值
            item.activation = time_score + rel_score
            
            # --- 3.1 & 3.2 准则：记录数学推导轨迹 ---
            item.last_derivation = (
                f"T_diff: {dt:.0f}s | Calc: 0.7 * exp(-0.001*{dt:.0f}) = {time_score:.4f} ; "
                f"Match: {common} | Rel_Score: 0.3 * ({len(common)}/{current_len}) = {rel_score:.4f} ; "
                f"Total: {item.activation:.4f}"
            )

    def _cleanup(self):
        # 2.3 准则：阈值清理
        self.items = [it for it in self.items if it.activation >= self.THRESHOLD]
        
        # 2.3 准则：容量挤出
        if len(self.items) > self.MAX_CAPACITY:
            self.items.sort(key=lambda x: x.activation, reverse=True)
            self.items = self.items[:self.MAX_CAPACITY]

    def get_active_contents(self) -> List[str]:
        # 返回按时间排序的活跃内容
        return [it.content for it in sorted(self.items, key=lambda x: x.timestamp)]
