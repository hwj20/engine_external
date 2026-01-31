"""
Memory Framework API
连接 memory_framework 和 FastAPI backend
"""
import sys
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

# 添加 memory_framework 到路径
MEMORY_FRAMEWORK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 
    "memory_framework", 
    "memory_framework"
)
sys.path.insert(0, MEMORY_FRAMEWORK_PATH)

from schema.models import MemoryNode, Entity, EntityType, RelationType
from schema.temporal_tree import TemporalMemoryTree
from schema.knowledge_graph import KnowledgeGraph
from core.memory_manager import MemoryManager


class MemoryService:
    """记忆服务 - 封装 MemoryManager"""
    
    _instance: Optional['MemoryService'] = None
    
    def __init__(self, user_id: str = "default_user", storage_path: str = None):
        self.user_id = user_id
        if storage_path is None:
            storage_path = os.path.join(os.path.dirname(__file__), "data", "memory_framework")
        self.manager = MemoryManager(user_id=user_id, storage_path=storage_path)
        print(f"[MemoryService] Initialized for user: {user_id}, storage: {storage_path}", flush=True)
    
    @classmethod
    def get_instance(cls, user_id: str = "default_user") -> 'MemoryService':
        """单例模式获取实例"""
        if cls._instance is None:
            cls._instance = cls(user_id)
        return cls._instance
    
    def add_memory(
        self,
        content: str,
        importance: float = 0.5,
        emotion_tags: List[str] = None,
        topic_tags: List[str] = None,
        entities: List[Dict[str, Any]] = None
    ) -> str:
        """添加记忆"""
        memory_id = self.manager.add_memory(
            content=content,
            importance=importance,
            emotion_tags=emotion_tags or [],
            topic_tags=topic_tags or [],
            entities=entities
        )
        self.manager.save()
        return memory_id
    
    def get_memory_tree_summary(self) -> Dict[str, Any]:
        """获取记忆树摘要"""
        tree = self.manager.memory_tree
        
        summary = {
            "total_memories": len([n for n in tree.nodes.values() if n.time_grain == "event"]),
            "years": [],
            "recent_memories": []
        }
        
        # 按年份组织
        for year_key, year_id in tree.year_index.items():
            year_node = tree.nodes.get(year_id)
            if year_node:
                year_data = {
                    "year": year_key,
                    "months": []
                }
                for month_id in year_node.children_ids:
                    month_node = tree.nodes.get(month_id)
                    if month_node:
                        month_events = self._count_events_under_node(tree, month_node)
                        year_data["months"].append({
                            "month": month_node.content,
                            "event_count": month_events
                        })
                summary["years"].append(year_data)
        
        # 获取最近记忆
        all_events = [n for n in tree.nodes.values() if n.time_grain == "event"]
        all_events.sort(key=lambda x: x.timestamp, reverse=True)
        
        for event in all_events[:20]:
            summary["recent_memories"].append({
                "id": event.id,
                "content": event.content,
                "timestamp": event.timestamp.isoformat(),
                "importance": event.base_importance,
                "effective_importance": event.calculate_effective_importance(),
                "emotion_tags": event.emotion_tags,
                "topic_tags": event.topic_tags,
                "mention_count": event.mention_count
            })
        
        return summary
    
    def _count_events_under_node(self, tree: TemporalMemoryTree, node: MemoryNode) -> int:
        """递归计算节点下的事件数"""
        if node.time_grain == "event":
            return 1
        count = 0
        for child_id in node.children_ids:
            child = tree.nodes.get(child_id)
            if child:
                count += self._count_events_under_node(tree, child)
        return count
    
    def get_knowledge_graph_summary(self) -> Dict[str, Any]:
        """获取知识图谱摘要"""
        graph = self.manager.knowledge_graph
        
        summary = {
            "user_profile": graph.user_profile.to_dict(),
            "total_entities": len(graph.entities),
            "total_relationships": len(graph.relationships),
            "entities_by_type": {},
            "entities": [],
            "relationships": []
        }
        
        # 按类型统计实体
        for entity_type, entity_ids in graph.type_index.items():
            summary["entities_by_type"][entity_type.value] = len(entity_ids)
        
        # 所有实体
        for entity in graph.entities.values():
            summary["entities"].append({
                "id": entity.id,
                "name": entity.name,
                "type": entity.entity_type.value,
                "importance": entity.importance,
                "mention_count": entity.mention_count,
                "attributes": entity.attributes,
                "sentiment": entity.sentiment
            })
        
        # 所有关系
        for rel in graph.relationships.values():
            source = graph.entities.get(rel.source_id)
            target = graph.entities.get(rel.target_id)
            summary["relationships"].append({
                "id": rel.id,
                "source": source.name if source else rel.source_id,
                "target": target.name if target else rel.target_id,
                "type": rel.relation_type.value,
                "description": rel.description,
                "confidence": rel.confidence
            })
        
        return summary
    
    def search_memories(
        self,
        query: str = None,
        time_hint: str = None,
        topic: str = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """搜索记忆"""
        results = self.manager.search_memories(
            query=query,
            time_hint=time_hint,
            topic=topic,
            limit=limit
        )
        
        return [{
            "id": m.id,
            "content": m.content,
            "timestamp": m.timestamp.isoformat(),
            "importance": m.base_importance,
            "effective_importance": m.calculate_effective_importance(),
            "emotion_tags": m.emotion_tags,
            "topic_tags": m.topic_tags
        } for m in results]
    
    def get_context_for_conversation(self, query: str = None, limit: int = 10) -> Dict[str, Any]:
        """获取对话上下文（用于注入 LLM）"""
        topics = [query] if query else None
        context_str = self.manager.get_full_context(current_topics=topics)
        stats = self.manager.get_stats()
        return {
            "context": context_str,
            "stats": stats
        }
    
    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        tree = self.manager.memory_tree
        if memory_id in tree.nodes:
            node = tree.nodes[memory_id]
            # 从父节点移除
            if node.parent_id and node.parent_id in tree.nodes:
                parent = tree.nodes[node.parent_id]
                if memory_id in parent.children_ids:
                    parent.children_ids.remove(memory_id)
            # 删除节点
            del tree.nodes[memory_id]
            self.manager.save()
            return True
        return False
    
    def add_demo_data(self):
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
                "entities": [
                    {"name": "小明", "type": "person", "relation": "朋友", "relation_desc": "大学室友"}
                ]
            },
            {
                "content": "用户说晚上和女朋友小红一起吃了火锅",
                "importance": 0.6,
                "emotion_tags": ["开心"],
                "topic_tags": ["饮食", "约会"],
                "entities": [
                    {"name": "小红", "type": "person", "relation": "恋人", "relation_desc": "女朋友"}
                ]
            },
            {
                "content": "用户提到下周要参加公司的季度review",
                "importance": 0.8,
                "topic_tags": ["工作", "计划"],
                "entities": [
                    {"name": "季度review", "type": "event"}
                ]
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


# Pydantic 模型
class AddMemoryRequest(BaseModel):
    content: str
    importance: float = 0.5
    emotion_tags: List[str] = []
    topic_tags: List[str] = []
    entities: List[Dict[str, Any]] = []


class SearchMemoryRequest(BaseModel):
    query: Optional[str] = None
    time_hint: Optional[str] = None
    topic: Optional[str] = None
    limit: int = 10


class DeleteMemoryRequest(BaseModel):
    memory_id: str
