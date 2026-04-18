# Generated from design/memory_working.md v1.4
import time
import math
from typing import List, Dict, Any, Tuple

class WorkingMemoryItem:
    def __init__(self, trace_id: str, content: str, timestamp: float = None):
        self.trace_id = trace_id
        self.content = content
        self.timestamp = timestamp or time.time()
        self.activation = 1.0
        # Audit derivation trace
        self.last_derivation = ""

class WorkingMemory:
    """
    ClawBrain Working Memory.
    Implements a dual-factor dynamics model with mathematical transparency.
    """
    THRESHOLD = 0.3
    MAX_CAPACITY = 15
    DECAY_LAMBDA = 0.001

    def __init__(self):
        self.items: List[WorkingMemoryItem] = []

    def add_item(self, *args, **kwargs):
        """
        Supports:
          1. add_item(WorkingMemoryItem(...))
          2. add_item(trace_id, content) [Legacy]
        """
        if len(args) == 1 and isinstance(args[0], WorkingMemoryItem):
            item = args[0]
        elif len(args) == 2:
            item = WorkingMemoryItem(trace_id=args[0], content=args[1])
        elif "item" in kwargs:
            item = kwargs["item"]
        else:
            raise TypeError("WorkingMemory.add_item() expects either a WorkingMemoryItem or (id, content)")

        # 1. Initial Injection
        self.items.append(item)
        
        # 2. Refresh all activation values using the content of the new item
        self._refresh_activations(item.content)
        
        # 3. Perform cleanup according to Spec 2.3
        self._cleanup()

    def _refresh_activations(self, current_focus: str):
        now = time.time()
        current_words = set(current_focus.lower().split())
        current_len = len(current_words) if current_words else 1

        for item in self.items:
            # --- Rule 2.2: TimeScore Calculation ---
            dt = max(0, now - item.timestamp)
            time_score = 0.7 * math.exp(-self.DECAY_LAMBDA * dt)
            
            # --- Rule 2.2: RelevanceScore Calculation ---
            item_words = set(item.content.lower().split())
            common = item_words.intersection(current_words)
            rel_score = 0.3 * (len(common) / current_len)
            
            # Update activation
            item.activation = time_score + rel_score
            
            # --- Rule 3.1 & 3.2: Record mathematical derivation trace ---
            item.last_derivation = (
                f"T_diff: {dt:.0f}s | Calc: 0.7 * exp(-0.001*{dt:.0f}) = {time_score:.4f} ; "
                f"Match: {common} | Rel_Score: 0.3 * ({len(common)}/{current_len}) = {rel_score:.4f} ; "
                f"Total: {item.activation:.4f}"
            )

    def _cleanup(self):
        # Rule 2.3: Threshold Eviction
        self.items = [it for it in self.items if it.activation >= self.THRESHOLD]
        
        # Rule 2.3: Capacity Eviction
        if len(self.items) > self.MAX_CAPACITY:
            self.items.sort(key=lambda x: x.activation, reverse=True)
            self.items = self.items[:self.MAX_CAPACITY]

    def get_active_contents(self) -> List[str]:
        # Return active contents sorted by timestamp
        return [it.content for it in sorted(self.items, key=lambda x: x.timestamp)]
