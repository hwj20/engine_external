"""
核心数据模型定义
定义记忆系统中的基本数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid


class MemoryType(Enum):
    """记忆类型"""
    EPISODIC = "episodic"      # 情景记忆：具体事件
    SEMANTIC = "semantic"       # 语义记忆：抽象知识
    PROCEDURAL = "procedural"  # 程序记忆：习惯/偏好


class EntityType(Enum):
    """实体类型"""
    USER = "user"              # 用户本人
    PERSON = "person"          # 用户提到的人
    PLACE = "place"            # 地点
    ORGANIZATION = "organization"  # 组织/公司
    EVENT = "event"            # 事件
    CONCEPT = "concept"        # 抽象概念
    OBJECT = "object"          # 物品


class RelationType(Enum):
    """关系类型"""
    # 人际关系
    FAMILY = "family"          # 家人
    FRIEND = "friend"          # 朋友
    COLLEAGUE = "colleague"    # 同事
    ROMANTIC = "romantic"      # 恋人/配偶
    
    # 组织关系
    WORKS_AT = "works_at"      # 工作于
    STUDIES_AT = "studies_at"  # 就读于
    BELONGS_TO = "belongs_to"  # 属于
    
    # 事件关系
    PARTICIPATED_IN = "participated_in"  # 参与
    CAUSED = "caused"          # 导致
    RELATED_TO = "related_to"  # 相关
    
    # 情感关系
    LIKES = "likes"            # 喜欢
    DISLIKES = "dislikes"      # 不喜欢
    FEARS = "fears"            # 害怕
    WANTS = "wants"            # 想要


@dataclass
class MemoryNode:
    """
    记忆节点 - 时间树的基本单元
    
    支持树形嵌套：
    - 年节点包含月节点
    - 月节点包含周节点
    - 周节点包含日节点
    - 日节点包含事件节点
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # 时间信息
    timestamp: datetime = field(default_factory=datetime.now)
    time_grain: str = "event"  # year/month/week/day/event
    
    # 内容
    content: str = ""                    # 记忆内容摘要
    detail: Optional[str] = None         # 详细内容（可选展开）
    raw_conversation: Optional[str] = None  # 原始对话片段
    
    # 记忆属性
    memory_type: MemoryType = MemoryType.EPISODIC
    emotion_tags: List[str] = field(default_factory=list)  # 情感标签
    topic_tags: List[str] = field(default_factory=list)    # 话题标签
    
    # 重要度系统（艾宾浩斯曲线核心）
    base_importance: float = 0.5         # 基础重要度 [0, 1]
    current_strength: float = 1.0        # 当前记忆强度 [0, 1]
    mention_count: int = 0               # 被提及次数
    last_mentioned: Optional[datetime] = None  # 上次被提及时间
    mention_history: List[datetime] = field(default_factory=list)  # 提及历史
    
    # 树形结构
    parent_id: Optional[str] = None      # 父节点ID
    children_ids: List[str] = field(default_factory=list)  # 子节点ID列表
    
    # 图谱链接
    linked_entities: List[str] = field(default_factory=list)  # 关联的实体ID
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_consolidated: bool = False        # 是否已被压缩
    
    def calculate_effective_importance(self) -> float:
        """
        计算有效重要度
        综合考虑：基础重要度 × 当前强度 + 提及频率加成
        """
        mention_bonus = min(0.3, self.mention_count * 0.05)  # 提及加成，最高0.3
        return min(1.0, self.base_importance * self.current_strength + mention_bonus)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "time_grain": self.time_grain,
            "content": self.content,
            "detail": self.detail,
            "memory_type": self.memory_type.value,
            "emotion_tags": self.emotion_tags,
            "topic_tags": self.topic_tags,
            "base_importance": self.base_importance,
            "current_strength": self.current_strength,
            "mention_count": self.mention_count,
            "last_mentioned": self.last_mentioned.isoformat() if self.last_mentioned else None,
            "parent_id": self.parent_id,
            "children_ids": self.children_ids,
            "linked_entities": self.linked_entities,
            "effective_importance": self.calculate_effective_importance()
        }


