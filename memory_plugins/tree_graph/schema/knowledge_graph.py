"""
知识图谱
存储实体及其关系，支持推理查询
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Set, Tuple
from collections import defaultdict
import json

from .models import Entity, Relationship, EntityType, RelationType, UserProfile


class KnowledgeGraph:
    """
    知识图谱
    
    存储用户提到的所有实体及其关系
    支持：
    1. 实体管理（增删改查）
    2. 关系管理
    3. 图遍历和推理
    4. 与时间记忆树的联动
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        
        # 用户画像（特殊实体）
        self.user_profile = UserProfile()
        
        # 实体存储
        self.entities: Dict[str, Entity] = {}
        
        # 关系存储
        self.relationships: Dict[str, Relationship] = {}
        
        # 索引
        self.name_index: Dict[str, str] = {}  # name/alias -> entity_id
        self.type_index: Dict[EntityType, List[str]] = defaultdict(list)
        
        # 邻接表（快速查询关系）
        self.outgoing_edges: Dict[str, List[str]] = defaultdict(list)  # entity_id -> [rel_id]
        self.incoming_edges: Dict[str, List[str]] = defaultdict(list)  # entity_id -> [rel_id]
    
    # ==================== 实体管理 ====================
    
    def add_entity(self, entity: Entity) -> str:
        """添加实体"""
        self.entities[entity.id] = entity
        
        # 更新名称索引
        self.name_index[entity.name.lower()] = entity.id
        for alias in entity.aliases:
            self.name_index[alias.lower()] = entity.id
        
        # 更新类型索引
        self.type_index[entity.entity_type].append(entity.id)
        
        return entity.id
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """获取实体"""
        return self.entities.get(entity_id)
    
    def find_entity_by_name(self, name: str) -> Optional[Entity]:
        """通过名称查找实体"""
        entity_id = self.name_index.get(name.lower())
        if entity_id:
            return self.entities.get(entity_id)
        return None
    
    def get_or_create_entity(
        self, 
        name: str, 
        entity_type: EntityType = EntityType.PERSON
    ) -> Entity:
        """获取或创建实体"""
        existing = self.find_entity_by_name(name)
        if existing:
            return existing
        
        entity = Entity(
            name=name,
            entity_type=entity_type
        )
        self.add_entity(entity)
        return entity
    
    def update_entity(
        self, 
        entity_id: str, 
        updates: Dict[str, Any]
    ) -> Optional[Entity]:
        """更新实体属性"""
        entity = self.entities.get(entity_id)
        if not entity:
            return None
        
        # 更新基本属性
        for key, value in updates.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        
        # 合并attributes
        if "attributes" in updates:
            entity.attributes.update(updates["attributes"])
        
        entity.updated_at = datetime.now()
        return entity
    
    def record_entity_mention(
        self, 
        entity_id: str, 
        memory_id: str,
        timestamp: Optional[datetime] = None
    ):
        """记录实体被提及"""
        entity = self.entities.get(entity_id)
        if not entity:
            return
        
        entity.mention_count += 1
        entity.last_mentioned = timestamp or datetime.now()
        
        # 更新最近记忆引用
        entity.recent_memory_ids.append(memory_id)
        if len(entity.recent_memory_ids) > 10:  # 只保留最近10条
            entity.recent_memory_ids = entity.recent_memory_ids[-10:]
        
        # 首次提及
        if not entity.first_memory_id:
            entity.first_memory_id = memory_id
        
        # 更新重要度
        entity.importance = min(1.0, entity.importance + 0.02)
    
    def get_entities_by_type(self, entity_type: EntityType) -> List[Entity]:
        """获取指定类型的所有实体"""
        entity_ids = self.type_index.get(entity_type, [])
        return [self.entities[eid] for eid in entity_ids]
    
    # ==================== 关系管理 ====================
    
    def add_relationship(self, relationship: Relationship) -> str:
        """添加关系"""
        self.relationships[relationship.id] = relationship
        
        # 更新邻接表
        self.outgoing_edges[relationship.source_id].append(relationship.id)
        self.incoming_edges[relationship.target_id].append(relationship.id)
        
        # 如果是双向关系，也添加反向边
        if relationship.is_bidirectional:
            self.outgoing_edges[relationship.target_id].append(relationship.id)
            self.incoming_edges[relationship.source_id].append(relationship.id)
        
        return relationship.id
    
    def get_relationship(self, rel_id: str) -> Optional[Relationship]:
        """获取关系"""
        return self.relationships.get(rel_id)
    
    def find_relationship(
        self, 
        source_id: str, 
        target_id: str,
        relation_type: Optional[RelationType] = None
    ) -> Optional[Relationship]:
        """查找两个实体之间的关系"""
        for rel_id in self.outgoing_edges.get(source_id, []):
            rel = self.relationships[rel_id]
            if rel.target_id == target_id or \
               (rel.is_bidirectional and rel.source_id == target_id):
                if relation_type is None or rel.relation_type == relation_type:
                    return rel
        return None
    
    def get_entity_relationships(
        self, 
        entity_id: str,
        direction: str = "both"  # "outgoing", "incoming", "both"
    ) -> List[Relationship]:
        """获取实体的所有关系"""
        relations = []
        
        if direction in ("outgoing", "both"):
            for rel_id in self.outgoing_edges.get(entity_id, []):
                relations.append(self.relationships[rel_id])
        
        if direction in ("incoming", "both"):
            for rel_id in self.incoming_edges.get(entity_id, []):
                rel = self.relationships[rel_id]
                if rel not in relations:
                    relations.append(rel)
        
        return relations
    
    def create_relationship_between(
        self,
        source_name: str,
        target_name: str,
        relation_type: RelationType,
        description: str = "",
        evidence_memory_id: Optional[str] = None
    ) -> Relationship:
        """在两个实体之间创建关系（自动创建不存在的实体）"""
        source = self.get_or_create_entity(source_name)
        target = self.get_or_create_entity(target_name)
        
        # 检查是否已存在
        existing = self.find_relationship(source.id, target.id, relation_type)
        if existing:
            # 更新证据
            if evidence_memory_id:
                existing.evidence_memory_ids.append(evidence_memory_id)
            existing.confidence = min(1.0, existing.confidence + 0.1)
            return existing
        
        rel = Relationship(
            source_id=source.id,
            target_id=target.id,
            relation_type=relation_type,
            description=description,
            evidence_memory_ids=[evidence_memory_id] if evidence_memory_id else []
        )
        self.add_relationship(rel)
        return rel
    
    # ==================== 图查询和推理 ====================
    
    def get_related_entities(
        self,
        entity_id: str,
        max_depth: int = 2,
        relation_types: Optional[List[RelationType]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        获取相关实体（BFS遍历）
        
        Returns:
            {entity_id: {"entity": Entity, "path": [关系路径], "depth": 深度}}
        """
        result = {}
        visited = {entity_id}
        queue = [(entity_id, [], 0)]  # (entity_id, path, depth)
        
        while queue:
            current_id, path, depth = queue.pop(0)
            
            if depth >= max_depth:
                continue
            
            for rel in self.get_entity_relationships(current_id):
                # 类型过滤
                if relation_types and rel.relation_type not in relation_types:
                    continue
                
                # 找到另一端
                other_id = rel.target_id if rel.source_id == current_id else rel.source_id
                
                if other_id in visited:
                    continue
                
                visited.add(other_id)
                new_path = path + [rel]
                
                result[other_id] = {
                    "entity": self.entities[other_id],
                    "path": new_path,
                    "depth": depth + 1
                }
                
                queue.append((other_id, new_path, depth + 1))
        
        return result
    
    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5
    ) -> Optional[List[Relationship]]:
        """查找两个实体之间的路径"""
        if source_id == target_id:
            return []
        
        visited = {source_id}
        queue = [(source_id, [])]
        
        while queue:
            current_id, path = queue.pop(0)
            
            if len(path) >= max_depth:
                continue
            
            for rel in self.get_entity_relationships(current_id):
                other_id = rel.target_id if rel.source_id == current_id else rel.source_id
                
                if other_id == target_id:
                    return path + [rel]
                
                if other_id not in visited:
                    visited.add(other_id)
                    queue.append((other_id, path + [rel]))
        
        return None
    
    def infer_relationship(
        self,
        source_id: str,
        target_id: str
    ) -> Optional[str]:
        """
        推理两个实体之间的关系
        
        例如：
        - A是B的妈妈，B是C的朋友 → A可能是C朋友的妈妈
        - A在X公司工作，B也在X公司工作 → A和B是同事
        """
        path = self.find_path(source_id, target_id)
        if not path:
            return None
        
        if len(path) == 1:
            return path[0].description
        
        # 简单的路径描述
        source = self.entities[source_id]
        target = self.entities[target_id]
        
        descriptions = []
        current = source_id
        for rel in path:
            other = rel.target_id if rel.source_id == current else rel.source_id
            other_entity = self.entities[other]
            descriptions.append(f"{rel.relation_type.value}→{other_entity.name}")
            current = other
        
        return f"{source.name} {'→'.join(descriptions)}"
    
    def get_social_circle(
        self, 
        center_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取社交圈视图
        以用户或指定实体为中心
        """
        # 如果未指定，以用户画像为中心
        if center_id is None:
            # 创建一个虚拟的用户实体
            center_entity = Entity(
                id="user",
                name=self.user_profile.name or "用户",
                entity_type=EntityType.USER
            )
        else:
            center_entity = self.entities.get(center_id)
            if not center_entity:
                return {}
        
        # 按关系类型分组
        circles = {
            "family": [],
            "friends": [],
            "colleagues": [],
            "romantic": [],
            "others": []
        }
        
        # 获取所有人物实体
        people = self.get_entities_by_type(EntityType.PERSON)
        
        for person in people:
            if person.id == center_id:
                continue
            
            # 查找与中心的关系
            rel = self.find_relationship(center_id or "user", person.id)
            
            if rel:
                if rel.relation_type == RelationType.FAMILY:
                    circles["family"].append(person)
                elif rel.relation_type == RelationType.FRIEND:
                    circles["friends"].append(person)
                elif rel.relation_type == RelationType.COLLEAGUE:
                    circles["colleagues"].append(person)
                elif rel.relation_type == RelationType.ROMANTIC:
                    circles["romantic"].append(person)
                else:
                    circles["others"].append(person)
            else:
                circles["others"].append(person)
        
        return {
            "center": center_entity.to_dict() if isinstance(center_entity, Entity) else None,
            "circles": {
                k: [e.to_dict() for e in v] 
                for k, v in circles.items()
            }
        }
    
    def get_entity_profile(self, entity_id: str) -> Dict[str, Any]:
        """
        获取实体的完整档案
        包括属性、关系、相关记忆
        """
        entity = self.entities.get(entity_id)
        if not entity:
            return {}
        
        relationships = self.get_entity_relationships(entity_id)
        
        # 分类关系
        rel_groups = defaultdict(list)
        for rel in relationships:
            other_id = rel.target_id if rel.source_id == entity_id else rel.source_id
            other = self.entities.get(other_id)
            if other:
                rel_groups[rel.relation_type.value].append({
                    "entity": other.to_dict(),
                    "description": rel.description
                })
        
        return {
            "basic_info": entity.to_dict(),
            "relationships": dict(rel_groups),
            "first_mentioned": entity.first_memory_id,
            "recent_memories": entity.recent_memory_ids,
            "importance_score": entity.importance
        }
    
    # ==================== 用户画像管理 ====================
    
    def update_user_profile(self, updates: Dict[str, Any]):
        """更新用户画像"""
        for key, value in updates.items():
            if hasattr(self.user_profile, key):
                current = getattr(self.user_profile, key)
                if isinstance(current, dict):
                    current.update(value)
                elif isinstance(current, list):
                    if isinstance(value, list):
                        current.extend(value)
                        # 去重
                        setattr(self.user_profile, key, list(set(current)))
                    else:
                        current.append(value)
                else:
                    setattr(self.user_profile, key, value)
        
        self.user_profile.updated_at = datetime.now()
    
    def get_user_profile(self) -> Dict[str, Any]:
        """获取用户画像"""
        return self.user_profile.to_dict()
    
    # ==================== 序列化 ====================
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "user_id": self.user_id,
            "user_profile": self.user_profile.to_dict(),
            "entities": {k: v.to_dict() for k, v in self.entities.items()},
            "relationships": {k: v.to_dict() for k, v in self.relationships.items()},
            "name_index": self.name_index,
            "type_index": {k.value: v for k, v in self.type_index.items()},
        }
    
    def save(self, filepath: str):
        """保存到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    def get_context_summary(self, max_entities: int = 10) -> str:
        """
        生成可注入prompt的上下文摘要
        用于让Agent了解用户的社交圈
        """
        lines = []
        
        # 用户基本信息
        profile = self.user_profile
        if profile.name:
            lines.append(f"用户名称: {profile.name}")
        if profile.demographics:
            lines.append(f"基本信息: {profile.demographics}")
        if profile.life_context:
            lines.append(f"当前状态: {profile.life_context}")
        
        # 重要人物
        people = self.get_entities_by_type(EntityType.PERSON)
        important_people = sorted(
            people, 
            key=lambda x: x.importance, 
            reverse=True
        )[:max_entities]
        
        if important_people:
            lines.append("\n重要人物:")
            for person in important_people:
                rel = self.find_relationship("user", person.id)
                rel_desc = rel.description if rel else "提及过的人"
                lines.append(f"  - {person.name}: {rel_desc}")
        
        return "\n".join(lines)
