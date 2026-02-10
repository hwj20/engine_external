import json
import logging
import requests
from typing import Dict, List, Tuple, Any

logger = logging.getLogger(__name__)

class OpenAICompatibleClient:
    '''
    Minimal OpenAI-compatible chat completions client (HTTP).
    Endpoint: {base_url}/v1/chat/completions
    '''
    def __init__(self, base_url: str, api_key: str, model: str, max_input_tokens: int = 2000):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_input_tokens = max_input_tokens

    def _estimate_tokens(self, text: str, message_count: int) -> int:
        """
        估算文本的token数量。
        中文约1.5字符/token，英文约4字符/token，每条消息额外约4个token
        """
        if not text:
            return message_count * 4
        
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        total_chars = len(text)
        chinese_ratio = chinese_chars / total_chars if total_chars > 0 else 0
        
        if chinese_ratio > 0.3:
            tokens = int(total_chars / 1.5)
        else:
            tokens = int(total_chars / 4)
        
        return tokens + message_count * 4

    def _apply_token_budget(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        应用token预算的滑动窗口策略。
        保护system prompt（稳定内容），对user message的内容做动态截断。
        """
        if len(messages) < 2:
            return messages
        
        # 分离system和user消息
        system_msg = messages[0]  # 第一条通常是system
        user_msg = messages[-1]   # 最后一条是user
        
        # 先计算不截断的budget
        system_tokens = self._estimate_tokens(system_msg.get("content", ""), 1)
        user_content = user_msg.get("content", "")
        total_current = system_tokens + self._estimate_tokens(user_content, 1)
        
        if total_current <= self.max_input_tokens:
            logger.info(f"Token budget OK: {total_current}/{self.max_input_tokens}")
            return messages
        
        logger.warning(f"Token budget exceeded: {total_current}/{self.max_input_tokens}, applying sliding window to user message...")
        
        # 需要缩减user message的内容
        # 查找"对话历史:\n"的分界点，用来截断对话历史部分
        content_lower = user_content.lower()
        history_marker = "对话历史:"
        
        if history_marker in user_content:
            # 将user content分为三部分：历史 + 其他部分
            parts = user_content.split(history_marker, 1)
            before_history = parts[0] + history_marker
            history_and_rest = history_marker + parts[1] if len(parts) > 1 else ""
            
            # 在"相关记忆:"或直接用户输入处分割
            rest_marker = "相关记忆:"
            if rest_marker in parts[1]:
                history_part, rest_part = parts[1].split(rest_marker, 1)
                rest_content = rest_marker + rest_part
            else:
                history_part = parts[1]
                rest_content = ""
            
            # 计算固定部分的token（system + before_history + rest_content）
            fixed_tokens = system_tokens + self._estimate_tokens(before_history, 0) + self._estimate_tokens(rest_content, 0)
            budget_for_history = self.max_input_tokens - fixed_tokens - 16  # 留16个token的buffer
            
            if budget_for_history > 0:
                # 从最后向前截断历史（保留最近的对话）
                history_lines = history_part.strip().split("\n")
                selected_lines = []
                line_tokens = 0
                
                for line in reversed(history_lines):
                    line_t = self._estimate_tokens(line, 0)
                    if line_tokens + line_t > budget_for_history:
                        break
                    selected_lines.insert(0, line)
                    line_tokens += line_t
                
                truncated_history = "\n".join(selected_lines)
                if truncated_history != history_part:
                    logger.warning(f"Sliding window: history truncated to {line_tokens} tokens ({len(selected_lines)} lines)")
                
                # 重组user content
                truncated_user_content = before_history + "\n" + truncated_history + "\n" + rest_content
                user_msg["content"] = truncated_user_content
            else:
                logger.warning(f"User message too large even without history, keeping as is")
        
        return [system_msg, user_msg]

    def chat(self, messages: List[Dict[str, str]], max_tokens: int = 300, temperature: float = 0.6) -> Tuple[str, Dict[str, Any]]:
        """
        Send chat completion request.
        Returns: (response_text, token_info)
        token_info contains: prompt_tokens, completion_tokens, total_tokens from API,
        plus estimated_input_tokens calculated locally
        """
        url = f"{self.base_url}/v1/chat/completions"
        logger.info(f"Calling LLM: {url} with model {self.model}")
        
        # 应用滑动窗口策略：保护system prompt，对user message做动态截断
        messages = self._apply_token_budget(messages)
        
        # 计算最终的输入token数
        input_content = "\n".join([msg.get("content", "") for msg in messages])
        estimated_input_tokens = self._estimate_tokens(input_content, len(messages))
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            obj = resp.json()
            logger.info(f"LLM response received successfully")
            
            # 提取token使用信息
            usage = obj.get("usage", {})
            token_info = {
                "estimated_input_tokens": estimated_input_tokens,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0)
            }
            
            return obj["choices"][0]["message"]["content"], token_info
        except Exception as e:
            logger.error(f"LLM request failed: {type(e).__name__}: {e}")
            raise
