"""
向量记忆插件
使用向量数据库进行语义搜索
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid
import hashlib

from .base import (
    MemoryPluginBase, 
    MemoryItem, 
    MemorySearchResult, 
    PluginInfo, 
    MemoryType
)


class VectorMemoryPlugin(MemoryPluginBase):
    """
    向量记忆插件
    
    特点：
    - 使用向量相似度进行语义搜索
    - 支持本地 embedding（可选使用 API）
    - 高效的相似度检索
    
    注意：完整的向量功能需要安装额外的依赖（sentence-transformers 或 openai）
    这里提供一个基于关键词的简化实现，可以后续扩展为真正的向量搜索
    """
    
    @classmethod
    def get_plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            id="vector_memory",
            name="向量记忆",
            description="使用向量相似度进行语义搜索，适合大规模记忆的快速检索。",
            version="1.0.0",
            author="Aurora Team",
            supports_vector_search=True,
            supports_graph=False,
            supports_temporal=True,
            config_schema={
                "embedding_model": {
                    "type": "string",
                    "default": "local",
                    "options": ["local", "openai", "sentence-transformers"],
                    "description": "Embedding 模型选择"
                },
                "similarity_threshold": {
                    "type": "number",
                    "default": 0.5,
                    "min": 0.0,
                    "max": 1.0,
                    "description": "相似度阈值"
                },
                "max_memories": {
                    "type": "integer",
                    "default": 10000,
                    "description": "最大记忆数量"
                }
            }
        )
    
    def __init__(self, user_id: str, storage_path: str, config: Dict[str, Any] = None):
        super().__init__(user_id, storage_path, config)
        self.db_path = os.path.join(storage_path, f"{user_id}_vector_memory.db")
        self.conn = None
        self._embedder = None
    
    def initialize(self) -> bool:
        """初始化插件"""
        try:
            os.makedirs(self.storage_path, exist_ok=True)
            
            # 初始化 SQLite
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            
            self._create_tables()
            self._init_embedder()
            
            self._initialized = True
            print(f"[VectorMemoryPlugin] Initialized for user: {self.user_id}")
            return True
        except Exception as e:
            print(f"[VectorMemoryPlugin] Initialization failed: {e}")
            return False
    
    def _create_tables(self):
        """创建数据库表"""
        cursor = self.conn.cursor()
        
        # 记忆表
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
                embedding TEXT,
                keywords TEXT DEFAULT '[]',
                created_at TEXT,
                updated_at TEXT
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance)")
        
        self.conn.commit()
    
    def _init_embedder(self):
        """初始化 embedding 模型"""
        embedding_model = self.config.get("embedding_model", "local")
        
        if embedding_model == "local":
            # 使用简单的关键词提取作为"伪向量"
            self._embedder = self._simple_keyword_embedder
        elif embedding_model == "sentence-transformers":
            try:
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                self._embedder = lambda text: model.encode(text).tolist()
            except ImportError:
                print("[VectorMemoryPlugin] sentence-transformers not installed, falling back to local")
                self._embedder = self._simple_keyword_embedder
        else:
            self._embedder = self._simple_keyword_embedder
    
    def _simple_keyword_embedder(self, text: str) -> List[str]:
        """简单的关键词提取（作为伪向量）"""
        import re
        # 提取中文和英文词汇
        words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text.lower())
        # 去重并保持顺序
        seen = set()
        keywords = []
        for w in words:
            if w not in seen and len(w) > 1:
                seen.add(w)
                keywords.append(w)
        return keywords
    
    def _calculate_keyword_similarity(self, keywords1: List[str], keywords2: List[str]) -> float:
        """计算关键词相似度"""
        if not keywords1 or not keywords2:
            return 0.0
        set1, set2 = set(keywords1), set(keywords2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0
    
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
        """添加记忆"""
        if not self._initialized:
            self.initialize()
        
        memory_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        # 生成 embedding/关键词
        keywords = self._embedder(content)
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO memories (id, content, timestamp, importance, memory_type, 
                                  tags, emotion_tags, topic_tags, entities, metadata, 
                                  keywords, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
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
            now,
            now
        ))
        
        self.conn.commit()
        return memory_id
    
    def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """根据ID获取记忆"""
        if not self._initialized:
            self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        
        if row:
            return self._row_to_memory_item(row)
        return None
    
    def _row_to_memory_item(self, row) -> MemoryItem:
        """将数据库行转换为 MemoryItem"""
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
            metadata=json.loads(row["metadata"])
        )
    
    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        if not self._initialized:
            self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆"""
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
            "metadata": "metadata"
        }
        
        for key, db_field in field_mapping.items():
            if key in updates:
                set_clauses.append(f"{db_field} = ?")
                value = updates[key]
                if isinstance(value, (list, dict)):
                    value = json.dumps(value)
                values.append(value)
        
        if not set_clauses:
            return False
        
        # 更新关键词（如果内容变了）
        if "content" in updates:
            keywords = self._embedder(updates["content"])
            set_clauses.append("keywords = ?")
            values.append(json.dumps(keywords))
        
        set_clauses.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(memory_id)
        
        cursor = self.conn.cursor()
        cursor.execute(
            f"UPDATE memories SET {', '.join(set_clauses)} WHERE id = ?",
            values
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
        """搜索记忆"""
        if not self._initialized:
            self.initialize()
        
        cursor = self.conn.cursor()
        
        # 基础查询
        sql = "SELECT * FROM memories WHERE 1=1"
        params = []
        
        # 时间过滤
        if time_start:
            sql += " AND timestamp >= ?"
            params.append(time_start.isoformat())
        if time_end:
            sql += " AND timestamp <= ?"
            params.append(time_end.isoformat())
        
        # 类型过滤
        if memory_type:
            sql += " AND memory_type = ?"
            params.append(memory_type.value)
        
        sql += " ORDER BY timestamp DESC"
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        results = []
        query_keywords = self._embedder(query) if query else []
        
        for row in rows:
            memory_item = self._row_to_memory_item(row)
            
            # 计算相关性分数
            score = 0.0
            reasons = []
            
            # 关键词相似度
            if query_keywords:
                row_keywords = json.loads(row["keywords"])
                similarity = self._calculate_keyword_similarity(query_keywords, row_keywords)
                score = max(score, similarity)
                if similarity > 0:
                    reasons.append(f"关键词匹配: {similarity:.2f}")
            
            # 标签匹配
            if tags:
                memory_tags = memory_item.topic_tags + memory_item.tags
                matched = set(tags) & set(memory_tags)
                if matched:
                    tag_score = len(matched) / len(tags)
                    score = max(score, tag_score)
                    reasons.append(f"标签匹配: {', '.join(matched)}")
            
            # 内容包含查询词
            if query and query.lower() in memory_item.content.lower():
                score = max(score, 0.8)
                reasons.append(f"内容包含 '{query}'")
            
            # 重要度加成
            score = score * 0.7 + memory_item.importance * 0.3
            
            results.append(MemorySearchResult(
                memory=memory_item,
                score=score,
                match_reason="; ".join(reasons) if reasons else "时间顺序"
            ))
        
        # 按分数排序
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]
    
    def get_recent_memories(self, limit: int = 20) -> List[MemoryItem]:
        """获取最近的记忆"""
        if not self._initialized:
            self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM memories ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        return [self._row_to_memory_item(row) for row in cursor.fetchall()]
    
    def get_important_memories(self, limit: int = 20, min_importance: float = 0.5) -> List[MemoryItem]:
        """获取重要的记忆"""
        if not self._initialized:
            self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM memories WHERE importance >= ? ORDER BY importance DESC LIMIT ?",
            (min_importance, limit)
        )
        return [self._row_to_memory_item(row) for row in cursor.fetchall()]
    
    def get_context_for_conversation(
        self,
        query: str = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """获取对话上下文"""
        if not self._initialized:
            self.initialize()
        
        # 搜索相关记忆
        if query:
            results = self.search(query=query, limit=limit)
            memories = [r.memory for r in results]
        else:
            memories = self.get_recent_memories(limit=limit)
        
        # 构建上下文字符串
        context_parts = []
        for mem in memories:
            time_str = mem.timestamp.strftime("%Y-%m-%d %H:%M")
            context_parts.append(f"[{time_str}] {mem.content}")
        
        return {
            "context": "\n".join(context_parts),
            "memories": [m.to_dict() for m in memories],
            "stats": self.get_stats(),
            "plugin": "vector_memory"
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._initialized:
            self.initialize()
        
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM memories")
        total = cursor.fetchone()["count"]
        
        cursor.execute("SELECT memory_type, COUNT(*) as count FROM memories GROUP BY memory_type")
        by_type = {row["memory_type"]: row["count"] for row in cursor.fetchall()}
        
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN importance >= 0.7 THEN 1 ELSE 0 END) as high,
                SUM(CASE WHEN importance >= 0.4 AND importance < 0.7 THEN 1 ELSE 0 END) as medium,
                SUM(CASE WHEN importance < 0.4 THEN 1 ELSE 0 END) as low
            FROM memories
        """)
        importance_row = cursor.fetchone()
        
        return {
            "total_memories": total,
            "by_type": by_type,
            "memory_by_importance": {
                "high": importance_row["high"] or 0,
                "medium": importance_row["medium"] or 0,
                "low": importance_row["low"] or 0
            },
            "plugin_info": self.get_plugin_info().to_dict()
        }
    
    def get_visualization_data(self) -> Dict[str, Any]:
        """获取可视化数据"""
        memories = self.get_recent_memories(limit=10000)  # 无上限
        stats = self.get_stats()
        
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
            "stats": stats
        }
    
    def save(self) -> bool:
        """保存（SQLite 自动保存）"""
        if self.conn:
            self.conn.commit()
            return True
        return False
    
    def clear_all(self) -> bool:
        """清空所有记忆"""
        if not self._initialized:
            self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM memories")
        self.conn.commit()
        return True
    
    def add_demo_data(self) -> Dict[str, Any]:
        """添加演示数据"""
        demo_memories = [
            {
                "content": "用户说今天心情不太好，工作压力大",
                "importance": 0.7,
                "emotion_tags": ["压力", "负面"],
                "topic_tags": ["工作", "情绪"]
            },
            {
                "content": "和用户聊了小明的事，小明是用户的大学室友",
                "importance": 0.5,
                "topic_tags": ["朋友", "回忆"],
            },
            {
                "content": "用户说晚上和女朋友小红一起吃了火锅",
                "importance": 0.6,
                "emotion_tags": ["开心"],
                "topic_tags": ["饮食", "约会"],
            },
            {
                "content": "用户提到下周要参加公司的季度review",
                "importance": 0.8,
                "topic_tags": ["工作", "计划"],
            },
            {
                "content": "用户说自己喜欢喝咖啡，特别是拿铁",
                "importance": 0.4,
                "topic_tags": ["偏好", "饮品"]
            }
        ]
        
        for mem in demo_memories:
            self.add_memory(**mem)
        
        return {"added": len(demo_memories)}
