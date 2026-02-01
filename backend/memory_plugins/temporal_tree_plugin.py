"""
时间树记忆插件
封装现有的 memory_framework，支持时间线性记忆和知识图谱
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import uuid

from .base import (
    MemoryPluginBase, 
    MemoryItem, 
    MemorySearchResult, 
    PluginInfo, 
    MemoryType
)

# 添加 memory_framework 到路径
MEMORY_FRAMEWORK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
    "memory_framework", 
    "memory_framework"
)
if MEMORY_FRAMEWORK_PATH not in sys.path:
    sys.path.insert(0, MEMORY_FRAMEWORK_PATH)


class TemporalTreePlugin(MemoryPluginBase):
    """
    时间树记忆插件
    
    特点：
    - 按时间层级组织记忆（年 → 月 → 周 → 日 → 事件）
    - 支持艾宾浩斯遗忘曲线
    - 支持知识图谱（实体和关系）
    - 24小时自动压缩机制
    """
    
    @classmethod
    def get_plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            id="temporal_tree",
            name="时间树记忆",
            description="按时间层级组织记忆，支持艾宾浩斯遗忘曲线和知识图谱。模拟人类记忆的双系统架构。",
            version="1.0.0",
            author="Aurora Team",
            supports_vector_search=False,
            supports_graph=True,
            supports_temporal=True,
            config_schema={
                "forgetting_enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否启用遗忘曲线"
                },
                "consolidation_enabled": {
                    "type": "boolean", 
                    "default": True,
                    "description": "是否启用记忆压缩"
                },
                "base_retention": {
                    "type": "number",
                    "default": 0.8,
                    "min": 0.1,
                    "max": 1.0,
                    "description": "基础记忆保留率"
                }
            }
        )
    
    def __init__(self, user_id: str, storage_path: str, config: Dict[str, Any] = None):
        super().__init__(user_id, storage_path, config)
        self.manager = None
        self._import_framework()
    
    def _import_framework(self):
        """延迟导入 memory_framework 模块"""
        try:
            from schema.models import MemoryNode, Entity, EntityType, RelationType
            from schema.temporal_tree import TemporalMemoryTree
            from schema.knowledge_graph import KnowledgeGraph
            from core.memory_manager import MemoryManager
            
            self._MemoryNode = MemoryNode
            self._Entity = Entity
            self._EntityType = EntityType
            self._RelationType = RelationType
            self._TemporalMemoryTree = TemporalMemoryTree
            self._KnowledgeGraph = KnowledgeGraph
            self._MemoryManager = MemoryManager
            return True
        except ImportError as e:
            print(f"[TemporalTreePlugin] Failed to import memory_framework: {e}")
            return False
    
    def initialize(self) -> bool:
        """初始化插件"""
        try:
            os.makedirs(self.storage_path, exist_ok=True)
            
            # 创建 MemoryManager
            self.manager = self._MemoryManager(
                user_id=self.user_id,
                storage_path=self.storage_path
            )
            
            self._initialized = True
            print(f"[TemporalTreePlugin] Initialized for user: {self.user_id}")
            return True
        except Exception as e:
            print(f"[TemporalTreePlugin] Initialization failed: {e}")
            return False
    
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
        
        # 合并 tags 到 topic_tags
        all_topic_tags = list(topic_tags or [])
        if tags:
            all_topic_tags.extend(tags)
        
        memory_id = self.manager.add_memory(
            content=content,
            importance=importance,
            emotion_tags=emotion_tags or [],
            topic_tags=all_topic_tags,
            entities=entities
        )
        
        self.manager.save()
        return memory_id
    
    def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """根据ID获取记忆"""
        if not self._initialized:
            self.initialize()
        
        node = self.manager.memory_tree.nodes.get(memory_id)
        if node and node.time_grain == "event":
            return self._node_to_memory_item(node)
        return None
    
    def _node_to_memory_item(self, node) -> MemoryItem:
        """将 MemoryNode 转换为 MemoryItem"""
        return MemoryItem(
            id=node.id,
            content=node.content,
            timestamp=node.timestamp,
            importance=node.calculate_effective_importance(),
            memory_type=MemoryType.EPISODIC,
            tags=[],
            emotion_tags=node.emotion_tags,
            topic_tags=node.topic_tags,
            entities=[],
            metadata={
                "base_importance": node.base_importance,
                "mention_count": node.mention_count,
                "time_grain": node.time_grain,
            }
        )
    
    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        if not self._initialized:
            self.initialize()
        
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
    
    def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆"""
        if not self._initialized:
            self.initialize()
        
        tree = self.manager.memory_tree
        if memory_id in tree.nodes:
            node = tree.nodes[memory_id]
            if "content" in updates:
                node.content = updates["content"]
            if "importance" in updates:
                node.base_importance = updates["importance"]
            if "emotion_tags" in updates:
                node.emotion_tags = updates["emotion_tags"]
            if "topic_tags" in updates:
                node.topic_tags = updates["topic_tags"]
            self.manager.save()
            return True
        return False
    
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
        
        # 使用 manager 的搜索功能
        results = self.manager.search_memories(
            query=query,
            time_hint=None,  # 可以根据 time_start/time_end 转换
            topic=tags[0] if tags else None,
            limit=limit
        )
        
        search_results = []
        for node in results:
            # 时间过滤
            if time_start and node.timestamp < time_start:
                continue
            if time_end and node.timestamp > time_end:
                continue
            
            memory_item = self._node_to_memory_item(node)
            score = node.calculate_effective_importance()
            
            # 计算匹配原因
            reasons = []
            if query and query.lower() in node.content.lower():
                reasons.append(f"内容包含 '{query}'")
            if tags:
                matched_tags = [t for t in tags if t in node.topic_tags]
                if matched_tags:
                    reasons.append(f"标签匹配: {', '.join(matched_tags)}")
            
            search_results.append(MemorySearchResult(
                memory=memory_item,
                score=score,
                match_reason="; ".join(reasons) if reasons else "相关性匹配"
            ))
        
        return search_results[:limit]
    
    def get_recent_memories(self, limit: int = 20) -> List[MemoryItem]:
        """获取最近的记忆"""
        if not self._initialized:
            self.initialize()
        
        tree = self.manager.memory_tree
        all_events = [n for n in tree.nodes.values() if n.time_grain == "event"]
        all_events.sort(key=lambda x: x.timestamp, reverse=True)
        
        return [self._node_to_memory_item(n) for n in all_events[:limit]]
    
    def get_important_memories(self, limit: int = 20, min_importance: float = 0.5) -> List[MemoryItem]:
        """获取重要的记忆"""
        if not self._initialized:
            self.initialize()
        
        tree = self.manager.memory_tree
        all_events = [n for n in tree.nodes.values() 
                      if n.time_grain == "event" and n.calculate_effective_importance() >= min_importance]
        all_events.sort(key=lambda x: x.calculate_effective_importance(), reverse=True)
        
        return [self._node_to_memory_item(n) for n in all_events[:limit]]
    
    def get_context_for_conversation(
        self,
        query: str = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """获取对话上下文"""
        if not self._initialized:
            self.initialize()
        
        topics = [query] if query else None
        context_str = self.manager.get_full_context(current_topics=topics)
        stats = self.manager.get_stats()
        
        return {
            "context": context_str,
            "stats": stats,
            "plugin": "temporal_tree"
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._initialized:
            self.initialize()
        
        stats = self.manager.get_stats()
        graph = self.manager.knowledge_graph
        
        return {
            "total_memories": stats.get("total_memories", 0),
            "total_entities": len(graph.entities),
            "total_relationships": len(graph.relationships),
            "memory_by_importance": self._get_importance_distribution(),
            "plugin_info": self.get_plugin_info().to_dict()
        }
    
    def _get_importance_distribution(self) -> Dict[str, int]:
        """获取重要度分布"""
        tree = self.manager.memory_tree
        distribution = {"high": 0, "medium": 0, "low": 0}
        
        for node in tree.nodes.values():
            if node.time_grain == "event":
                imp = node.calculate_effective_importance()
                if imp >= 0.7:
                    distribution["high"] += 1
                elif imp >= 0.4:
                    distribution["medium"] += 1
                else:
                    distribution["low"] += 1
        
        return distribution
    
    def get_visualization_data(self) -> Dict[str, Any]:
        """获取可视化数据"""
        if not self._initialized:
            self.initialize()
        
        tree = self.manager.memory_tree
        graph = self.manager.knowledge_graph
        
        # 记忆树摘要
        tree_summary = {
            "total_memories": len([n for n in tree.nodes.values() if n.time_grain == "event"]),
            "years": [],
            "recent_memories": []
        }
        
        # 按年份组织
        for year_key, year_id in tree.year_index.items():
            year_node = tree.nodes.get(year_id)
            if year_node:
                year_data = {"year": year_key, "months": []}
                for month_id in year_node.children_ids:
                    month_node = tree.nodes.get(month_id)
                    if month_node:
                        month_events = self._count_events_under_node(tree, month_node)
                        year_data["months"].append({
                            "month": month_node.content,
                            "event_count": month_events
                        })
                tree_summary["years"].append(year_data)
        
        # 最近记忆（无上限）
        all_events = [n for n in tree.nodes.values() if n.time_grain == "event"]
        all_events.sort(key=lambda x: x.timestamp, reverse=True)
        
        for event in all_events:
            tree_summary["recent_memories"].append({
                "id": event.id,
                "content": event.content,
                "timestamp": event.timestamp.isoformat(),
                "importance": event.base_importance,
                "effective_importance": event.calculate_effective_importance(),
                "emotion_tags": event.emotion_tags,
                "topic_tags": event.topic_tags,
                "mention_count": event.mention_count
            })
        
        # 知识图谱摘要
        graph_summary = {
            "user_profile": graph.user_profile.to_dict(),
            "total_entities": len(graph.entities),
            "total_relationships": len(graph.relationships),
            "entities_by_type": {},
            "entities": [],
            "relationships": []
        }
        
        for entity_type, entity_ids in graph.type_index.items():
            graph_summary["entities_by_type"][entity_type.value] = len(entity_ids)
        
        for entity in graph.entities.values():
            graph_summary["entities"].append({
                "id": entity.id,
                "name": entity.name,
                "type": entity.entity_type.value,
                "importance": entity.importance,
                "mention_count": entity.mention_count,
                "attributes": entity.attributes,
                "sentiment": entity.sentiment
            })
        
        for rel in graph.relationships.values():
            source = graph.entities.get(rel.source_id)
            target = graph.entities.get(rel.target_id)
            graph_summary["relationships"].append({
                "id": rel.id,
                "source": source.name if source else rel.source_id,
                "target": target.name if target else rel.target_id,
                "type": rel.relation_type.value,
                "description": rel.description,
                "confidence": rel.confidence
            })
        
        return {
            "memory_tree": tree_summary,
            "knowledge_graph": graph_summary
        }
    
    def _count_events_under_node(self, tree, node) -> int:
        """递归计算节点下的事件数"""
        if node.time_grain == "event":
            return 1
        count = 0
        for child_id in node.children_ids:
            child = tree.nodes.get(child_id)
            if child:
                count += self._count_events_under_node(tree, child)
        return count
    
    def save(self) -> bool:
        """保存"""
        if self.manager:
            self.manager.save()
            return True
        return False
    
    def clear_all(self) -> bool:
        """清空所有记忆"""
        if not self._initialized:
            self.initialize()
        
        self.manager.memory_tree = self._TemporalMemoryTree()
        self.manager.knowledge_graph = self._KnowledgeGraph(self.user_id)
        self.manager.save()
        return True
    
    # ==================== 知识图谱相关方法 ====================
    
    def add_entity(self, name: str, entity_type: str, attributes: Dict[str, Any] = None) -> str:
        """添加实体"""
        if not self._initialized:
            self.initialize()
        
        # 转换 entity_type
        entity_type_enum = getattr(self._EntityType, entity_type.upper(), self._EntityType.CONCEPT)
        
        entity = self._Entity(
            id=str(uuid.uuid4()),
            name=name,
            entity_type=entity_type_enum,
            attributes=attributes or {}
        )
        
        self.manager.knowledge_graph.entities[entity.id] = entity
        self.manager.save()
        return entity.id
    
    def add_relationship(self, source_id: str, target_id: str, relation_type: str) -> str:
        """添加关系"""
        if not self._initialized:
            self.initialize()
        
        # 这里简化处理，实际应该创建 Relationship 对象
        from schema.models import Relationship
        
        relation_type_enum = getattr(self._RelationType, relation_type.upper(), self._RelationType.RELATED_TO)
        
        rel = Relationship(
            id=str(uuid.uuid4()),
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type_enum
        )
        
        self.manager.knowledge_graph.relationships[rel.id] = rel
        self.manager.save()
        return rel.id
    
    def get_entities(self) -> List[Dict[str, Any]]:
        """获取所有实体"""
        if not self._initialized:
            self.initialize()
        
        return [
            {
                "id": e.id,
                "name": e.name,
                "type": e.entity_type.value,
                "importance": e.importance,
                "attributes": e.attributes,
            }
            for e in self.manager.knowledge_graph.entities.values()
        ]
    
    def get_relationships(self) -> List[Dict[str, Any]]:
        """获取所有关系"""
        if not self._initialized:
            self.initialize()
        
        graph = self.manager.knowledge_graph
        return [
            {
                "id": r.id,
                "source_id": r.source_id,
                "target_id": r.target_id,
                "source_name": graph.entities.get(r.source_id, {}).name if graph.entities.get(r.source_id) else None,
                "target_name": graph.entities.get(r.target_id, {}).name if graph.entities.get(r.target_id) else None,
                "type": r.relation_type.value,
                "description": r.description,
            }
            for r in graph.relationships.values()
        ]
    
    def consolidate_memories(self) -> Dict[str, Any]:
        """执行记忆压缩"""
        if not self._initialized:
            self.initialize()
        
        result = self.manager.consolidator.consolidate()
        self.manager.save()
        return result
    
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
