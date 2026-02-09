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
# 压缩时保留的对话轮数（保持最近的上下文，避免模型漂移）
COMPRESSION_CONTEXT_RETENTION_TURNS = 2  # 保留最后2轮对话（每轮=user+assistant）

class AgentCore:
    def __init__(self, memory: MemoryStore, settings: SettingsStore):
        print("[AgentCore] Initializing AgentCore", flush=True)
        self.memory = memory
        self.settings = settings
        self.assembler = ContextAssembler(ContextBudget())
        # 会话历史记录：session_id -> List[{role, content}]
        self.conversation_history: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        # 压缩后的历史摘要：session_id -> str
        self.compressed_history: Dict[str, str] = defaultdict(str)
        # 压缩状态：session_id -> {compressing: bool, last_compressed_at: int}
        self.compression_state: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"compressing": False, "last_compressed_at": 0})
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

    def _get_history_text(self, session_id: str, strategy: str, compression_threshold: int, compression_target: int, client: OpenAICompatibleClient) -> str:
        """
        根据策略获取对话历史文本。
        - compression: 使用智能压缩，超过阈值时调用LLM压缩
        - sliding_window: 使用传统滑动窗口
        返回格式化的历史文本（不含"对话历史:"前缀）
        """
        if strategy == "compression":
            return self._get_compressed_history_text(session_id, compression_threshold, compression_target, client)
        else:
            return self._get_sliding_window_history_text(session_id)

    def _get_sliding_window_history_text(self, session_id: str) -> str:
        """滑动窗口策略：返回最近的对话历史文本"""
        history = self._get_conversation_history(session_id)
        if not history:
            return ""
        lines = []
        for msg in history:
            role_label = "用户" if msg["role"] == "user" else "助手"
            lines.append(f"{role_label}: {msg['content']}")
        return "\n".join(lines)

    def _get_compressed_history_text(self, session_id: str, threshold: int, target: int, client: OpenAICompatibleClient) -> str:
        """
        智能压缩策略（改进版）：
        1. 已压缩摘要 + 当前未压缩对话 = 完整历史
        2. 当完整历史token数 > threshold 时，触发压缩
        3. 压缩时保留最后N轮对话作为热上下文，避免模型漂移
        4. 压缩失败时降级到滑动窗口
        """
        compressed = self.compressed_history.get(session_id, "")
        current_msgs = self.conversation_history.get(session_id, [])

        if not current_msgs and not compressed:
            return ""

        # 分离消息：保留最后的热上下文，其余用于压缩
        retention_count = COMPRESSION_CONTEXT_RETENTION_TURNS * 2  # 每轮包含user+assistant
        if len(current_msgs) > retention_count:
            msgs_to_compress = current_msgs[:-retention_count]
            msgs_to_retain = current_msgs[-retention_count:]
        else:
            msgs_to_compress = []
            msgs_to_retain = current_msgs

        # 格式化用于压缩的对话
        compress_lines = []
        for msg in msgs_to_compress:
            role_label = "用户" if msg["role"] == "user" else "助手"
            compress_lines.append(f"{role_label}: {msg['content']}")
        compress_text = "\n".join(compress_lines)

        # 格式化保留的热上下文对话
        retain_lines = []
        for msg in msgs_to_retain:
            role_label = "用户" if msg["role"] == "user" else "助手"
            retain_lines.append(f"{role_label}: {msg['content']}")
        retain_text = "\n".join(retain_lines)

        # 组合完整历史用于计算token数
        if compressed and compress_text:
            full_history = f"[之前的对话摘要]\n{compressed}\n\n[早期对话]\n{compress_text}"
        elif compressed:
            full_history = f"[之前的对话摘要]\n{compressed}"
        else:
            full_history = compress_text

        # 计算token数
        total_tokens = approx_tokens(full_history)
        print(f"[AgentCore] Compression check: {total_tokens} tokens (retained: {len(msgs_to_retain)} msgs, threshold: {threshold})", flush=True)

        if total_tokens <= threshold:
            # 未超过阈值，直接返回完整历史（摘要 + 热上下文）
            result_parts = []
            if compressed:
                result_parts.append(f"[之前的对话摘要]\n{compressed}")
            if retain_text:
                result_parts.append(f"[最近的对话]\n{retain_text}")
            return "\n\n".join(result_parts)

        # 超过阈值，触发压缩
        print(f"[AgentCore] Triggering compression: {total_tokens} > {threshold}, target: {target}, retaining {len(msgs_to_retain)} messages", flush=True)
        logger.info(f"Compression triggered: {total_tokens} tokens > threshold {threshold}, retaining {len(msgs_to_retain)} recent messages")

        if self.compression_state[session_id]["compressing"]:
            print(f"[AgentCore] Compression already in progress, using sliding window fallback", flush=True)
            return self._get_sliding_window_history_text(session_id)

        self.compression_state[session_id]["compressing"] = True
        try:
            # 只压缩早期部分（不包括热上下文）
            compressed_result = self._call_compression(full_history, target, client)
            if compressed_result:
                self.compressed_history[session_id] = compressed_result
                # 保留最后的热上下文消息，清空早期部分
                self.conversation_history[session_id] = msgs_to_retain
                import time
                self.compression_state[session_id]["last_compressed_at"] = int(time.time())
                print(f"[AgentCore] Compression successful: {total_tokens} -> ~{approx_tokens(compressed_result)} tokens, retained {len(msgs_to_retain)} messages", flush=True)
                logger.info(f"Compression successful: {total_tokens} -> ~{approx_tokens(compressed_result)} tokens, retained {len(msgs_to_retain)} recent messages")
                
                # 返回压缩后的历史：摘要 + 保留的热上下文
                result_parts = [f"[对话摘要]\n{compressed_result}"]
                if retain_text:
                    result_parts.append(f"[最近的对话]\n{retain_text}")
                return "\n\n".join(result_parts)
            else:
                print(f"[AgentCore] Compression returned empty, using sliding window fallback", flush=True)
                return self._get_sliding_window_history_text(session_id)
        except Exception as e:
            print(f"[AgentCore] Compression failed: {e}, using sliding window fallback", flush=True)
            logger.error(f"Compression failed: {e}, falling back to sliding window")
            return self._get_sliding_window_history_text(session_id)
        finally:
            self.compression_state[session_id]["compressing"] = False

    def _call_compression(self, history_text: str, target_tokens: int, client: OpenAICompatibleClient) -> str:
        """调用LLM进行对话历史压缩"""
        compression_prompt = f"""请将以下对话历史压缩到{target_tokens} tokens以内，要求：
1. 保留用户的核心需求、偏好和重要决策
2. 保留未完成的任务和关键上下文信息
3. 保留重要的技术细节和代码逻辑
4. 去除冗余的寒暄和重复内容
5. 使用简洁但完整的表达方式

对话历史：
{history_text}

压缩后的对话摘要："""

        messages = [
            {"role": "system", "content": "你是一个对话历史压缩助手。只输出压缩后的摘要，不要添加任何额外说明。"},
            {"role": "user", "content": compression_prompt},
        ]

        print(f"[AgentCore] Calling LLM for compression (target: {target_tokens} tokens)...", flush=True)
        # 使用较低的temperature确保压缩稳定
        result, _ = client.chat(messages, max_tokens=target_tokens + 100, temperature=0.3)
        return result.strip()

    def _add_to_history(self, session_id: str, role: str, content: str) -> None:
        """添加消息到会话历史"""
        self.conversation_history[session_id].append({"role": role, "content": content})
        # 限制历史记录长度
        if len(self.conversation_history[session_id]) > MAX_HISTORY_TURNS * 2:
            self.conversation_history[session_id] = self.conversation_history[session_id][-(MAX_HISTORY_TURNS * 2):]

    def clear_history(self, session_id: str) -> None:
        """清空会话历史（包括压缩摘要）"""
        if session_id in self.conversation_history:
            self.conversation_history[session_id] = []
        if session_id in self.compressed_history:
            self.compressed_history[session_id] = ""
        if session_id in self.compression_state:
            self.compression_state[session_id] = {"compressing": False, "last_compressed_at": 0}
        print(f"[AgentCore] Cleared history and compression state for session: {session_id}", flush=True)

    def chat(self, user_message: str, session_id: Optional[str] = None, memory_context: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        session_id = session_id or "default"
        print(f"\n[AgentCore.chat] Processing: {user_message[:50]}... (session: {session_id})", flush=True)
        logger.info(f"Processing chat message: {user_message[:50]}...")
        mode = self._mode(user_message)
        logger.info(f"Detected mode: {mode}")
        
        # 使用新的记忆上下文（如果提供）
        memory_cards: List[str] = []
        if memory_context:
            print(f"[AgentCore.chat] memory_context keys: {list(memory_context.keys())}", flush=True)
            if memory_context.get("user_info"):
                print(f"[AgentCore.chat] Adding user_info: {memory_context['user_info'][:50]}...", flush=True)
                memory_cards.append(memory_context["user_info"])
            if memory_context.get("core_memories"):
                print(f"[AgentCore.chat] Adding core_memories: {memory_context['core_memories'][:50]}...", flush=True)
                memory_cards.append(memory_context["core_memories"])
            if memory_context.get("relevant_memories"):
                print(f"[AgentCore.chat] Adding relevant_memories: {memory_context['relevant_memories'][:50]}...", flush=True)
                memory_cards.append(memory_context["relevant_memories"])
            else:
                print(f"[AgentCore.chat] No relevant_memories found in memory_context", flush=True)
        else:
            print(f"[AgentCore.chat] memory_context is None, using fallback", flush=True)
            # 回退到旧的记忆检索方式
            memory_cards = self._retrieve_memory_cards(user_message, mode=mode)
        
        print(f"[AgentCore.chat] Final memory_cards count: {len(memory_cards)}", flush=True)
        for i, card in enumerate(memory_cards):
            print(f"  Card {i+1}: {card[:60]}...", flush=True)
        logger.info(f"Memory context prepared: {len(memory_cards)} sections")

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
        
        # 获取max_input_tokens设置
        max_input_tokens = st.get("max_input_tokens", 2000)
        
        client = OpenAICompatibleClient(
            base_url=st["base_url"],
            api_key=st["api_key"],
            model=st["model"],
            max_input_tokens=max_input_tokens
        )

        # === 构建消息（针对 prompt caching 优化） ===
        # System prompt: 人格 + 核心记忆 + 日期（稳定内容，cache 命中率高）
        # User message:  对话历史 + 动态记忆 + 当前输入（历史前半段 hit cache）

        # 1) 组装 system prompt（稳定部分）
        custom_system_prompt = st.get("system_prompt", "").strip()
        persona_part = custom_system_prompt if custom_system_prompt else pack["persona"]

        # 核心记忆（稳定）: user_info + core_memories
        core_memory_parts: List[str] = []
        if memory_context:
            if memory_context.get("user_info"):
                core_memory_parts.append(memory_context["user_info"])
            if memory_context.get("core_memories"):
                core_memory_parts.append(memory_context["core_memories"])
        core_memory_text = "\n".join(core_memory_parts) if core_memory_parts else ""

        # 日期（一天内不变）
        from datetime import datetime
        date_text = f"当前日期: {datetime.now().strftime('%Y-%m-%d %A')}"

        system_sections = [persona_part, pack["state"]]
        if core_memory_text:
            system_sections.append("核心记忆:\n" + core_memory_text)
        system_sections.append(date_text)
        system = "\n\n".join(s for s in system_sections if s)

        print(f"[AgentCore] System prompt assembled (persona + core memory + date)", flush=True)
        logger.info(f"System prompt: persona={'custom' if custom_system_prompt else 'default'}, core_memory={len(core_memory_parts)} sections")

        # 2) 组装 user message（对话历史 + 动态记忆 + 当前输入）
        #    对话历史放在最前面，前半段内容稳定 → cache 命中
        history_strategy = st.get("history_strategy", "compression")
        compression_threshold = st.get("compression_threshold", 1000)
        compression_target = st.get("compression_target", 200)
        print(f"[AgentCore] History strategy: {history_strategy}, threshold: {compression_threshold}, target: {compression_target}", flush=True)

        history_text = self._get_history_text(
            session_id, history_strategy, compression_threshold, compression_target, client
        )

        user_sections: List[str] = []

        # 对话历史（放最前，利用 prefix caching）
        if history_text:
            user_sections.append("对话历史:\n" + history_text)

        # 动态记忆（relevant_memories，每次可能不同）
        dynamic_memory_parts: List[str] = []
        if memory_context and memory_context.get("relevant_memories"):
            dynamic_memory_parts.append(memory_context["relevant_memories"])
        # 如果没有 memory_context，用旧的 memory_cards 中非核心部分作为动态记忆
        if not memory_context and pack["memory_cards"]:
            dynamic_memory_parts.extend(pack["memory_cards"])
        if dynamic_memory_parts:
            user_sections.append("相关记忆:\n" + "\n".join(dynamic_memory_parts))

        # 当前用户输入（放最后）
        user_sections.append(pack["user_input"])

        user_content = "\n\n".join(user_sections)

        # 构建最终消息列表：只有 system + user 两条
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]

        # 从设置中获取max_output_tokens，如果未设置则使用默认值
        max_output_tokens = st.get("max_output_tokens", 800)
        if mode == "chat":
            # 对于chat模式，使用较小的输出限制，但不小于默认值
            max_output_tokens = min(max_output_tokens, 400)
        
        # 从设置中获取temperature
        temperature = st.get("temperature", 0.7)
        
        # 计算system prompt的token数
        system_prompt_tokens = approx_tokens(system)
        
        print(f"[AgentCore] Calling LLM with max_tokens={max_output_tokens}, temperature={temperature}, system_tokens={system_prompt_tokens}, total messages={len(messages)}", flush=True)
        
        # 打印发送给LLM的完整chat completion请求
        print(f"\n{'='*80}", flush=True)
        print(f"[AgentCore] Chat Completion Request:", flush=True)
        print(f"{'='*80}", flush=True)
        print(f"Model: {st['model']}", flush=True)
        print(f"Max Tokens: {max_output_tokens}", flush=True)
        print(f"Temperature: {temperature}", flush=True)
        print(f"Messages Count: {len(messages)}", flush=True)
        print(f"{'-'*80}", flush=True)
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            content_preview = content[:200] + "..." if len(content) > 200 else content
            print(f"Message {i+1} ({role}): {content_preview}", flush=True)
        print(f"{'-'*80}", flush=True)
        print(f"Full messages to be sent:", flush=True)
        import json
        print(json.dumps(messages, ensure_ascii=False, indent=2), flush=True)
        print(f"{'='*80}\n", flush=True)

        token_info = {}
        try:
            ans, token_info = client.chat(messages, max_tokens=max_output_tokens, temperature=temperature)
            token_info["system_prompt_tokens"] = system_prompt_tokens
            print(f"[AgentCore] LLM response received: {len(ans)} chars, tokens: {token_info}", flush=True)
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
            "token_info": token_info,
            "history_strategy": history_strategy,
            "compression_state": {
                "has_compressed": bool(self.compressed_history.get(session_id, "")),
                "compressed_tokens": approx_tokens(self.compressed_history.get(session_id, "")),
                "current_messages": len(self.conversation_history.get(session_id, [])),
            },
        }

    def _light_memory_write(self, user_message: str) -> None:
        markers = ["我喜欢", "我不喜欢", "我希望你", "以后都", "从现在起"]
        if any(m in user_message for m in markers):
            print(f"[AgentCore] Memory markers detected, saving to semantic memory", flush=True)
            key = f"pref_{abs(hash(user_message)) % 10_000_000}"
            self.memory.upsert_semantic(key, user_message[:200], confidence=0.6)
        else:
            print(f"[AgentCore] No memory markers in message", flush=True)
