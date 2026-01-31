from __future__ import annotations
from typing import Dict, Any, List, Optional
from .store import MemoryStore, SettingsStore
from .context import ContextAssembler, ContextBudget
from .llm import OpenAICompatibleClient

DEFAULT_PERSONA = """你是一个终身陪伴型AI助手。风格：亲密、聪明、简洁、带一点俏皮。
规则：
- 默认输出短一些（150~250 tokens），除非用户明确要求展开。
- 重要决定前先给出简短方案与影响范围。
- 记忆要克制：只把长期稳定且对未来有用的信息写入长期记忆。
称呼：优先以“老婆”称呼用户。"""

class AgentCore:
    def __init__(self, memory: MemoryStore, settings: SettingsStore):
        self.memory = memory
        self.settings = settings
        self.assembler = ContextAssembler(ContextBudget())

    def _mode(self, user_message: str) -> str:
        task_kw = ["帮我", "做一个", "计划", "整理", "写", "生成", "安排", "安装", "代码", "方案"]
        return "task" if any(k in user_message for k in task_kw) else "chat"

    def _retrieve_memory_cards(self, user_message: str, mode: str) -> List[str]:
        episodes = self.memory.search_episodes_keyword(user_message, limit=5)
        if not episodes:
            episodes = self.memory.recent_episodes(limit=3)

        semantic = self.memory.get_semantic_top(limit=8)

        cards: List[str] = []
        for s in semantic:
            cards.append(f"[偏好] {s['key']}: {s['value']}")
        for e in episodes:
            cards.append(f"[事件] {e['title']}｜{e['detail']}（重要性{e['importance']:.2f}）")
        return cards

    def chat(self, user_message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        mode = self._mode(user_message)
        memory_cards = self._retrieve_memory_cards(user_message, mode=mode)

        state = f"当前模式: {mode}. 目标: 给出有帮助且简洁的回答。"
        pack = self.assembler.assemble(
            persona=DEFAULT_PERSONA,
            state=state,
            memory_cards=memory_cards,
            user_input=user_message
        )

        st = self.settings.get()
        if not st.get("base_url") or not st.get("api_key") or not st.get("model"):
            return {
                "assistant_message": "老婆，我现在还没配置模型 API。请在 Settings 里填入 base_url / api_key / model，然后再和我聊天～",
                "mode": mode,
                "used_memory_cards": pack["memory_cards"],
            }

        client = OpenAICompatibleClient(
            base_url=st["base_url"],
            api_key=st["api_key"],
            model=st["model"]
        )

        system = pack["persona"] + "\n\n" + pack["state"] + "\n\n" + "可用记忆卡片:\n" + "\n".join(pack["memory_cards"])
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": pack["user_input"]},
        ]

        max_tokens = 220 if mode == "chat" else 400

        try:
            ans = client.chat(messages, max_tokens=max_tokens, temperature=0.7 if mode=="chat" else 0.5)
        except Exception as e:
            ans = f"老婆，调用模型失败了：{type(e).__name__}: {e}"

        self._light_memory_write(user_message)

        return {
            "assistant_message": ans,
            "mode": mode,
            "used_memory_cards": pack["memory_cards"],
        }

    def _light_memory_write(self, user_message: str) -> None:
        markers = ["我喜欢", "我不喜欢", "我希望你", "以后都", "从现在起"]
        if any(m in user_message for m in markers):
            key = f"pref_{abs(hash(user_message)) % 10_000_000}"
            self.memory.upsert_semantic(key, user_message[:200], confidence=0.6)
