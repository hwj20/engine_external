import os
import sys
import logging
import re
import json
import time
import shutil
import requests
from pathlib import Path
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from agent.core import AgentCore
from agent.store import MemoryStore, SettingsStore
from memory_plugin_api import (
    MemoryPluginService,
    AddMemoryRequest, 
    SearchMemoryRequest, 
    DeleteMemoryRequest,
    SwitchPluginRequest,
    PluginConfigRequest,
    EvaluateMemoriesRequest,
    UpdateMemoryImportanceRequest
)
from conversations_api import (
    get_conversations_list,
    get_conversation_detail,
    search_conversations,
    get_engine_conversations_list,
    get_engine_conversation_detail,
    save_engine_conversation,
    update_conversation_title,
    reload_engine_conversations,
    init_engine_conversations,
    split_conversations_file,
    delete_engine_conversation,
    is_split_available,
    _find_conversations_json,
    PERSONAL_INFO_DIR
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Fix Windows console UTF-8 encoding for Unicode characters
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

APP_HOST = "127.0.0.1"
APP_PORT = 8787

app = FastAPI(title="AURORA Local Agent MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure data directory exists (will be created at runtime)
# For packaged app, data goes to user's AppData; for dev, it's in backend/data
if getattr(sys, 'frozen', False):
    # Running as packaged executable
    DATA_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "AURORA-Local-Agent")
else:
    # Running in development
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

os.makedirs(DATA_DIR, exist_ok=True)

settings = SettingsStore(os.path.join(DATA_DIR, "settings.json"))
memory = MemoryStore(os.path.join(DATA_DIR, "memory.sqlite3"))
agent = AgentCore(memory=memory, settings=settings)

# System Prompts templates 目录
# For packaged app, auto-copy system_prompts from bundle to AppData on first run
if getattr(sys, 'frozen', False):
    # Running as packaged executable - bundled system_prompts location
    BUNDLED_SYSTEM_PROMPTS = os.path.join(sys._MEIPASS, "system_prompts")
    # User-accessible system_prompts location (in AppData)
    SYSTEM_PROMPTS_DIR = os.path.join(DATA_DIR, "system_prompts")
    
    # Auto-copy from bundle if AppData doesn't have it yet
    if not os.path.exists(SYSTEM_PROMPTS_DIR):
        try:
            if os.path.exists(BUNDLED_SYSTEM_PROMPTS):
                shutil.copytree(BUNDLED_SYSTEM_PROMPTS, SYSTEM_PROMPTS_DIR)
                print(f"[INIT] Copied bundled system prompts to AppData: {SYSTEM_PROMPTS_DIR}", flush=True)
            else:
                print(f"[WARN] Bundled system prompts not found: {BUNDLED_SYSTEM_PROMPTS}", flush=True)
        except Exception as e:
            print(f"[ERROR] Failed to copy system prompts to AppData: {e}", flush=True)
    
    print(f"[INIT] Running as packaged app, using SYSTEM_PROMPTS_DIR: {SYSTEM_PROMPTS_DIR}", flush=True)
else:
    # Running in development - use bundled location directly
    SYSTEM_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "system_prompts")
    print(f"[INIT] Running in development, using SYSTEM_PROMPTS_DIR: {SYSTEM_PROMPTS_DIR}", flush=True)

# Verify directory exists
if not os.path.exists(SYSTEM_PROMPTS_DIR):
    print(f"[ERROR] System prompts directory not found: {SYSTEM_PROMPTS_DIR}", flush=True)
    logger.error(f"System prompts directory not found: {SYSTEM_PROMPTS_DIR}")
else:
    print(f"[INIT] System prompts directory exists with {len(os.listdir(SYSTEM_PROMPTS_DIR))} files", flush=True)

# 用户自定义人格存储目录
CUSTOM_PERSONALITIES_DIR = os.path.join(DATA_DIR, "custom_personalities")
os.makedirs(CUSTOM_PERSONALITIES_DIR, exist_ok=True)

