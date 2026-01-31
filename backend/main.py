import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent.core import AgentCore
from agent.store import MemoryStore, SettingsStore

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
    return {"ok": True}

@app.get("/settings")
def get_settings():
    return settings.get_safe()

@app.post("/settings")
def set_settings(req: SettingsReq):
    settings.set(req.model_dump())
    return {"ok": True}

@app.post("/chat", response_model=ChatResp)
def chat(req: ChatReq):
    out = agent.chat(req.user_message, session_id=req.session_id)
    return ChatResp(**out)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=APP_HOST, port=APP_PORT, reload=False)
