from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any

def approx_tokens(text: str) -> int:
    # MVP approximation: ~4 chars/token (English). Chinese differs; heuristic only.
    return 0 if not text else max(1, len(text) // 4)

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