def load_system_prompt_templates() -> Dict[str, Dict[str, Any]]:
    """加载所有可用的系统提示模板"""
    templates = {}
    
    if not os.path.exists(SYSTEM_PROMPTS_DIR):
        print(f"[SYSTEM_PROMPTS] Directory not found: {SYSTEM_PROMPTS_DIR}", flush=True)
        return templates
    
    # 扫描所有.md文件
    for file_path in sorted(Path(SYSTEM_PROMPTS_DIR).glob("*.md")):
        if file_path.name == "README.md" or file_path.name == "05_template.md":
            continue
            
        template_id = file_path.stem  # e.g., "01_standard"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # 提取标题（第一行或#开头的行）
            title = "Custom Template"
            lines = content.split('\n')
            for line in lines:
                if line.startswith('#'):
                    title = line.lstrip('#').strip()
                    break
            
            # 移除markdown格式标记，只保留纯文本
            text_content = content
            # 移除markdown代码块标记
            text_content = re.sub(r'```[\w]*\n', '', text_content)
            text_content = re.sub(r'\n```', '', text_content)
            # 移除markdown标题标记
            text_content = re.sub(r'^#+\s+', '', text_content, flags=re.MULTILINE)
            # 移除markdown加粗和斜体
            text_content = re.sub(r'\*\*|\*|__', '', text_content)
            # 移除markdown列表标记
            text_content = re.sub(r'^[\-\*]\s+', '', text_content, flags=re.MULTILINE)
            # 清理多余空行
            text_content = '\n'.join([line.rstrip() for line in text_content.split('\n')])
            while '\n\n\n' in text_content:
                text_content = text_content.replace('\n\n\n', '\n\n')
            text_content = text_content.strip()
            
            templates[template_id] = {
                "id": template_id,
                "title": title,
                "content": text_content,
                "file": file_path.name,
                "is_builtin": True
            }
            print(f"[SYSTEM_PROMPTS] Loaded template: {template_id} - {title}", flush=True)
            
        except Exception as e:
            print(f"[SYSTEM_PROMPTS] Error loading {file_path.name}: {e}", flush=True)
            logger.error(f"Error loading system prompt template {file_path.name}: {e}")
    
    return templates

def load_custom_personalities() -> Dict[str, Dict[str, Any]]:
    """加载用户自定义的人格"""
    personalities = {}
    
    if not os.path.exists(CUSTOM_PERSONALITIES_DIR):
        return personalities
    
    try:
        for file_path in sorted(Path(CUSTOM_PERSONALITIES_DIR).glob("*.json")):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                personality_id = file_path.stem
                personalities[personality_id] = {
                    "id": personality_id,
                    "title": data.get("title", personality_id),
                    "content": data.get("content", ""),
                    "is_builtin": False
                }
                print(f"[CUSTOM_PERSONALITIES] Loaded: {personality_id} - {data.get('title', personality_id)}", flush=True)
            except Exception as e:
                print(f"[CUSTOM_PERSONALITIES] Error loading {file_path.name}: {e}", flush=True)
                logger.error(f"Error loading custom personality {file_path.name}: {e}")
    except Exception as e:
        print(f"[CUSTOM_PERSONALITIES] Error scanning directory: {e}", flush=True)
    
    return personalities

# 在启动时加载所有模板
SYSTEM_PROMPT_TEMPLATES = load_system_prompt_templates()
CUSTOM_PERSONALITIES = load_custom_personalities()
# 合并模板和自定义人格
ALL_PERSONALITIES = {**SYSTEM_PROMPT_TEMPLATES, **CUSTOM_PERSONALITIES}
print(f"[SYSTEM_PROMPTS] Loaded {len(SYSTEM_PROMPT_TEMPLATES)} built-in templates", flush=True)
print(f"[CUSTOM_PERSONALITIES] Loaded {len(CUSTOM_PERSONALITIES)} custom personalities", flush=True)

# 初始化 Memory Plugin 服务（新的插件化系统）
memory_service = MemoryPluginService.get_instance(
    user_id="default_user"
)

class ChatReq(BaseModel):
    user_message: str
    session_id: str | None = None
    user_profile: Optional[Dict[str, Any]] = None  # 用户基本信息

class ChatResp(BaseModel):
    assistant_message: str
    mode: str
    used_memory_cards: list[str]
    token_info: Optional[Dict[str, Any]] = None
    history_strategy: Optional[str] = None
    compression_state: Optional[Dict[str, Any]] = None

class SettingsReq(BaseModel):
    provider: str = "openai_compatible"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = ""
    max_input_tokens: Optional[int] = 2000
    max_output_tokens: Optional[int] = 800
    temperature: Optional[float] = 0.7
    dev_mode: Optional[bool] = False
    history_strategy: Optional[str] = "compression"
    compression_threshold: Optional[int] = 1000
    compression_target: Optional[int] = 200
    language: Optional[str] = "zh"

class ModelUpdateReq(BaseModel):
    model: str

@app.get("/health")
def health():
    print("[HEALTH] Health check requested", flush=True)
    logger.info("Health check requested")
    return {"ok": True}

@app.get("/settings")
def get_settings():
    print("[SETTINGS] Getting settings", flush=True)
    logger.info("Settings requested")
    result = settings.get_safe()
    print(f"[SETTINGS] Returned: base_url={result.get('base_url')}, model={result.get('model')}", flush=True)
    return result