@dataclass
class Entity:
    """
    实体 - 图谱的节点
    
    表示用户提到的任何有身份的事物：
    人物、地点、组织、概念等
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # 基本信息
    name: str = ""                       # 名称
    aliases: List[str] = field(default_factory=list)  # 别名/昵称
    entity_type: EntityType = EntityType.PERSON
    
    # 描述性属性（动态积累）
    attributes: Dict[str, Any] = field(default_factory=dict)
    # 示例：
    # {
    #     "age": 28,
    #     "occupation": "程序员",
    #     "personality": ["内向", "善良"],
    #     "likes": ["咖啡", "猫"],
    #     "important_dates": {"birthday": "03-15"}
    # }
    
    # 用户对该实体的情感倾向
    sentiment: float = 0.0               # [-1, 1] 负面到正面
    sentiment_notes: List[str] = field(default_factory=list)  # 情感依据
    
    # 重要度（类似记忆节点）
    importance: float = 0.5
    mention_count: int = 0
    last_mentioned: Optional[datetime] = None
    
    # 首次和最近记忆链接
    first_memory_id: Optional[str] = None   # 首次提到的记忆
    recent_memory_ids: List[str] = field(default_factory=list)  # 最近相关记忆
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "aliases": self.aliases,
            "entity_type": self.entity_type.value,
            "attributes": self.attributes,
            "sentiment": self.sentiment,
            "importance": self.importance,
            "mention_count": self.mention_count
        }


@dataclass
class Relationship:
    """
    关系 - 图谱的边
    
    表示两个实体之间的关系
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # 关系两端
    source_id: str = ""                  # 源实体ID
    target_id: str = ""                  # 目标实体ID
    relation_type: RelationType = RelationType.RELATED_TO
    
    # 关系描述
    description: str = ""                # 关系描述
    # 示例："小明的妈妈"，"大学室友"，"前任老板"
    
    # 关系属性
    attributes: Dict[str, Any] = field(default_factory=dict)
    # 示例：
    # {
    #     "since": "2020-01",
    #     "status": "active",
    #     "closeness": 0.8
    # }
    
    # 情感色彩
    sentiment: float = 0.0               # 这段关系的情感色彩
    
    # 双向性
    is_bidirectional: bool = True        # 是否双向关系
    
    # 证据链接
    evidence_memory_ids: List[str] = field(default_factory=list)  # 支持该关系的记忆
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0              # 置信度
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type.value,
            "description": self.description,
            "attributes": self.attributes,
            "sentiment": self.sentiment,
            "is_bidirectional": self.is_bidirectional,
            "confidence": self.confidence
        }


@dataclass
class UserProfile:
    """
    用户画像 - 特殊的实体，有更丰富的结构
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # 基本信息
    name: Optional[str] = None
    nickname: Optional[str] = None       # Agent对用户的称呼
    
    # 人口统计学信息（逐步积累）
    demographics: Dict[str, Any] = field(default_factory=dict)
    # {
    #     "age_range": "25-30",
    #     "gender": "male",
    #     "location": "北京",
    #     "occupation": "软件工程师",
    #     "education": "本科"
    # }
    
    # 性格特征（从对话中推断）
    personality: Dict[str, float] = field(default_factory=dict)
    # Big Five 或自定义维度
    # {
    #     "openness": 0.7,
    #     "conscientiousness": 0.6,
    #     "extraversion": 0.4,
    #     "agreeableness": 0.8,
    #     "neuroticism": 0.3
    # }
    
    # 兴趣和偏好
    interests: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    # {
    #     "communication_style": "直接简洁",
    #     "humor_preference": "冷幽默",
    #     "response_length": "中等",
    #     "topics_to_avoid": ["政治"]
    # }
    
    # 生活状态
    life_context: Dict[str, Any] = field(default_factory=dict)
    # {
    #     "current_focus": "找工作",
    #     "recent_mood": "焦虑",
    #     "life_stage": "职业转型期"
    # }
    
    # 重要日期
    important_dates: Dict[str, str] = field(default_factory=dict)
    # {
    #     "birthday": "1995-03-15",
    #     "anniversary": "2022-06-20"
    # }
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "nickname": self.nickname,
            "demographics": self.demographics,
            "personality": self.personality,
            "interests": self.interests,
            "preferences": self.preferences,
            "life_context": self.life_context,
            "important_dates": self.important_dates
        }


@dataclass 
class ConversationContext:
    """
    对话上下文 - 工作记忆
    
    存储当前对话的临时状态
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = field(default_factory=datetime.now)
    
    # 当前话题
    current_topics: List[str] = field(default_factory=list)
    
    # 本次对话提取的记忆（待持久化）
    pending_memories: List[MemoryNode] = field(default_factory=list)
    
    # 本次对话涉及的实体
    active_entities: List[str] = field(default_factory=list)
    
    # 召回的历史记忆（注入context的）
    recalled_memories: List[MemoryNode] = field(default_factory=list)
    
    # 对话情绪轨迹
    emotion_trajectory: List[Dict[str, Any]] = field(default_factory=list)
    # [{"timestamp": ..., "emotion": "happy", "intensity": 0.7}]
