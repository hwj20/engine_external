import json
import logging
import urllib.request
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

    def chat(self, messages: List[Dict[str, str]], max_tokens: int = 300, temperature: float = 0.6) -> Tuple[str, Dict[str, Any]]:
        """
        Send chat completion request.
        Returns: (response_text, token_info)
        token_info contains: prompt_tokens, completion_tokens, total_tokens from API,
        plus estimated_input_tokens calculated locally
        """
        url = f"{self.base_url}/v1/chat/completions"
        logger.info(f"Calling LLM: {url} with model {self.model}")
        
        # 计算输入token数（改进的本地估算）
        # OpenAI消息格式会为每条消息添加约4个token的开销
        input_content = "\n".join([msg.get("content", "") for msg in messages])
        
        # 更精确的估算：中文约1.5字符/token，英文约4字符/token
        # 检测中文字符比例
        chinese_chars = sum(1 for c in input_content if '\u4e00' <= c <= '\u9fff')
        total_chars = len(input_content)
        chinese_ratio = chinese_chars / total_chars if total_chars > 0 else 0
        
        # 混合计算：中文部分用1.5，英文部分用4
        if chinese_ratio > 0.3:
            # 中文为主的文本
            estimated_input_tokens = int(total_chars / 1.5)
        else:
            # 英文为主的文本
            estimated_input_tokens = int(total_chars / 4)
        
        # 加上消息格式开销（每条消息约4个token）
        estimated_input_tokens += len(messages) * 4
        
        if estimated_input_tokens > self.max_input_tokens:
            logger.warning(f"Input tokens ({estimated_input_tokens}) exceeds limit ({self.max_input_tokens}), truncating...")
            # 如果超过限制，则从较早的消息开始删除（保留system和最后一条user消息）
            if len(messages) > 2:
                # 保留第一条（通常是system），最后一条（当前user message），删除中间的
                messages = [messages[0]] + messages[-1:]
                # 重新计算
                input_content = "\n".join([msg.get("content", "") for msg in messages])
                chinese_chars = sum(1 for c in input_content if '\u4e00' <= c <= '\u9fff')
                total_chars = len(input_content)
                chinese_ratio = chinese_chars / total_chars if total_chars > 0 else 0
                if chinese_ratio > 0.3:
                    estimated_input_tokens = int(total_chars / 1.5)
                else:
                    estimated_input_tokens = int(total_chars / 4)
                estimated_input_tokens += len(messages) * 4
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                obj = json.loads(resp.read().decode("utf-8"))
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
