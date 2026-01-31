import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent.core import AgentCore
from agent.store import MemoryStore, SettingsStore
from memory_api import (
    MemoryService, 
    AddMemoryRequest, 
    SearchMemoryRequest, 
    DeleteMemoryRequest
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

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

settings = SettingsStore(os.path.join(DATA_DIR, "settings.json"))
memory = MemoryStore(os.path.join(DATA_DIR, "memory.sqlite3"))
agent = AgentCore(memory=memory, settings=settings)

# 初始化 Memory Framework 服务
memory_service = MemoryService.get_instance(
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


# ==================== Memory Framework API ====================

@app.get("/memory/tree")
def get_memory_tree():
    """获取记忆树摘要"""
    print("[MEMORY] Getting memory tree summary", flush=True)
    return memory_service.get_memory_tree_summary()


@app.get("/memory/graph")
def get_knowledge_graph():
    """获取知识图谱摘要"""
    print("[MEMORY] Getting knowledge graph summary", flush=True)
    return memory_service.get_knowledge_graph_summary()


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


@app.get("/memory/context")
def get_memory_context(query: str = None, limit: int = 10):
    """获取对话上下文"""
    print(f"[MEMORY] Getting context for: {query}", flush=True)
    context = memory_service.get_context_for_conversation(query, limit)
    return context

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
