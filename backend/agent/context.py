from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any

def approx_tokens(text: str) -> int:
    """
    更精确的token估算：
    - 中文：约1.5个字符/token
    - 英文：约4个字符/token
    根据文本中中文字符的比例动态计算
    """
    if not text:
        return 0
    
    # 统计中文字符
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    total_chars = len(text)
    chinese_ratio = chinese_chars / total_chars if total_chars > 0 else 0
    
    # 混合计算
    if chinese_ratio > 0.3:
        # 中文为主
        return max(1, int(total_chars / 1.5))
    else:
        # 英文为主
        return max(1, total_chars // 4)

@dataclass
class ContextBudget:
    persona: int = 450
    state: int = 300
    memory: int = 900
    tool: int = 600
    max_total: int = 2200

class ContextAssembler:
    def __init__(self, budget: ContextBudget | None = None):
        self.budget = budget or ContextBudget()

    def assemble(self, persona: str, state: str, memory_cards: List[str], user_input: str) -> Dict[str, Any]:
        persona = self._trim(persona, self.budget.persona)
        state = self._trim(state, self.budget.state)

        trimmed_cards: List[str] = []
        mem_used = 0
        for c in memory_cards:
            t = approx_tokens(c)
            if mem_used + t > self.budget.memory:
                break
            trimmed_cards.append(c)
            mem_used += t

        return {
            "persona": persona,
            "state": state,
            "memory_cards": trimmed_cards,
            "user_input": user_input,
            "estimated_tokens": approx_tokens(persona) + approx_tokens(state) + mem_used + approx_tokens(user_input)
        }

    def _trim(self, text: str, max_tokens: int) -> str:
        if approx_tokens(text) <= max_tokens:
            return text
        max_chars = max_tokens * 4
        return text[:max_chars] + "…"
