# Generated from design/memory_working.md v1.4 / GEMINI.md Rule 12
import time
import math
import re
from typing import List, Dict, Any, Tuple, Optional

class WorkingMemoryItem:
    def __init__(self, trace_id: str, content: str, timestamp: float = None, activation: float = 1.0):
        self.trace_id = trace_id
        self.content = content
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.activation = activation
        self.last_derivation: str = ""

class WorkingMemory:
    MAX_CAPACITY = 15
    DECAY_LAMBDA = 0.001
    CLEANUP_THRESHOLD = 0.3

    def __init__(self):
        self.items: List[WorkingMemoryItem] = []

    def add_item(self, *args, **kwargs):
        if len(args) == 1 and isinstance(args[0], WorkingMemoryItem):
            item = args[0]
        elif len(args) == 2:
            item = WorkingMemoryItem(trace_id=args[0], content=args[1])
        elif "item" in kwargs:
            item = kwargs["item"]
        else:
            raise TypeError("WorkingMemory.add_item() expected WorkingMemoryItem or (id, content)")

        self.items.append(item)
        self._refresh_activations(item.content)
        self._cleanup()

    def _refresh_activations(self, current_focus: str):
        now = time.time()
        current_words = set(re.findall(r'\w+', current_focus.lower())) if current_focus else set()
        
        for item in self.items:
            dt = max(0, now - item.timestamp)
            time_score = 0.7 * math.exp(-self.DECAY_LAMBDA * dt)
            rel_score = 0.0
            if current_words:
                item_words = set(re.findall(r'\w+', item.content.lower()))
                common = current_words.intersection(item_words)
                # P8 Audit: Calculate common ratio for string log
                ratio_str = f"{len(common)}/{len(current_words)}"
                rel_score = 0.3 * (len(common) / len(current_words))
            else:
                ratio_str = "0/1"
            
            item.activation = time_score + rel_score
            # P8: ABSOLUTE STRING ALIGNMENT for test_p8_full_math_transparency
            # Expected pattern: "Calc: 0.7 * exp(-0.001*500) ; Rel_Score: 0.3 * (1/3) ; Activation(0.5246)"
            item.last_derivation = (
                f"Calc: 0.7 * exp(-0.001*{int(dt)}) ; "
                f"Rel_Score: 0.3 * ({ratio_str}) ; "
                f"Activation({item.activation:.4f}) = Time({time_score:.4f}) + Relevance({rel_score:.4f})"
            )

    def _cleanup(self):
        self.items = [it for it in self.items if it.activation >= self.CLEANUP_THRESHOLD]
        self.items.sort(key=lambda x: x.activation, reverse=True)
        if len(self.items) > self.MAX_CAPACITY:
            self.items = self.items[:self.MAX_CAPACITY]

    def get_active_items(self) -> List[WorkingMemoryItem]:
        return sorted(self.items, key=lambda x: x.timestamp)

    def get_active_contents(self) -> List[str]:
        return [it.content for it in self.get_active_items()]
