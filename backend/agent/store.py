import os
import json
import sqlite3
import time
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

def _now_ts() -> int:
    return int(time.time())

class SettingsStore:
    '''
    MVP: stores API key locally in JSON.
    Production: use OS keychain (Keytar) or encrypted storage.
    '''
    def __init__(self, path: str):
        self.path = path
        print(f"[SettingsStore] Initializing at {path}", flush=True)
        if not os.path.exists(self.path):
            print(f"[SettingsStore] Creating new settings file", flush=True)
            self.set({
                "provider": "openai_compatible",
                "base_url": "",
                "api_key": "",
                "model": "",
                "system_prompt": "",
                "max_input_tokens": 2000,
                "max_output_tokens": 800,
                "temperature": 0.7,
                "dev_mode": False,
                "history_strategy": "compression",
                "compression_threshold": 1000,
                "compression_target": 200,
                "language": "zh"
            })
        else:
            print(f"[SettingsStore] Loading existing settings from {path}", flush=True)
            # 加载现有设置并添加缺失的新字段
            existing = self.get()
            if "max_input_tokens" not in existing:
                existing["max_input_tokens"] = 2000
            if "max_output_tokens" not in existing:
                existing["max_output_tokens"] = 800
            if "temperature" not in existing:
                existing["temperature"] = 0.7
            if "dev_mode" not in existing:
                existing["dev_mode"] = False
            if "history_strategy" not in existing:
                existing["history_strategy"] = "compression"
            if "compression_threshold" not in existing:
                existing["compression_threshold"] = 1000
            if "compression_target" not in existing:
                existing["compression_target"] = 200
            if "language" not in existing:
                existing["language"] = "zh"
            self.set(existing)

    def set(self, data: Dict[str, Any]) -> None:
        print(f"[SettingsStore.set] Writing settings", flush=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Settings saved to {self.path}")

    def get(self) -> Dict[str, Any]:
        print(f"[SettingsStore.get] Reading settings from {self.path}", flush=True)
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_safe(self) -> Dict[str, Any]:
        d = dict(self.get())
        if d.get("api_key"):
            d["api_key"] = "********"
        return d

class MemoryStore:
    '''
    SQLite memory store:
      - semantic_memory: long-term stable preferences/rules
      - episodic_memory: events w/ time + entities + importance
      - conversation_summaries: session summaries
    '''
    def __init__(self, db_path: str):
        self.db_path = db_path
        print(f"[MemoryStore] Initializing at {db_path}", flush=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        print(f"[MemoryStore._init] Creating/checking database tables", flush=True)
        with self._conn() as conn:
            conn.execute('''
            CREATE TABLE IF NOT EXISTS semantic_memory(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE,
                value TEXT,
                confidence REAL DEFAULT 0.8,
                locked INTEGER DEFAULT 0,
                updated_at INTEGER
            )
            ''')
            conn.execute('''
            CREATE TABLE IF NOT EXISTS episodic_memory(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER,
                title TEXT,
                detail TEXT,
                entities TEXT,
                importance REAL DEFAULT 0.5
            )
            ''')
            conn.execute('''
            CREATE TABLE IF NOT EXISTS conversation_summaries(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                ts_start INTEGER,
                ts_end INTEGER,
                summary TEXT,
                tags TEXT
            )
            ''')
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ep_ts ON episodic_memory(ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ep_imp ON episodic_memory(importance)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sum_session ON conversation_summaries(session_id)")
            conn.commit()
        print(f"[MemoryStore._init] Database initialized", flush=True)

    # ---- Semantic ----
    def upsert_semantic(self, key: str, value: str, confidence: float = 0.8, locked: int = 0) -> None:
        print(f"[MemoryStore] Upserting semantic: key={key}, confidence={confidence}", flush=True)
        with self._conn() as conn:
            conn.execute('''
            INSERT INTO semantic_memory(key, value, confidence, locked, updated_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(key) DO UPDATE SET
                value=excluded.value,
                confidence=excluded.confidence,
                locked=CASE WHEN semantic_memory.locked=1 THEN 1 ELSE excluded.locked END,
                updated_at=excluded.updated_at
            ''', (key, value, confidence, locked, _now_ts()))
            conn.commit()

    def get_semantic_top(self, limit: int = 50) -> List[dict]:
        print(f"[MemoryStore] Getting top {limit} semantic memories", flush=True)
        with self._conn() as conn:
            rows = conn.execute('''
            SELECT key, value, confidence, locked, updated_at
            FROM semantic_memory
            ORDER BY locked DESC, updated_at DESC
            LIMIT ?
            ''', (limit,)).fetchall()
            result = [dict(r) for r in rows]
            print(f"[MemoryStore] Retrieved {len(result)} semantic memories", flush=True)
            return result

    # ---- Episodic ----
    def add_episode(self, title: str, detail: str, entities: str = "", importance: float = 0.5, ts: Optional[int] = None) -> None:
        print(f"[MemoryStore] Adding episode: {title}, importance={importance}", flush=True)
        with self._conn() as conn:
            conn.execute('''
            INSERT INTO episodic_memory(ts, title, detail, entities, importance)
            VALUES(?,?,?,?,?)
            ''', (ts or _now_ts(), title, detail, entities, importance))
            conn.commit()

    def search_episodes_keyword(self, query: str, limit: int = 8) -> List[dict]:
        print(f"[MemoryStore] Searching episodes with keyword: '{query}', limit={limit}", flush=True)
        q = f"%{query}%"
        with self._conn() as conn:
            rows = conn.execute('''
            SELECT ts, title, detail, entities, importance
            FROM episodic_memory
            WHERE title LIKE ? OR detail LIKE ? OR entities LIKE ?
            ORDER BY importance DESC, ts DESC
            LIMIT ?
            ''', (q, q, q, limit)).fetchall()
            result = [dict(r) for r in rows]
            print(f"[MemoryStore] Found {len(result)} matching episodes", flush=True)
            return result

    def recent_episodes(self, limit: int = 8) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute('''
            SELECT ts, title, detail, entities, importance
            FROM episodic_memory
            ORDER BY ts DESC
            LIMIT ?
            ''', (limit,)).fetchall()
            return [dict(r) for r in rows]
