import os
import sys
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from agent.core import AgentCore
from agent.store import MemoryStore, SettingsStore
from memory_plugin_api import (
    MemoryPluginService,
    AddMemoryRequest, 
    SearchMemoryRequest, 
    DeleteMemoryRequest,
    SwitchPluginRequest,
    PluginConfigRequest
)
from conversations_api import (
    get_conversations_list,
    get_conversation_detail,
    search_conversations
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# 初始化 Memory Plugin 服务（新的插件化系统）
memory_service = MemoryPluginService.get_instance(
    user_id="default_user"
)

class ChatReq(BaseModel):
    user_message: str
    session_id: str | None = None

class ChatResp(BaseModel):
    assistant_message: str
    mode: str
    used_memory_cards: list[str]

class SettingsReq(BaseModel):
    provider: str = "openai_compatible"
    base_url: str
    api_key: str
    model: str

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
    settings.set(req.model_dump())
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

@app.post("/chat", response_model=ChatResp)
def chat(req: ChatReq):
    print(f"\n>>> [CHAT] Request: {req.user_message[:50]}...", flush=True)
    logger.info(f"Chat request: {req.user_message[:50]}... (session: {req.session_id})")
    out = agent.chat(req.user_message, session_id=req.session_id)
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


# ==================== Conversations API ====================

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


if __name__ == "__main__":
    import uvicorn
    import sys
    print(f"\n\n{'='*60}")
    print(f"Starting AURORA backend on http://{APP_HOST}:{APP_PORT}")
    print(f"{'='*60}\n")
    sys.stdout.flush()
    sys.stderr.flush()
    logger.info(f"Starting AURORA backend on {APP_HOST}:{APP_PORT}")
    uvicorn.run("main:app", host=APP_HOST, port=APP_PORT, reload=False, log_level="info")
