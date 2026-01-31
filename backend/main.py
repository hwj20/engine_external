import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent.core import AgentCore
from agent.store import MemoryStore, SettingsStore

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

@app.post("/chat", response_model=ChatResp)
def chat(req: ChatReq):
    print(f"\n>>> [CHAT] Request: {req.user_message[:50]}...", flush=True)
    logger.info(f"Chat request: {req.user_message[:50]}... (session: {req.session_id})")
    out = agent.chat(req.user_message, session_id=req.session_id)
    print(f"<<< [CHAT] Response ({out['mode']}): {out['assistant_message'][:100]}...\n", flush=True)
    logger.info(f"Chat response mode: {out['mode']}, memory_cards: {len(out['used_memory_cards'])}")
    return ChatResp(**out)

@app.post("/echo")
def echo(req: ChatReq):
    """Simple echo endpoint for testing"""
    print(f"\n[ECHO] Received message: '{req.user_message}'", flush=True)
    logger.info(f"Echo test: {req.user_message}")
    return {"echo": req.user_message, "received_at": "backend"}

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