@app.post("/settings")
def set_settings(req: SettingsReq):
    print(f"[SETTINGS] Updating: provider={req.provider}, base_url={req.base_url}, model={req.model}", flush=True)
    logger.info(f"Settings updated - provider: {req.provider}, model: {req.model}")
    
    # Get current settings
    current = settings.get()
    
    # Only update fields that were provided
    if req.base_url is not None:
        current["base_url"] = req.base_url
    if req.api_key is not None:
        current["api_key"] = req.api_key
    if req.model is not None:
        current["model"] = req.model
    if req.system_prompt is not None:
        current["system_prompt"] = req.system_prompt
    if req.max_input_tokens is not None:
        current["max_input_tokens"] = req.max_input_tokens
    if req.max_output_tokens is not None:
        current["max_output_tokens"] = req.max_output_tokens
    if req.temperature is not None:
        current["temperature"] = req.temperature
    if req.dev_mode is not None:
        current["dev_mode"] = req.dev_mode
    if req.history_strategy is not None:
        current["history_strategy"] = req.history_strategy
    if req.compression_threshold is not None:
        current["compression_threshold"] = req.compression_threshold
    if req.compression_target is not None:
        current["compression_target"] = req.compression_target
    if req.language is not None:
        current["language"] = req.language
    
    # 验证token限制
    if current["max_input_tokens"] and (current["max_input_tokens"] < 100 or current["max_input_tokens"] > 128000):
        return {"error": "max_input_tokens must be between 100 and 128000", "status": "error"}
    if current["max_output_tokens"] and (current["max_output_tokens"] < 100 or current["max_output_tokens"] > 32000):
        return {"error": "max_output_tokens must be between 100 and 32000", "status": "error"}
    
    settings.set(current)
    print("[SETTINGS] Settings saved successfully", flush=True)
    return {"ok": True}

@app.post("/settings/model")
def update_model_only(req: ModelUpdateReq):
    print(f"[SETTINGS] Updating model only: {req.model}", flush=True)
    logger.info(f"Model updated to: {req.model}")
    current = settings.get()
    current["model"] = req.model
    settings.set(current)
    print("[SETTINGS] Model updated successfully", flush=True)
    return {"ok": True}


