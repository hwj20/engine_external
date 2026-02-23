"""
本地小模型重排记忆插件
使用本地小模型（优先 sentence-transformers MiniLM）进行记忆匹配和排序
"""

import os
import sys
import json
import math
import sqlite3
import re
import uuid
from collections import Counter
from datetime import datetime
from typing import Optional, List, Dict, Any

from .base import (
    MemoryPluginBase,
    MemoryItem,
    MemorySearchResult,
    PluginInfo,
    MemoryType,
)


class LocalRerankMemoryPlugin(MemoryPluginBase):
    """
    本地小模型重排记忆插件

    设计目标：
    - 在本地完成记忆检索，不依赖远端 API
    - 优先使用 MiniLM 进行语义匹配
    - 若本地模型不可用，降级到轻量哈希向量，确保可用性
    """

    DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"

    @classmethod
    def get_plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            id="local_rerank",
            name="本地小模型重排",
            description="使用本地小模型进行语义匹配与重排序，适合离线或低延迟场景。",
            version="1.0.0",
            author="Aurora Team",
            supports_vector_search=True,
            supports_graph=False,
            supports_temporal=True,
            config_schema={
                "model_backend": {
                    "type": "string",
                    "default": "minilm",
                    "options": ["minilm", "hash_fallback"],
                    "description": "本地编码后端：minilm（优先）或 hash_fallback（轻量降级）"
                },
                "model_name": {
                    "type": "string",
                    "default": cls.DEFAULT_MODEL_NAME,
                    "description": "sentence-transformers 模型名称"
                },
                "local_model_path": {
                    "type": "string",
                    "default": "",
                    "description": "本地模型目录（可选，存在时优先加载）"
                },
                "semantic_weight": {
                    "type": "number",
                    "default": 0.75,
                    "min": 0.0,
                    "max": 1.0,
                    "description": "语义相似度权重"
                },
                "keyword_weight": {
                    "type": "number",
                    "default": 0.15,
                    "min": 0.0,
                    "max": 1.0,
                    "description": "关键词重合权重"
                },
                "importance_weight": {
                    "type": "number",
                    "default": 0.10,
                    "min": 0.0,
                    "max": 1.0,
                    "description": "记忆重要度权重"
                },
            }
        )

    def __init__(self, user_id: str, storage_path: str, config: Dict[str, Any] = None):
        super().__init__(user_id, storage_path, config)
        self.db_path = self.config.get("shared_db_file") or os.path.join(storage_path, f"{user_id}_local_rerank_memory.db")
        self.conn = None
        self._encoder = None
        self._encoder_backend = "hash_fallback"
        self._encoder_name = "hash_fallback"

    def initialize(self) -> bool:
        try:
            os.makedirs(self.storage_path, exist_ok=True)
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._create_tables()
            self._init_encoder()
            self._initialized = True
            print(f"[LocalRerankMemoryPlugin] Initialized for user: {self.user_id}, backend={self._encoder_backend}")
            return True
        except Exception as e:
            print(f"[LocalRerankMemoryPlugin] Initialization failed: {e}")
            return False

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                importance REAL DEFAULT 0.5,
                memory_type TEXT DEFAULT 'episodic',
                tags TEXT DEFAULT '[]',
                emotion_tags TEXT DEFAULT '[]',
                topic_tags TEXT DEFAULT '[]',
                entities TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                keywords TEXT DEFAULT '[]',
                embedding TEXT DEFAULT '[]',
                created_at TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp_local_rerank ON memories(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_importance_local_rerank ON memories(importance)")
        self.conn.commit()

    def _init_encoder(self):
        backend = self.config.get("model_backend", "minilm")
        model_name = self.config.get("model_name", self.DEFAULT_MODEL_NAME)

        if backend == "hash_fallback":
            self._encoder_backend = "hash_fallback"
            self._encoder_name = "hash_fallback"
            self._encoder = self._encode_with_hash_vector
            return

        try:
            from sentence_transformers import SentenceTransformer
            load_target, source = self._resolve_model_load_target(model_name)
            model = SentenceTransformer(load_target)

            def encode_with_minilm(text: str) -> List[float]:
                emb = model.encode(text, normalize_embeddings=True)
                if hasattr(emb, "tolist"):
                    return emb.tolist()
                return list(emb)

            self._encoder = encode_with_minilm
            self._encoder_backend = "minilm"
            self._encoder_name = load_target
            print(f"[LocalRerankMemoryPlugin] MiniLM loaded from {source}: {load_target}")
        except Exception as e:
            print(f"[LocalRerankMemoryPlugin] MiniLM unavailable, fallback to hash encoder: {e}")
            self._encoder_backend = "hash_fallback"
            self._encoder_name = "hash_fallback"
            self._encoder = self._encode_with_hash_vector

    def _get_model_leaf_name(self, model_name: str) -> str:
        return (model_name or self.DEFAULT_MODEL_NAME).strip().split("/")[-1]

    def _get_runtime_model_root(self) -> str:
        # plugin storage: .../data/memory_plugins/local_rerank
        # runtime model root: .../data/models/sentence-transformers
        data_root = os.path.dirname(os.path.dirname(self.storage_path))
        return os.path.join(data_root, "models", "sentence-transformers")

    def _get_packaged_model_dir(self, model_name: str) -> str:
        leaf = self._get_model_leaf_name(model_name)
        if getattr(sys, 'frozen', False):
            # sys.executable -> .../resources/bin/backend/backend.exe (Windows)
            # or .../Contents/MacOS/backend (macOS) for Electron packaged app
            if sys.platform == "darwin":
                # macOS: Electron app structure
                resources_root = os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
            else:
                # Windows: PyInstaller app structure
                resources_root = os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
            return os.path.join(resources_root, "models", "sentence-transformers", leaf)

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        return os.path.join(project_root, "app", "resources", "models", "sentence-transformers", leaf)

    def _get_local_model_candidates(self, model_name: str) -> List[str]:
        candidates: List[str] = []
        cfg_local_path = (self.config.get("local_model_path") or "").strip()
        if cfg_local_path:
            candidates.append(cfg_local_path)

        packaged_dir = self._get_packaged_model_dir(model_name)
        if packaged_dir not in candidates:
            candidates.append(packaged_dir)

        runtime_dir = os.path.join(self._get_runtime_model_root(), self._get_model_leaf_name(model_name))
        if runtime_dir not in candidates:
            candidates.append(runtime_dir)

        return candidates

    def _resolve_model_load_target(self, model_name: str):
        for candidate in self._get_local_model_candidates(model_name):
            if candidate and os.path.isdir(candidate):
                return candidate, "local_path"
        return model_name, "hub"

    def get_local_model_status(self) -> Dict[str, Any]:
        model_name = self.config.get("model_name", self.DEFAULT_MODEL_NAME)
        candidates = self._get_local_model_candidates(model_name)
        existing_local_dirs = [p for p in candidates if p and os.path.isdir(p)]
        runtime_dir = os.path.join(self._get_runtime_model_root(), self._get_model_leaf_name(model_name))
        packaged_dir = self._get_packaged_model_dir(model_name)

        return {
            "plugin": "local_rerank",
            "configured_backend": self.config.get("model_backend", "minilm"),
            "encoder_backend": self._encoder_backend,
            "encoder_name": self._encoder_name,
            "model_name": model_name,
            "local_model_path": (self.config.get("local_model_path") or "").strip(),
            "runtime_model_dir": runtime_dir,
            "packaged_model_dir": packaged_dir,
            "local_model_exists": len(existing_local_dirs) > 0,
            "existing_local_dirs": existing_local_dirs,
            "is_model_ready": self._encoder_backend == "minilm",
        }

    def download_local_model(self, force_download: bool = False) -> Dict[str, Any]:
        model_name = self.config.get("model_name", self.DEFAULT_MODEL_NAME)
        model_leaf = self._get_model_leaf_name(model_name)
        runtime_root = self._get_runtime_model_root()
        target_dir = os.path.join(runtime_root, model_leaf)
        os.makedirs(runtime_root, exist_ok=True)

        downloaded = False
        if force_download or not os.path.isdir(target_dir):
            repo_id = model_name if "/" in model_name else f"sentence-transformers/{model_name}"
            try:
                from huggingface_hub import snapshot_download
                snapshot_download(
                    repo_id=repo_id,
                    local_dir=target_dir,
                    local_dir_use_symlinks=False,
                    resume_download=True,
                )
                downloaded = True
            except Exception as e:
                raise RuntimeError(f"Model download failed: {e}")

        self.config["model_backend"] = "minilm"
        self.config["local_model_path"] = target_dir
        self._init_encoder()

        status = self.get_local_model_status()
        status["downloaded"] = downloaded
        return status

    def _extract_keywords(self, text: str) -> List[str]:
        if not text:
            return []
        words = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z]+", text.lower())
        seen = set()
        out = []
        for w in words:
            if len(w) <= 1:
                continue
            if w in seen:
                continue
            seen.add(w)
            out.append(w)
        return out

    def _encode_with_hash_vector(self, text: str, dim: int = 128) -> List[float]:
        tokens = re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9]+", (text or "").lower())
        if not tokens:
            return [0.0] * dim

        vec = [0.0] * dim
        counts = Counter(tokens)
        total = sum(counts.values()) or 1
        for token, cnt in counts.items():
            bucket = hash(token) % dim
            vec[bucket] += cnt / total

        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def _encode(self, text: str) -> List[float]:
        return self._encoder(text) if self._encoder else self._encode_with_hash_vector(text)

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        return sum(x * y for x, y in zip(a, b))

    def _keyword_overlap(self, q_keywords: List[str], m_keywords: List[str]) -> float:
        if not q_keywords or not m_keywords:
            return 0.0
        s1, s2 = set(q_keywords), set(m_keywords)
        union = len(s1 | s2)
        if union == 0:
            return 0.0
        return len(s1 & s2) / union

    def _row_to_memory_item(self, row) -> MemoryItem:
        return MemoryItem(
            id=row["id"],
            content=row["content"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            importance=row["importance"],
            memory_type=MemoryType(row["memory_type"]),
            tags=json.loads(row["tags"]),
            emotion_tags=json.loads(row["emotion_tags"]),
            topic_tags=json.loads(row["topic_tags"]),
            entities=json.loads(row["entities"]),
            metadata=json.loads(row["metadata"]),
        )

    def add_memory(
        self,
        content: str,
        importance: float = 0.5,
        memory_type: MemoryType = MemoryType.EPISODIC,
        tags: List[str] = None,
        emotion_tags: List[str] = None,
        topic_tags: List[str] = None,
        entities: List[Dict[str, Any]] = None,
        metadata: Dict[str, Any] = None,
    ) -> str:
        if not self._initialized:
            self.initialize()

        memory_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        keywords = self._extract_keywords(content)
        embedding = self._encode(content)

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO memories (id, content, timestamp, importance, memory_type,
                                  tags, emotion_tags, topic_tags, entities, metadata,
                                  keywords, embedding, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                content,
                now,
                importance,
                memory_type.value,
                json.dumps(tags or []),
                json.dumps(emotion_tags or []),
                json.dumps(topic_tags or []),
                json.dumps(entities or []),
                json.dumps(metadata or {}),
                json.dumps(keywords),
                json.dumps(embedding),
                now,
                now,
            ),
        )
        self.conn.commit()
        return memory_id

    def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        if not self._initialized:
            self.initialize()

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_memory_item(row)

    def delete_memory(self, memory_id: str) -> bool:
        if not self._initialized:
            self.initialize()
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        if not self._initialized:
            self.initialize()

        set_clauses = []
        values = []

        field_mapping = {
            "content": "content",
            "importance": "importance",
            "tags": "tags",
            "emotion_tags": "emotion_tags",
            "topic_tags": "topic_tags",
            "entities": "entities",
            "metadata": "metadata",
        }

        for key, db_field in field_mapping.items():
            if key in updates:
                value = updates[key]
                if isinstance(value, (list, dict)):
                    value = json.dumps(value)
                set_clauses.append(f"{db_field} = ?")
                values.append(value)

        if "content" in updates:
            new_keywords = self._extract_keywords(updates["content"])
            new_embedding = self._encode(updates["content"])
            set_clauses.append("keywords = ?")
            values.append(json.dumps(new_keywords))
            set_clauses.append("embedding = ?")
            values.append(json.dumps(new_embedding))

        if not set_clauses:
            return False

        set_clauses.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(memory_id)

        cursor = self.conn.cursor()
        cursor.execute(
            f"UPDATE memories SET {', '.join(set_clauses)} WHERE id = ?",
            values,
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def search(
        self,
        query: str = None,
        time_start: datetime = None,
        time_end: datetime = None,
        tags: List[str] = None,
        memory_type: MemoryType = None,
        limit: int = 10,
    ) -> List[MemorySearchResult]:
        if not self._initialized:
            self.initialize()

        cursor = self.conn.cursor()
        sql = "SELECT * FROM memories WHERE 1=1"
        params = []

        if time_start:
            sql += " AND timestamp >= ?"
            params.append(time_start.isoformat())
        if time_end:
            sql += " AND timestamp <= ?"
            params.append(time_end.isoformat())
        if memory_type:
            sql += " AND memory_type = ?"
            params.append(memory_type.value)

        sql += " ORDER BY timestamp DESC"
        cursor.execute(sql, params)
        rows = cursor.fetchall()

        semantic_weight = float(self.config.get("semantic_weight", 0.75))
        keyword_weight = float(self.config.get("keyword_weight", 0.15))
        importance_weight = float(self.config.get("importance_weight", 0.10))

        query_embedding = self._encode(query) if query else []
        query_keywords = self._extract_keywords(query) if query else []

        results: List[MemorySearchResult] = []

        for row in rows:
            mem = self._row_to_memory_item(row)

            if tags:
                memory_tags = set(mem.tags + mem.topic_tags)
                if not (memory_tags & set(tags)):
                    continue

            memory_embedding = json.loads(row["embedding"]) if row["embedding"] else []
            memory_keywords = json.loads(row["keywords"]) if row["keywords"] else []

            semantic_score = self._cosine_similarity(query_embedding, memory_embedding) if query else 0.0
            keyword_score = self._keyword_overlap(query_keywords, memory_keywords) if query else 0.0
            importance_score = float(mem.importance or 0.0)

            final_score = (
                semantic_score * semantic_weight
                + keyword_score * keyword_weight
                + importance_score * importance_weight
            ) if query else importance_score

            match_reason = (
                f"semantic={semantic_score:.3f}, keyword={keyword_score:.3f}, importance={importance_score:.3f}, backend={self._encoder_backend}"
                if query else
                "importance ranking"
            )

            results.append(MemorySearchResult(memory=mem, score=final_score, match_reason=match_reason))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def get_recent_memories(self, limit: int = 20) -> List[MemoryItem]:
        if not self._initialized:
            self.initialize()
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM memories ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [self._row_to_memory_item(row) for row in cursor.fetchall()]

    def get_important_memories(self, limit: int = 20, min_importance: float = 0.5) -> List[MemoryItem]:
        if not self._initialized:
            self.initialize()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM memories WHERE importance >= ? ORDER BY importance DESC, timestamp DESC LIMIT ?",
            (min_importance, limit),
        )
        return [self._row_to_memory_item(row) for row in cursor.fetchall()]

    def get_context_for_conversation(self, query: str = None, limit: int = 10) -> Dict[str, Any]:
        if query:
            memories = [r.memory for r in self.search(query=query, limit=limit)]
        else:
            memories = self.get_recent_memories(limit=limit)

        context_lines = []
        for m in memories:
            ts = m.timestamp.strftime("%Y-%m-%d %H:%M")
            context_lines.append(f"[{ts}] {m.content}")

        return {
            "context": "\n".join(context_lines),
            "memories": [m.to_dict() for m in memories],
            "plugin": "local_rerank",
            "encoder_backend": self._encoder_backend,
            "encoder_name": self._encoder_name,
        }

    def get_stats(self) -> Dict[str, Any]:
        if not self._initialized:
            self.initialize()

        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM memories")
        total = cursor.fetchone()["count"]

        cursor.execute(
            """
            SELECT
                SUM(CASE WHEN importance >= 0.7 THEN 1 ELSE 0 END) AS high,
                SUM(CASE WHEN importance >= 0.4 AND importance < 0.7 THEN 1 ELSE 0 END) AS medium,
                SUM(CASE WHEN importance < 0.4 THEN 1 ELSE 0 END) AS low
            FROM memories
            """
        )
        row = cursor.fetchone()

        return {
            "total_memories": total,
            "memory_by_importance": {
                "high": row["high"] or 0,
                "medium": row["medium"] or 0,
                "low": row["low"] or 0,
            },
            "encoder_backend": self._encoder_backend,
            "encoder_name": self._encoder_name,
            "plugin_info": self.get_plugin_info().to_dict(),
        }

    def get_visualization_data(self) -> Dict[str, Any]:
        memories = self.get_recent_memories(limit=10000)
        return {
            "recent_memories": [
                {
                    "id": m.id,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "importance": m.importance,
                    "emotion_tags": m.emotion_tags,
                    "topic_tags": m.topic_tags,
                }
                for m in memories
            ],
            "stats": self.get_stats(),
        }

    def save(self) -> bool:
        if self.conn:
            self.conn.commit()
            return True
        return False

    def clear_all(self) -> bool:
        if not self._initialized:
            self.initialize()
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM memories")
        self.conn.commit()
        return True