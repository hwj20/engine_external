"""
记忆管理器
统一管理时间树和知识图谱
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import json
import os

from schema.models import MemoryNode, Entity, Relationship, MemoryType, EntityType, RelationType
from schema.temporal_tree import TemporalMemoryTree
from schema.knowledge_graph import KnowledgeGraph
from core.forgetting_curve import ForgettingCurve, ContextMemorySelector, ForgettingConfig
from core.consolidation import MemoryConsolidator, MemoryMigrator, ConsolidationConfig


class MemoryManager:
    """
    记忆管理器 - 统一入口
    
    功能：
    1. 记忆的增删改查
    2. 自动维护时间树和图谱的一致性
    3. 提供context注入接口
    4. 处理用户查询（"昨天吃了什么"）
    """
    
    def __init__(
        self,
        user_id: str,
        storage_path: Optional[str] = None,
        forgetting_config: Optional[ForgettingConfig] = None,
        consolidation_config: Optional[ConsolidationConfig] = None
    ):
        self.user_id = user_id
        self.storage_path = storage_path or f"./memory_data/{user_id}"
        
        # 核心组件
        self.memory_tree = TemporalMemoryTree()
        self.knowledge_graph = KnowledgeGraph(user_id)
        self.forgetting_curve = ForgettingCurve(forgetting_config)
        self.context_selector = ContextMemorySelector(self.forgetting_curve)
        self.consolidator = MemoryConsolidator(
            self.memory_tree,
            self.knowledge_graph,
            self.forgetting_curve,
            consolidation_config
        )
        
        # 尝试加载已有数据
        self._load_if_exists()
    
    def _load_if_exists(self):
        """如果存在已保存的数据，加载它"""
        tree_path = os.path.join(self.storage_path, "memory_tree.json")
        graph_path = os.path.join(self.storage_path, "knowledge_graph.json")
        
        if os.path.exists(tree_path):
            self.memory_tree.load(tree_path)
        if os.path.exists(graph_path):
            self.knowledge_graph.load(graph_path)
    
    def save(self):
        """保存所有数据"""
        os.makedirs(self.storage_path, exist_ok=True)
        self.memory_tree.save(os.path.join(self.storage_path, "memory_tree.json"))
        self.knowledge_graph.save(os.path.join(self.storage_path, "knowledge_graph.json"))
    
    # ==================== 记忆写入 ====================
    
    def add_memory(
        self,
        content: str,
        timestamp: Optional[datetime] = None,
        importance: float = 0.5,
        emotion_tags: List[str] = None,
        topic_tags: List[str] = None,
        entities: List[Dict[str, Any]] = None,
        raw_conversation: str = None
    ) -> str:
        """
        添加一条记忆
        
        Args:
            content: 记忆内容摘要
            timestamp: 时间戳（默认当前时间）
            importance: 重要度 [0, 1]
            emotion_tags: 情感标签
            topic_tags: 话题标签
            entities: 涉及的实体 [{"name": "小明", "type": "person", "relation": "friend"}]
            raw_conversation: 原始对话内容
            
        Returns:
            记忆ID
        """
        memory = MemoryNode(
            timestamp=timestamp or datetime.now(),
            content=content,
            base_importance=importance,
            emotion_tags=emotion_tags or [],
            topic_tags=topic_tags or [],
            raw_conversation=raw_conversation
        )
        
        # 添加到时间树
        memory_id = self.memory_tree.add_memory(memory)
        
        # 处理实体
        if entities:
            for entity_info in entities:
                entity = self._process_entity(entity_info, memory_id)
                memory.linked_entities.append(entity.id)
        
        return memory_id
    
    def _process_entity(self, entity_info: Dict[str, Any], memory_id: str) -> Entity:
        """处理实体信息"""
        name = entity_info.get("name", "")
        entity_type = EntityType(entity_info.get("type", "person"))
        
        # 获取或创建实体
        entity = self.knowledge_graph.get_or_create_entity(name, entity_type)
        
        # 记录提及
        self.knowledge_graph.record_entity_mention(
            entity.id, 
            memory_id,
            datetime.now()
        )
        
        # 如果有关系信息，创建与用户的关系
        if "relation" in entity_info:
            relation_type = self._map_relation_type(entity_info["relation"])
            self.knowledge_graph.create_relationship_between(
                "用户",  # 用户作为源
                name,
                relation_type,
                entity_info.get("relation_desc", ""),
                memory_id
            )
        
        # 更新实体属性
        if "attributes" in entity_info:
            self.knowledge_graph.update_entity(entity.id, {"attributes": entity_info["attributes"]})
        
        return entity
    
    def _map_relation_type(self, relation_str: str) -> RelationType:
        """将字符串映射到关系类型"""
        mapping = {
            "家人": RelationType.FAMILY,
            "family": RelationType.FAMILY,
            "朋友": RelationType.FRIEND,
            "friend": RelationType.FRIEND,
            "同事": RelationType.COLLEAGUE,
            "colleague": RelationType.COLLEAGUE,
            "恋人": RelationType.ROMANTIC,
            "romantic": RelationType.ROMANTIC,
        }
        return mapping.get(relation_str.lower(), RelationType.RELATED_TO)
    
    def reinforce_memory(self, memory_id: str) -> float:
        """强化记忆（被提及时调用）"""
        memory = self.memory_tree.get_memory(memory_id)
        if memory:
            return self.forgetting_curve.reinforce_memory(memory)
        return 0.0
    
    # ==================== 记忆查询 ====================
    
    def search_memories(
        self,
        query: str = None,
        time_hint: str = None,
        topic: str = None,
        entity_name: str = None,
        limit: int = 10
    ) -> List[MemoryNode]:
        """
        搜索记忆
        
        支持多种查询方式的组合：
        - 关键词搜索
        - 时间提示（"昨天"，"上周"）
        - 话题过滤
        - 实体关联
        """
        results = []
        
        # 时间+话题搜索
        if time_hint or topic:
            results = self.memory_tree.search_by_time_and_topic(
                time_hint=time_hint,
                topic=topic
            )
        
        # 关键词搜索
        if query:
            keyword_results = self.memory_tree.search_by_content(query, limit * 2)
            if results:
                # 取交集
                result_ids = {m.id for m in results}
                results = [m for m in keyword_results if m.id in result_ids]
            else:
                results = keyword_results
        
        # 实体关联
        if entity_name:
            entity = self.knowledge_graph.find_entity_by_name(entity_name)
            if entity:
                entity_memory_ids = set(entity.recent_memory_ids)
                if entity.first_memory_id:
                    entity_memory_ids.add(entity.first_memory_id)
                
                if results:
                    results = [m for m in results if m.id in entity_memory_ids]
                else:
                    results = [
                        self.memory_tree.get_memory(mid) 
                        for mid in entity_memory_ids
                        if self.memory_tree.get_memory(mid)
                    ]
        
        # 如果没有任何条件，返回最近的记忆
        if not results and not any([query, time_hint, topic, entity_name]):
            all_events = [
                n for n in self.memory_tree.nodes.values() 
                if n.time_grain == "event"
            ]
            results = sorted(all_events, key=lambda x: x.timestamp, reverse=True)
        
        # 强化被搜索到的记忆
        for memory in results[:limit]:
            self.reinforce_memory(memory.id)
        
        return results[:limit]
    
    def answer_memory_query(self, query: str) -> Dict[str, Any]:
        """
        回答关于记忆的自然语言查询
        
        例如：
        - "昨天晚上我们吃的什么？"
        - "小明是谁？"
        - "上周我们聊了什么？"
        
        Returns:
            {
                "found": bool,
                "memories": List[MemoryNode],
                "answer_hint": str,  # 给Agent的回答提示
                "related_entities": List[Entity]
            }
        """
        result = {
            "found": False,
            "memories": [],
            "answer_hint": "",
            "related_entities": []
        }
        
        # 解析查询
        parsed = self._parse_query(query)
        
        # 搜索记忆
        memories = self.search_memories(
            query=parsed.get("keyword"),
            time_hint=parsed.get("time_hint"),
            topic=parsed.get("topic"),
            entity_name=parsed.get("entity")
        )
        
        if memories:
            result["found"] = True
            result["memories"] = memories
            result["answer_hint"] = self._generate_answer_hint(memories, parsed)
            
            # 获取相关实体
            entity_ids = set()
            for m in memories:
                entity_ids.update(m.linked_entities)
            result["related_entities"] = [
                self.knowledge_graph.get_entity(eid) 
                for eid in entity_ids
                if self.knowledge_graph.get_entity(eid)
            ]
        else:
            result["answer_hint"] = "抱歉，我没有找到相关的记忆。"
        
        return result
    
    def _parse_query(self, query: str) -> Dict[str, Any]:
        """解析自然语言查询"""
        parsed = {}
        
        # 时间提示词
        time_hints = ["昨天", "前天", "上周", "上个月", "去年", "今天", "刚才"]
        for hint in time_hints:
            if hint in query:
                parsed["time_hint"] = hint
                break
        
        # 简单的关键词提取（实际应该用NLP）
        # 移除时间词后的内容作为关键词
        keyword = query
        for hint in time_hints:
            keyword = keyword.replace(hint, "")
        keyword = keyword.replace("我们", "").replace("什么", "").replace("？", "").replace("?", "")
        keyword = keyword.strip()
        if keyword:
            parsed["keyword"] = keyword
        
        return parsed
    
    def _generate_answer_hint(self, memories: List[MemoryNode], parsed: Dict) -> str:
        """生成回答提示"""
        if not memories:
            return ""
        
        hints = []
        for m in memories[:3]:
            time_str = m.timestamp.strftime("%m月%d日")
            hints.append(f"[{time_str}] {m.content}")
        
        return "\n".join(hints)
    
    # ==================== Context 注入 ====================
    
    def get_context_memories(
        self,
        current_topics: List[str] = None,
        current_entities: List[str] = None,
        max_memories: int = 10
    ) -> str:
        """
        获取应该注入到对话context的记忆
        
        Returns:
            格式化的记忆字符串，可直接注入prompt
        """
        all_events = [
            n for n in self.memory_tree.nodes.values() 
            if n.time_grain == "event"
        ]
        
        selected = self.context_selector.select_for_context(
            all_events,
            current_topics=current_topics,
            current_entities=current_entities
        )
        
        return self.context_selector.generate_context_summary(selected)
    
    def get_full_context(
        self,
        current_topics: List[str] = None,
        current_entities: List[str] = None
    ) -> str:
        """
        获取完整的context（记忆 + 用户画像 + 社交圈）
        """
        sections = []
        
        # 用户画像
        profile_summary = self.knowledge_graph.get_context_summary()
        if profile_summary:
            sections.append(profile_summary)
        
        # 相关记忆
        memory_context = self.get_context_memories(
            current_topics=current_topics,
            current_entities=current_entities
        )
        if memory_context:
            sections.append(memory_context)
        
        return "\n\n".join(sections)
    
    # ==================== 实体和关系 ====================
    
    def get_entity_info(self, name: str) -> Optional[Dict[str, Any]]:
        """获取实体信息"""
        entity = self.knowledge_graph.find_entity_by_name(name)
        if entity:
            return self.knowledge_graph.get_entity_profile(entity.id)
        return None
    
    def update_user_profile(self, updates: Dict[str, Any]):
        """更新用户画像"""
        self.knowledge_graph.update_user_profile(updates)
    
    def get_social_circle(self) -> Dict[str, Any]:
        """获取用户的社交圈"""
        return self.knowledge_graph.get_social_circle()
    
    # ==================== 维护操作 ====================
    
    async def run_consolidation(self) -> Dict[str, Any]:
        """手动触发记忆压缩"""
        return await self.consolidator.consolidate()
    
    def export_for_migration(self, filepath: str):
        """导出用于迁移"""
        MemoryMigrator.export_to_file(
            self.memory_tree,
            self.knowledge_graph,
            filepath
        )
    
    def get_migration_summary(self) -> str:
        """获取迁移摘要"""
        return MemoryMigrator.generate_migration_summary(
            self.memory_tree,
            self.knowledge_graph
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        all_events = [n for n in self.memory_tree.nodes.values() if n.time_grain == "event"]
        
        return {
            "total_memories": len(all_events),
            "total_entities": len(self.knowledge_graph.entities),
            "total_relationships": len(self.knowledge_graph.relationships),
            "years_covered": list(self.memory_tree.year_index.keys()),
            "avg_importance": sum(m.base_importance for m in all_events) / len(all_events) if all_events else 0,
            "consolidated_count": sum(1 for m in all_events if m.is_consolidated)
        }