@app.post("/models/fetch")
def fetch_openai_models():
    """Fetch available models from OpenAI API"""
    print("[MODELS] Fetching models from OpenAI", flush=True)
    
    try:
        st = settings.get()
        base_url = st.get("base_url", "").strip()
        api_key = st.get("api_key", "").strip()
        
        if not base_url or not api_key:
            print("[MODELS] Missing base_url or api_key", flush=True)
            return {"error": "base_url and api_key are required", "status": "error"}
        
        # Remove trailing slash from base_url
        base_url = base_url.rstrip('/')
        
        # Call the models endpoint
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        # Try different model endpoint paths
        endpoint_paths = [
            "/models",
            "/v1/models",
            "/api/models",
            "/api/v1/models"
        ]
        
        response = None
        last_error = None
        
        for endpoint_path in endpoint_paths:
            full_url = f"{base_url}{endpoint_path}"
            print(f"[MODELS] Trying {full_url}", flush=True)
            
            try:
                response = requests.get(
                    full_url,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    print(f"[MODELS] Success with {endpoint_path}", flush=True)
                    break
                elif response.status_code == 401:
                    print(f"[MODELS] Unauthorized (401) with {endpoint_path}", flush=True)
                    last_error = "Invalid API key"
                    break
                else:
                    print(f"[MODELS] {endpoint_path} returned {response.status_code}", flush=True)
                    last_error = f"Status {response.status_code}"
                    
            except Exception as e:
                print(f"[MODELS] Error trying {endpoint_path}: {e}", flush=True)
                last_error = str(e)
                continue
        
        if response is None:
            return {
                "error": f"Could not reach models endpoint. Last error: {last_error}",
                "status": "error",
                "hint": f"Tried endpoints: {', '.join(endpoint_paths)}"
            }
        
        if response.status_code == 401:
            print("[MODELS] API key invalid", flush=True)
            return {
                "error": "Invalid API key (401 Unauthorized)",
                "status": "error"
            }
        
        if response.status_code != 200:
            print(f"[MODELS] API returned status {response.status_code}: {response.text[:200]}", flush=True)
            return {
                "error": f"OpenAI API returned {response.status_code}",
                "status": "error",
                "details": response.text[:500] if response.text else "No details available"
            }
        
        data = response.json()
        models = data.get('data', [])
        
        if not models:
            print("[MODELS] No models returned from API", flush=True)
            return {
                "error": "No models found in API response",
                "status": "error",
                "response": data
            }
        
        # Filter to only include models with 'gpt' in the name, excluding 'audio' and 'tts' models (case-insensitive)
        filtered_models = [
            m for m in models 
            if 'gpt' in m.get('id', '').lower() 
            and 'audio' not in m.get('id', '').lower()
            and 'tts' not in m.get('id', '').lower()
        ]
        
        # Sort models: gpt-4o models first, then others
        def sort_key(model):
            model_id = model.get('id', '').lower()
            # gpt-4o gets priority (0), others get secondary priority (1)
            priority = 0 if 'gpt-4o' in model_id else 1
            return (priority, model_id)
        
        filtered_models.sort(key=sort_key)
        
        original_count = len(models)
        filtered_count = len(filtered_models)
        
        print(f"[MODELS] Successfully fetched {original_count} models, filtered to {filtered_count} GPT models (excluding audio/tts)", flush=True)
        
        return {
            "success": True,
            "models": filtered_models,
            "count": filtered_count
        }
        
    except requests.exceptions.Timeout:
        print("[MODELS] Request timeout", flush=True)
        return {
            "error": "Request timeout - check if base_url is correct and network is available",
            "status": "error"
        }
    except requests.exceptions.ConnectionError as e:
        print("[MODELS] Connection error", flush=True)
        return {
            "error": f"Cannot connect to base_url: {str(e)[:100]}",
            "status": "error"
        }
    except Exception as e:
        print(f"[MODELS] Error fetching models: {e}", flush=True)
        return {
            "error": f"Error: {str(e)[:200]}",
            "status": "error"
        }
    return {"ok": True, "model": req.model}

@app.get("/settings/system-prompt")
def get_system_prompt():
    print("[SETTINGS] Getting system prompt", flush=True)
    current = settings.get()
    return {"system_prompt": current.get("system_prompt", "")}

@app.post("/settings/system-prompt")
def set_system_prompt(data: dict):
    print(f"[SETTINGS] Updating system prompt", flush=True)
    logger.info(f"System prompt updated")
    current = settings.get()
    current["system_prompt"] = data.get("system_prompt", "")
    settings.set(current)
    print("[SETTINGS] System prompt saved successfully", flush=True)
    return {"ok": True}

@app.get("/settings/system-prompt/templates")
def get_system_prompt_templates():
    """获取所有可用的系统提示模板列表"""
    print("[SETTINGS] Getting system prompt templates list", flush=True)
    logger.info("System prompt templates list requested")
    
    # 构建模板列表：先是内置模板，再是自定义人格
    templates_list = []
    
    # 添加内置模板
    for template_id, template_data in SYSTEM_PROMPT_TEMPLATES.items():
        templates_list.append({
            "id": template_id,
            "title": template_data["title"],
            "is_builtin": True
        })
    
    # 添加自定义人格
    for personality_id, personality_data in CUSTOM_PERSONALITIES.items():
        templates_list.append({
            "id": personality_id,
            "title": personality_data["title"],
            "is_builtin": False
        })
    
    return {
        "templates": templates_list,
        "count": len(templates_list)
    }

@app.get("/settings/system-prompt/templates/{template_id}")
def get_system_prompt_template(template_id: str):
    """加载特定的系统提示模板"""
    print(f"[SETTINGS] Getting system prompt template: {template_id}", flush=True)
    logger.info(f"System prompt template requested: {template_id}")
    
    # 先检查内置模板，再检查自定义人格
    if template_id in SYSTEM_PROMPT_TEMPLATES:
        template_data = SYSTEM_PROMPT_TEMPLATES[template_id]
    elif template_id in CUSTOM_PERSONALITIES:
        template_data = CUSTOM_PERSONALITIES[template_id]
    else:
        print(f"[SETTINGS] Template not found: {template_id}", flush=True)
        return {"error": f"Template '{template_id}' not found", "status": "error"}
    
    print(f"[SETTINGS] Returning template: {template_id}", flush=True)
    
    return {
        "id": template_data["id"],
        "title": template_data["title"],
        "content": template_data["content"],
        "status": "success"
    }

@app.post("/settings/system-prompt/save-custom")
def save_custom_personality(data: dict):
    """保存用户自定义的人格"""
    global CUSTOM_PERSONALITIES
    
    print(f"[CUSTOM_PERSONALITIES] Saving custom personality", flush=True)
    
    title = data.get("title", "").strip() or "My Custom Personality"
    content = data.get("content", "").strip()
    
    if not content:
        return {"error": "Personality content cannot be empty", "status": "error"}
    
    # 生成ID
    personality_id = f"custom_{int(time.time())}"
    
    try:
        # 保存为JSON文件
        file_path = os.path.join(CUSTOM_PERSONALITIES_DIR, f"{personality_id}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({
                "title": title,
                "content": content,
                "created_at": time.time()
            }, f, ensure_ascii=False, indent=2)
        
        print(f"[CUSTOM_PERSONALITIES] Saved: {personality_id} - {title}", flush=True)
        logger.info(f"Custom personality saved: {personality_id}")
        
        # 重新加载所有自定义人格以确保同步
        CUSTOM_PERSONALITIES = load_custom_personalities()
        
        return {
            "personality_id": personality_id,
            "title": title,
            "status": "success"
        }
    except Exception as e:
        print(f"[CUSTOM_PERSONALITIES] Error saving: {e}", flush=True)
        logger.error(f"Error saving custom personality: {e}")
        return {"error": str(e), "status": "error"}

