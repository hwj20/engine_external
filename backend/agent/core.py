from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict
from .store import MemoryStore, SettingsStore
from .context import ContextAssembler, ContextBudget, approx_tokens
from .llm import OpenAICompatibleClient

logger = logging.getLogger(__name__)

DEFAULT_PERSONA = """你是一个终身陪伴型AI助手。风格：亲密、聪明、简洁、带一点俏皮。
规则：
- 默认输出短一些（150~250 tokens），除非用户明确要求展开。
- 重要决定前先给出简短方案与影响范围。
- 记忆要克制：只把长期稳定且对未来有用的信息写入长期记忆。
"""

# 最大保留的历史消息轮数（已弃用，改为基于token的动态计算）
MAX_HISTORY_TURNS = 10
# 对话历史的token预算（用于滑动窗口）
HISTORY_TOKEN_BUDGET = 1200  # 约300条消息的容量（中文平均6字/消息）

class AgentCore:
    def __init__(self, memory: MemoryStore, settings: SettingsStore):
        print("[AgentCore] Initializing AgentCore", flush=True)
        self.memory = memory
        self.settings = settings
        self.assembler = ContextAssembler(ContextBudget())
        # 会话历史记录：session_id -> List[{role, content}]
        self.conversation_history: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        print("[AgentCore] AgentCore initialized", flush=True)

    def _mode(self, user_message: str) -> str:
        task_kw = ["帮我", "做一个", "计划", "整理", "写", "生成", "安排", "安装", "代码", "方案"]
        mode = "task" if any(k in user_message for k in task_kw) else "chat"
        print(f"[AgentCore] Mode detection: {mode}", flush=True)
        return mode

    def _retrieve_memory_cards(self, user_message: str, mode: str) -> List[str]:
        print(f"[AgentCore] Retrieving memory cards for mode: {mode}", flush=True)
        episodes = self.memory.search_episodes_keyword(user_message, limit=5)
        if not episodes:
            print(f"[AgentCore] No keyword match episodes, getting recent ones", flush=True)
            episodes = self.memory.recent_episodes(limit=3)

        semantic = self.memory.get_semantic_top(limit=8)

        cards: List[str] = []
        for s in semantic:
            cards.append(f"[偏好] {s['key']}: {s['value']}")
        for e in episodes:
            cards.append(f"[事件] {e['title']}｜{e['detail']}（重要性{e['importance']:.2f}）")
        print(f"[AgentCore] Memory cards prepared: {len(cards)} cards", flush=True)
        return cards

    def _get_conversation_history(self, session_id: str, max_turns: int = 5) -> List[Dict[str, str]]:
        """获取最近的对话历史（基于token预算的滑动窗口）"""
        history = self.conversation_history.get(session_id, [])
        if not history:
            return []
        
        # 基于token预算动态选择历史消息
        # 从最近的消息开始，向前累加，直到达到token预算
        selected = []
        total_tokens = 0
        
        # 从后向前遍历（最近的消息在后）
        for msg in reversed(history):
            msg_tokens = approx_tokens(msg["content"])
            if total_tokens + msg_tokens > HISTORY_TOKEN_BUDGET:
                break
            selected.insert(0, msg)  # 插入到前面以保持顺序
            total_tokens += msg_tokens
        
        print(f"[AgentCore] Selected {len(selected)} messages ({total_tokens} tokens) from history for session: {session_id}", flush=True)
        logger.info(f"Selected {len(selected)} messages ({total_tokens} tokens) from conversation history")
        return selected

    def _add_to_history(self, session_id: str, role: str, content: str) -> None:
        """添加消息到会话历史"""
        self.conversation_history[session_id].append({"role": role, "content": content})
        # 限制历史记录长度
        if len(self.conversation_history[session_id]) > MAX_HISTORY_TURNS * 2:
            self.conversation_history[session_id] = self.conversation_history[session_id][-(MAX_HISTORY_TURNS * 2):]

    def clear_history(self, session_id: str) -> None:
        """清空会话历史"""
        if session_id in self.conversation_history:
            self.conversation_history[session_id] = []
            print(f"[AgentCore] Cleared history for session: {session_id}", flush=True)

    def chat(self, user_message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        session_id = session_id or "default"
        print(f"\n[AgentCore.chat] Processing: {user_message[:50]}... (session: {session_id})", flush=True)
        logger.info(f"Processing chat message: {user_message[:50]}...")
        mode = self._mode(user_message)
        logger.info(f"Detected mode: {mode}")
        memory_cards = self._retrieve_memory_cards(user_message, mode=mode)
        logger.info(f"Retrieved {len(memory_cards)} memory cards")

        state = f"当前模式: {mode}. 目标: 给出有帮助且简洁的回答。"
        print(f"[AgentCore] Assembling context...", flush=True)
        pack = self.assembler.assemble(
            persona=DEFAULT_PERSONA,
            state=state,
            memory_cards=memory_cards,
            user_input=user_message
        )
        print(f"[AgentCore] Context assembled", flush=True)

        st = self.settings.get()
        if not st.get("base_url") or not st.get("api_key") or not st.get("model"):
            print(f"[AgentCore] LLM settings not configured", flush=True)
            logger.warning("LLM settings not configured")
            return {
                "assistant_message": "我现在还没配置模型 API。请在 Settings 里填入 base_url / api_key / model，然后再和我聊天～",
                "mode": mode,
                "used_memory_cards": pack["memory_cards"],
            }

        print(f"[AgentCore] LLM settings found: base_url={st['base_url']}, model={st['model']}", flush=True)
        logger.info(f"LLM call with model: {st['model']}")
        client = OpenAICompatibleClient(
            base_url=st["base_url"],
            api_key=st["api_key"],
            model=st["model"]
        )

        # 构建system prompt：优先使用用户自定义的system_prompt，否则使用DEFAULT_PERSONA
        custom_system_prompt = st.get("system_prompt", "").strip()
        if custom_system_prompt:
            # 用户提供了自定义prompt，与默认persona和state合并
            system = custom_system_prompt + "\n\n" + pack["state"] + "\n\n" + "可用记忆卡片:\n" + "\n".join(pack["memory_cards"])
            print(f"[AgentCore] Using custom system prompt (len={len(custom_system_prompt)})", flush=True)
            logger.info(f"Using custom system prompt from settings")
        else:
            # 使用默认的persona和state
            system = pack["persona"] + "\n\n" + pack["state"] + "\n\n" + "可用记忆卡片:\n" + "\n".join(pack["memory_cards"])
            print(f"[AgentCore] Using default persona prompt", flush=True)
            logger.info(f"Using default persona prompt")
        
        # 获取最近的对话历史（基于token预算的滑动窗口）
        history = self._get_conversation_history(session_id)
        history_count = len(history) // 2
        print(f"[AgentCore] Including {history_count} turns of conversation history", flush=True)
        
        # 构建消息列表：system + history + current user message
        messages = [{"role": "system", "content": system}]
        messages.extend(history)
        messages.append({"role": "user", "content": pack["user_input"]})

        max_tokens = 220 if mode == "chat" else 400
        print(f"[AgentCore] Calling LLM with max_tokens={max_tokens}, total messages={len(messages)}", flush=True)

        try:
            ans = client.chat(messages, max_tokens=max_tokens, temperature=0.7 if mode=="chat" else 0.5)
            print(f"[AgentCore] LLM response received: {len(ans)} chars", flush=True)
            logger.info(f"LLM response received: {len(ans)} chars")
            
            # 保存对话历史
            self._add_to_history(session_id, "user", user_message)
            self._add_to_history(session_id, "assistant", ans)
            print(f"[AgentCore] Conversation history updated for session: {session_id}", flush=True)
        except Exception as e:
            print(f"[AgentCore] LLM call failed: {type(e).__name__}: {e}", flush=True)
            logger.error(f"LLM call failed: {type(e).__name__}: {e}")
            ans = f"调用模型失败了：{type(e).__name__}: {e}"

        print(f"[AgentCore] Writing to memory if needed...", flush=True)
        self._light_memory_write(user_message)

        print(f"[AgentCore.chat] Returning response\n", flush=True)
        return {
            "assistant_message": ans,
            "mode": mode,
            "used_memory_cards": pack["memory_cards"],
        }

    def _light_memory_write(self, user_message: str) -> None:
        markers = ["我喜欢", "我不喜欢", "我希望你", "以后都", "从现在起"]
        if any(m in user_message for m in markers):
            print(f"[AgentCore] Memory markers detected, saving to semantic memory", flush=True)
            key = f"pref_{abs(hash(user_message)) % 10_000_000}"
            self.memory.upsert_semantic(key, user_message[:200], confidence=0.6)
        else:
            print(f"[AgentCore] No memory markers in message", flush=True)
