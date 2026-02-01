"""
简单 SQLite 记忆插件
轻量级的记忆存储，适合入门使用
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid

from .base import (
    MemoryPluginBase, 
    MemoryItem, 
    MemorySearchResult, 
    PluginInfo, 
    MemoryType
)


class SimpleSQLitePlugin(MemoryPluginBase):
    """
    简单 SQLite 记忆插件
    
    特点：
    - 轻量级，无额外依赖
    - 简单的文本搜索
    - 适合小规模记忆存储
    """
    
    @classmethod
    def get_plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            id="simple_sqlite",
            name="简单记忆",
            description="轻量级 SQLite 存储，简单易用，适合入门。",
            version="1.0.0",
            author="Aurora Team",
            supports_vector_search=False,
            supports_graph=False,
            supports_temporal=True,
            config_schema={
                "max_memories": {
                    "type": "integer",
                    "default": 1000,
                    "description": "最大记忆数量"
                }
            }
        )
    
    def __init__(self, user_id: str, storage_path: str, config: Dict[str, Any] = None):
        super().__init__(user_id, storage_path, config)
        self.db_path = os.path.join(storage_path, f"{user_id}_simple_memory.db")
        self.conn = None
    
    def initialize(self) -> bool:
        """初始化插件"""
        try:
            os.makedirs(self.storage_path, exist_ok=True)
            
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            
            self._create_tables()
            
            self._initialized = True
            print(f"[SimpleSQLitePlugin] Initialized for user: {self.user_id}")
            return True
        except Exception as e:
            print(f"[SimpleSQLitePlugin] Initialization failed: {e}")
            return False
    
    def _create_tables(self):
        """创建数据库表"""
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
                metadata TEXT DEFAULT '{}'
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance)")
        
        self.conn.commit()
    
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
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO memories (id, content, timestamp, importance, memory_type, 
                                  tags, emotion_tags, topic_tags, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            memory_id,
            content,
            now,
            importance,
            memory_type.value,
            json.dumps(tags or []),
            json.dumps(emotion_tags or []),
            json.dumps(topic_tags or []),
            json.dumps(metadata or {})
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
        
        for key in ["content", "importance", "tags", "emotion_tags", "topic_tags", "metadata"]:
            if key in updates:
                set_clauses.append(f"{key} = ?")
                value = updates[key]
                if isinstance(value, (list, dict)):
                    value = json.dumps(value)
                values.append(value)
        
        if not set_clauses:
            return False
        
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
        
        sql = "SELECT * FROM memories WHERE 1=1"
        params = []
        
        # 内容搜索
        if query:
            sql += " AND content LIKE ?"
            params.append(f"%{query}%")
        
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
        
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        
        results = []
        for row in cursor.fetchall():
            memory_item = self._row_to_memory_item(row)
            
            score = memory_item.importance
            reasons = []
            
            if query and query.lower() in memory_item.content.lower():
                score = max(score, 0.8)
                reasons.append(f"内容包含 '{query}'")
            
            if tags:
                memory_tags = memory_item.topic_tags + memory_item.tags
                matched = set(tags) & set(memory_tags)
                if matched:
                    reasons.append(f"标签匹配: {', '.join(matched)}")
            
            results.append(MemorySearchResult(
                memory=memory_item,
                score=score,
                match_reason="; ".join(reasons) if reasons else "时间顺序"
            ))
        
        return results
    
    def get_recent_memories(self, limit: int = 20) -> List[MemoryItem]:
        """获取最近的记忆"""
        if not self._initialized:
            self.initialize()
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM memories ORDER BY timestamp DESC LIMIT ?", (limit,))
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
        if query:
            results = self.search(query=query, limit=limit)
            memories = [r.memory for r in results]
        else:
            memories = self.get_recent_memories(limit=limit)
        
        context_parts = []
        for mem in memories:
            time_str = mem.timestamp.strftime("%Y-%m-%d %H:%M")
            context_parts.append(f"[{time_str}] {mem.content}")
        
        return {
            "context": "\n".join(context_parts),
            "memories": [m.to_dict() for m in memories],
            "plugin": "simple_sqlite"
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._initialized:
            self.initialize()
        
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM memories")
        total = cursor.fetchone()["count"]
        
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN importance >= 0.7 THEN 1 ELSE 0 END) as high,
                SUM(CASE WHEN importance >= 0.4 AND importance < 0.7 THEN 1 ELSE 0 END) as medium,
                SUM(CASE WHEN importance < 0.4 THEN 1 ELSE 0 END) as low
            FROM memories
        """)
        row = cursor.fetchone()
        
        return {
            "total_memories": total,
            "memory_by_importance": {
                "high": row["high"] or 0,
                "medium": row["medium"] or 0,
                "low": row["low"] or 0
            },
            "plugin_info": self.get_plugin_info().to_dict()
        }
    
    def get_visualization_data(self) -> Dict[str, Any]:
        """获取可视化数据"""
        memories = self.get_recent_memories(limit=50)
        
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
            "stats": self.get_stats()
        }
    
    def save(self) -> bool:
        """保存"""
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
            {"content": "用户喜欢喝咖啡，特别是拿铁", "importance": 0.4, "topic_tags": ["偏好", "饮品"]},
            {"content": "用户今天心情不太好", "importance": 0.6, "emotion_tags": ["负面"], "topic_tags": ["情绪"]},
            {"content": "用户下周有重要会议", "importance": 0.8, "topic_tags": ["工作", "计划"]},
        ]
        
        for mem in demo_memories:
            self.add_memory(**mem)
        
        return {"added": len(demo_memories)}