@app.delete("/settings/system-prompt/templates/{template_id}")
def delete_system_prompt_template(template_id: str):
    """删除自定义的系统提示模板"""
    global CUSTOM_PERSONALITIES
    
    print(f"[SYSTEM_PROMPTS] Deleting template: {template_id}", flush=True)
    
    try:
        # 只允许删除自定义的personality，不允许删除内置模板
        if not template_id.startswith("custom_"):
            return {
                "error": "Cannot delete built-in templates",
                "status": "error"
            }
        
        # 删除文件
        file_path = os.path.join(CUSTOM_PERSONALITIES_DIR, f"{template_id}.json")
        
        if not os.path.exists(file_path):
            return {
                "error": "Template not found",
                "status": "error"
            }
        
        os.remove(file_path)
        print(f"[SYSTEM_PROMPTS] Deleted: {template_id}", flush=True)
        logger.info(f"System prompt template deleted: {template_id}")
        
        # 重新加载自定义personalities
        CUSTOM_PERSONALITIES = load_custom_personalities()
        
        return {
            "status": "success",
            "message": "Template deleted successfully"
        }
    except Exception as e:
        print(f"[SYSTEM_PROMPTS] Error deleting: {e}", flush=True)
        logger.error(f"Error deleting system prompt template: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@app.get("/settings/token-limits")
def get_token_limits():
    """获取token限制设置"""
    print("[SETTINGS] Getting token limits", flush=True)
    current = settings.get()
    return {
        "max_input_tokens": current.get("max_input_tokens", 2000),
        "max_output_tokens": current.get("max_output_tokens", 800)
    }

@app.post("/settings/token-limits")
def set_token_limits(data: dict):
    """保存token限制设置"""
    print("[SETTINGS] Updating token limits", flush=True)
    try:
        max_input = int(data.get("max_input_tokens", 2000))
        max_output = int(data.get("max_output_tokens", 800))
        
        # 基本验证
        if max_input < 100 or max_input > 128000:
            return {"error": "max_input_tokens must be between 100 and 128000", "status": "error"}
        if max_output < 100 or max_output > 32000:
            return {"error": "max_output_tokens must be between 100 and 32000", "status": "error"}
        
        current = settings.get()
        current["max_input_tokens"] = max_input
        current["max_output_tokens"] = max_output
        settings.set(current)
        
        print(f"[SETTINGS] Token limits saved: input={max_input}, output={max_output}", flush=True)
        logger.info(f"Token limits updated: input={max_input}, output={max_output}")
        return {
            "max_input_tokens": max_input,
            "max_output_tokens": max_output,
            "status": "success"
        }
    except ValueError as e:
        return {"error": f"Invalid token limits: {e}", "status": "error"}

@app.post("/chat", response_model=ChatResp)
def chat(req: ChatReq):
    print(f"\n>>> [CHAT] Request: {req.user_message[:50]}...", flush=True)
    print(f">>> [CHAT] user_profile: {req.user_profile}", flush=True)
    print(f">>> [CHAT] memory_service: {memory_service}", flush=True)
    logger.info(f"Chat request: {req.user_message[:50]}... (session: {req.session_id})")
    
    # 获取记忆上下文
    print(f">>> [CHAT] Calling get_conversation_context with query='{req.user_message}'", flush=True)
    memory_context = memory_service.get_conversation_context(
        query=req.user_message,
        user_profile=req.user_profile
    )
    print(f">>> [CHAT] Got memory_context: {memory_context}", flush=True)
    
    out = agent.chat(
        req.user_message, 
        session_id=req.session_id,
        memory_context=memory_context
    )
    print(f"<<< [CHAT] Response ({out['mode']}): {out['assistant_message'][:100]}...\n", flush=True)
    logger.info(f"Chat response mode: {out['mode']}, memory_cards: {len(out['used_memory_cards'])}")
    return ChatResp(**out)

class ClearHistoryReq(BaseModel):
    session_id: str = "default"

@app.post("/clear-history")
def clear_history(req: ClearHistoryReq):
    """清空指定会话的对话历史"""
    print(f"[CLEAR] Clearing history for session: {req.session_id}", flush=True)
    logger.info(f"Clearing history for session: {req.session_id}")
    agent.clear_history(req.session_id)
    return {"ok": True, "session_id": req.session_id}

@app.post("/echo")
def echo(req: ChatReq):
    """Simple echo endpoint for testing"""
    print(f"\n[ECHO] Received message: '{req.user_message}'", flush=True)
    logger.info(f"Echo test: {req.user_message}")
    return {"echo": req.user_message, "received_at": "backend"}


# ==================== Memory Plugin API ====================

# --- 插件管理 ---

@app.get("/memory/plugins")
def get_available_plugins():
    """获取所有可用的记忆插件"""
    print("[MEMORY] Getting available plugins", flush=True)
    return {"plugins": memory_service.get_available_plugins()}


@app.get("/memory/plugins/active")
def get_active_plugin():
    """获取当前激活的插件"""
    print("[MEMORY] Getting active plugin", flush=True)
    return memory_service.get_active_plugin()


@app.post("/memory/plugins/switch")
def switch_plugin(req: SwitchPluginRequest):
    """切换记忆插件"""
    print(f"[MEMORY] Switching to plugin: {req.plugin_id}", flush=True)
    result = memory_service.switch_plugin(req.plugin_id)
    return result


@app.post("/memory/plugins/config")
def set_plugin_config(req: PluginConfigRequest):
    """设置插件配置"""
    print(f"[MEMORY] Setting config for plugin: {req.plugin_id}", flush=True)
    result = memory_service.set_plugin_config(req.plugin_id, req.config)
    return result


# --- 记忆操作 ---

@app.get("/memory/visualization")
def get_visualization_data():
    """获取可视化数据（包含记忆和插件信息）"""
    print("[MEMORY] Getting visualization data", flush=True)
    return memory_service.get_visualization_data()


@app.get("/memory/stats")
def get_memory_stats():
    """获取记忆统计信息"""
    print("[MEMORY] Getting stats", flush=True)
    return memory_service.get_stats()


@app.get("/memory/recent")
def get_recent_memories(limit: int = 20):
    """获取最近的记忆"""
    print(f"[MEMORY] Getting recent memories (limit={limit})", flush=True)
    return {"memories": memory_service.get_recent_memories(limit)}


@app.post("/memory/add")
def add_memory(req: AddMemoryRequest):
    """添加新记忆"""
    print(f"[MEMORY] Adding memory: {req.content[:50]}...", flush=True)
    memory_id = memory_service.add_memory(
        content=req.content,
        importance=req.importance,
        emotion_tags=req.emotion_tags,
        topic_tags=req.topic_tags,
        entities=req.entities
    )
    return {"ok": True, "memory_id": memory_id}


@app.post("/memory/search")
def search_memories(req: SearchMemoryRequest):
    """搜索记忆"""
    print(f"[MEMORY] Searching: query={req.query}, time={req.time_hint}, topic={req.topic}", flush=True)
    results = memory_service.search_memories(
        query=req.query,
        time_hint=req.time_hint,
        topic=req.topic,
        limit=req.limit
    )
    return {"results": results}


@app.post("/memory/delete")
def delete_memory(req: DeleteMemoryRequest):
    """删除记忆"""
    print(f"[MEMORY] Deleting memory: {req.memory_id}", flush=True)
    result = memory_service.delete_memory(req.memory_id)
    return {"ok": result}


@app.post("/memory/demo")
def add_demo_data():
    """添加演示数据"""
    print("[MEMORY] Adding demo data", flush=True)
    result = memory_service.add_demo_data()
    return {"ok": True, **result}


@app.post("/memory/clear")
def clear_all_memories():
    """清空所有记忆"""
    print("[MEMORY] Clearing all memories", flush=True)
    result = memory_service.clear_all()
    return {"ok": result}


@app.get("/memory/context")
def get_memory_context(query: str = None, limit: int = 10):
    """获取对话上下文"""
    print(f"[MEMORY] Getting context for: {query}", flush=True)
    context = memory_service.get_context_for_conversation(query, limit)
    return context


# --- Knowledge Graph (if plugin supports) ---

@app.get("/memory/entities")
def get_entities():
    """Get entity list"""
    print("[MEMORY] Getting entities", flush=True)
    return {"entities": memory_service.get_entities()}


@app.get("/memory/relationships")
def get_relationships():
    """Get relationship list"""
    print("[MEMORY] Getting relationships", flush=True)
    return {"relationships": memory_service.get_relationships()}


# --- LLM Memory Evaluation ---

@app.post("/memory/evaluate")
def evaluate_memories(req: EvaluateMemoriesRequest = EvaluateMemoriesRequest()):
    """
    使用 LLM 评估记忆的重要性
    严格标准：只有真正的核心身份信息才会被标记为核心记忆
    """
    print(f"[MEMORY] Evaluating memories with LLM, memory_ids={req.memory_ids}", flush=True)
    
    # 获取 LLM 配置
    settings_data = settings.get()
    base_url = settings_data.get("base_url", "")
    api_key = settings_data.get("api_key", "")
    model = settings_data.get("model", "")
    
    if not base_url or not api_key or not model:
        return {
            "success": False,
            "error": "LLM not configured",
            "message": "请先在设置中配置 LLM 的 base_url、api_key 和 model"
        }
    
    # 创建 LLM 客户端
    from agent.llm import OpenAICompatibleClient
    llm_client = OpenAICompatibleClient(
        base_url=base_url,
        api_key=api_key,
        model=model
    )
    
    result = memory_service.evaluate_memories_with_llm(
        llm_client=llm_client,
        memory_ids=req.memory_ids if req.memory_ids else None
    )
    return result


@app.post("/memory/update-importance")
def update_memory_importance(req: UpdateMemoryImportanceRequest):
    """
    更新单条记忆的重要性
    """
    print(f"[MEMORY] Updating importance for {req.memory_id} to {req.importance}", flush=True)
    result = memory_service.update_memory_importance(req.memory_id, req.importance)
    return result


# ==================== Conversations API (Original - Read Only) ====================

@app.get("/conversations")
def list_conversations(query: Optional[str] = None, limit: Optional[int] = None):
    """
    Get list of conversations (titles only for performance)
    Supports optional search query
    If limit is not provided, returns all conversations
    """
    print(f"[CONVERSATIONS] Listing conversations (query={query}, limit={limit})", flush=True)
    logger.info(f"Listing conversations: query={query}")
    
    if query:
        results = search_conversations(query, limit if limit else 10000)
    else:
        all_convs = get_conversations_list()
        results = all_convs if not limit else all_convs[:limit]
    
    return {"conversations": [r.model_dump() for r in results]}


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    """
    Get full conversation detail by ID (lazy load)
    """
    print(f"[CONVERSATIONS] Loading conversation: {conversation_id}", flush=True)
    logger.info(f"Loading conversation: {conversation_id}")
    
    detail = get_conversation_detail(conversation_id)
    
    if not detail:
        return {"error": "Conversation not found", "conversation_id": conversation_id}
    
    return detail.model_dump()


# ==================== Engine Conversations API (Read-Write) ====================

@app.get("/engine-conversations")
def list_engine_conversations(query: Optional[str] = None):
    """
    Get list of engine conversations (from external_engine_conversation.json)
    """
    print(f"[ENGINE_CONV] Listing engine conversations (query={query})", flush=True)
    
    all_convs = get_engine_conversations_list()
    
    if query:
        query_lower = query.lower()
        all_convs = [c for c in all_convs if query_lower in c.title.lower()]
    
    return {"conversations": [r.model_dump() for r in all_convs]}


@app.get("/engine-conversations/{conversation_id}")
def get_engine_conversation(conversation_id: str):
    """
    Get engine conversation detail by ID
    """
    print(f"[ENGINE_CONV] Loading conversation: {conversation_id}", flush=True)
    
    detail = get_engine_conversation_detail(conversation_id)
    
    if not detail:
        return {"error": "Conversation not found", "conversation_id": conversation_id}
    
    return detail.model_dump()


@app.post("/engine-conversations/reload")
def reload_conversations():
    """
    Reload engine conversations by re-splitting from conversations.json
    """
    print(f"[ENGINE_CONV] Re-splitting conversations from source", flush=True)
    
    success = reload_engine_conversations()
    
    if success:
        return {"ok": True, "message": "Conversations re-split successfully"}
    else:
        return {"ok": False, "error": "Failed to re-split conversations"}


@app.get("/conversations/split-status")
def get_split_status():
    """Check whether conversations have been split into multi-file format"""
    available = is_split_available()
    return {"available": available}


@app.post("/engine-conversations/{conversation_id}/title")
def update_conv_title(conversation_id: str, data: dict):
    """
    Update conversation title
    """
    new_title = data.get("title", "")
    print(f"[ENGINE_CONV] Updating title: {conversation_id} -> {new_title}", flush=True)
    
    success = update_conversation_title(conversation_id, new_title)
    
    if success:
        return {"ok": True, "title": new_title}
    else:
        return {"ok": False, "error": "Failed to update title"}


@app.post("/engine-conversations/save")
def save_conversation(data: dict):
    """
    Save current conversation to engine conversations file
    """
    conversation_id = data.get("conversation_id", f"engine_{int(time.time())}")
    title = data.get("title", "Untitled Conversation")
    messages = data.get("messages", [])
    
    print(f"[ENGINE_CONV] Saving conversation: {conversation_id}", flush=True)
    
    success = save_engine_conversation(conversation_id, title, messages)
    
    if success:
        return {"ok": True, "conversation_id": conversation_id, "title": title}
    else:
        return {"ok": False, "error": "Failed to save conversation"}


@app.post("/engine-conversations/delete/{conversation_id}")
def delete_conversation(conversation_id: str):
    """
    Delete a conversation from the split store
    """
    print(f"[ENGINE_CONV] Deleting conversation: {conversation_id}", flush=True)
    success = delete_engine_conversation(conversation_id)
    if success:
        return {"ok": True, "message": f"Conversation {conversation_id} deleted"}
    else:
        return {"error": f"Conversation {conversation_id} not found or could not be deleted"}


@app.post("/upload-conversation-zip")
async def upload_conversation_zip(file: UploadFile = File(...)):
    """
    Upload a zip file and extract it to the personal_info/data directory
    (where conversations.json and related files live).
    """
    import zipfile
    import tempfile

    print(f"[UPLOAD] Receiving zip upload: {file.filename}", flush=True)

    if not file.filename or not file.filename.lower().endswith('.zip'):
        return {"ok": False, "error": "Only .zip files are allowed"}

    try:
        # Save uploaded file to a temp location
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.zip')
        try:
            contents = await file.read()
            with os.fdopen(tmp_fd, 'wb') as tmp_file:
                tmp_file.write(contents)

            # Validate it's actually a zip file
            if not zipfile.is_zipfile(tmp_path):
                return {"ok": False, "error": "Uploaded file is not a valid zip archive"}

            # Extract to PERSONAL_INFO_DIR
            extracted_count = 0
            with zipfile.ZipFile(tmp_path, 'r') as zf:
                # Security check: prevent path traversal
                for member in zf.namelist():
                    member_path = os.path.normpath(member)
                    if member_path.startswith('..') or os.path.isabs(member_path):
                        return {"ok": False, "error": f"Zip contains unsafe path: {member}"}

                zf.extractall(PERSONAL_INFO_DIR)
                extracted_count = len(zf.namelist())

            print(f"[UPLOAD] Extracted {extracted_count} files to {PERSONAL_INFO_DIR}", flush=True)

            # Auto-split conversations.json into multi-file architecture
            split_result = None
            source = _find_conversations_json(PERSONAL_INFO_DIR)
            if source:
                try:
                    split_result = split_conversations_file(source)
                    print(f"[UPLOAD] Auto-split: {split_result['total']} conversations in {split_result['elapsed']}s", flush=True)
                except Exception as e:
                    print(f"[UPLOAD] Auto-split failed: {e}", flush=True)
                    logger.error(f"Auto-split after upload failed: {e}")

            return {
                "ok": True,
                "message": f"Successfully extracted {extracted_count} files",
                "extracted_count": extracted_count,
                "target_dir": PERSONAL_INFO_DIR,
                "split": split_result
            }
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as e:
        print(f"[UPLOAD] Error processing zip upload: {e}", flush=True)
        return {"ok": False, "error": f"Failed to process zip: {str(e)}"}


@app.post("/load-conversation-to-context")
def load_conversation_to_context(data: dict):
    """
    Load a conversation into the agent's context (conversation history)
    """
    conversation_id = data.get("conversation_id")
    session_id = data.get("session_id", "default")
    
    print(f"[ENGINE_CONV] Loading conversation to context: {conversation_id} -> session {session_id}", flush=True)
    
    # First try engine conversations, then original
    detail = get_engine_conversation_detail(conversation_id)
    if not detail:
        detail = get_conversation_detail(conversation_id)
    
    if not detail:
        print(f"[ENGINE_CONV] Conversation not found: {conversation_id}", flush=True)
        return {"ok": False, "error": "Conversation not found"}
    
    # Clear existing history
    agent.clear_history(session_id)
    print(f"[ENGINE_CONV] Cleared history for session: {session_id}", flush=True)
    
    # Add messages to agent's conversation history
    added_count = 0
    for msg in detail.messages:
        if msg.role in ['user', 'assistant']:
            print(f"[ENGINE_CONV] Adding message - role: {msg.role}, content length: {len(msg.content)}", flush=True)
            agent._add_to_history(session_id, msg.role, msg.content)
            added_count += 1
    
    print(f"[ENGINE_CONV] Loaded {added_count} messages to session {session_id}", flush=True)
    print(f"[ENGINE_CONV] Session conversation_history now has {len(agent.conversation_history[session_id])} messages", flush=True)
    
    return {
        "ok": True,
        "conversation_id": conversation_id,
        "title": detail.title,
        "message_count": len(detail.messages),
        "session_id": session_id
    }


if __name__ == "__main__":
    import uvicorn
    import sys
    print(f"\n\n{'='*60}")
    print(f"Starting AURORA backend on http://{APP_HOST}:{APP_PORT}")
    print(f"{'='*60}\n")
    sys.stdout.flush()
    sys.stderr.flush()
    logger.info(f"Starting AURORA backend on {APP_HOST}:{APP_PORT}")
    uvicorn.run(app, host=APP_HOST, port=APP_PORT, reload=False, log_level="info")
