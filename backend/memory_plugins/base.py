"""
记忆插件基础接口定义
所有记忆插件都必须实现这个接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class MemoryType(Enum):
    """记忆类型"""
    EPISODIC = "episodic"      # 情景记忆：具体事件
    SEMANTIC = "semantic"       # 语义记忆：抽象知识
    PROCEDURAL = "procedural"   # 程序记忆：习惯/偏好


@dataclass
class MemoryItem:
    """统一的记忆项数据结构"""
    id: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    importance: float = 0.5
    memory_type: MemoryType = MemoryType.EPISODIC
    tags: List[str] = field(default_factory=list)
    emotion_tags: List[str] = field(default_factory=list)
    topic_tags: List[str] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "importance": self.importance,
            "memory_type": self.memory_type.value,
            "tags": self.tags,
            "emotion_tags": self.emotion_tags,
            "topic_tags": self.topic_tags,
            "entities": self.entities,
            "metadata": self.metadata,
        }


@dataclass
class MemorySearchResult:
    """搜索结果"""
    memory: MemoryItem
    score: float = 0.0  # 相关性得分
    match_reason: str = ""  # 匹配原因
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory": self.memory.to_dict(),
            "score": self.score,
            "match_reason": self.match_reason,
        }


@dataclass
class PluginInfo:
    """插件信息"""
    id: str                     # 唯一标识符
    name: str                   # 显示名称
    description: str            # 描述
    version: str                # 版本
    author: str = ""            # 作者
    supports_vector_search: bool = False   # 是否支持向量搜索
    supports_graph: bool = False           # 是否支持知识图谱
    supports_temporal: bool = False        # 是否支持时间检索
    config_schema: Dict[str, Any] = field(default_factory=dict)  # 配置项定义
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "supports_vector_search": self.supports_vector_search,
            "supports_graph": self.supports_graph,
            "supports_temporal": self.supports_temporal,
            "config_schema": self.config_schema,
        }


class MemoryPluginBase(ABC):
    """
    记忆插件基类
    所有记忆插件必须继承此类并实现所有抽象方法
    """
    
    def __init__(self, user_id: str, storage_path: str, config: Dict[str, Any] = None):
        """
        初始化插件
        
        Args:
            user_id: 用户ID
            storage_path: 存储路径
            config: 插件配置
        """
        self.user_id = user_id
        self.storage_path = storage_path
        self.config = config or {}
        self._initialized = False
    
    @classmethod
    @abstractmethod
    def get_plugin_info(cls) -> PluginInfo:
        """获取插件信息"""
        pass
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        初始化插件（创建数据库、加载数据等）
        返回是否成功
        """
        pass
    
    @abstractmethod
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
        """
        添加记忆
        返回记忆ID
        """
        pass
    
    @abstractmethod
    def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """根据ID获取记忆"""
        pass
    
    @abstractmethod
    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        pass
    
    @abstractmethod
    def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆"""
        pass
    
    @abstractmethod
    def search(
        self,
        query: str = None,
        time_start: datetime = None,
        time_end: datetime = None,
        tags: List[str] = None,
        memory_type: MemoryType = None,
        limit: int = 10,
    ) -> List[MemorySearchResult]:
        """
        搜索记忆
        支持多种查询条件组合
        """
        pass
    
    @abstractmethod
    def get_recent_memories(self, limit: int = 20) -> List[MemoryItem]:
        """获取最近的记忆"""
        pass
    
    @abstractmethod
    def get_important_memories(self, limit: int = 20, min_importance: float = 0.5) -> List[MemoryItem]:
        """获取重要的记忆"""
        pass
    
    @abstractmethod
    def get_context_for_conversation(
        self,
        query: str = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        获取对话上下文
        返回适合注入到 LLM prompt 的记忆上下文
        """
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        pass
    
    @abstractmethod
    def get_visualization_data(self) -> Dict[str, Any]:
        """
        获取可视化数据
        返回适合前端展示的数据结构
        """
        pass
    
    @abstractmethod
    def save(self) -> bool:
        """持久化保存"""
        pass
    
    @abstractmethod
    def clear_all(self) -> bool:
        """清空所有记忆"""
        pass
    
    # ==================== 可选方法（子类可以覆盖）====================
    
    def add_entity(self, name: str, entity_type: str, attributes: Dict[str, Any] = None) -> str:
        """添加实体（如果插件支持知识图谱）"""
        raise NotImplementedError("This plugin does not support knowledge graph")
    
    def add_relationship(self, source_id: str, target_id: str, relation_type: str) -> str:
        """添加关系（如果插件支持知识图谱）"""
        raise NotImplementedError("This plugin does not support knowledge graph")
    
    def get_entities(self) -> List[Dict[str, Any]]:
        """获取所有实体"""
        return []
    
    def get_relationships(self) -> List[Dict[str, Any]]:
        """获取所有关系"""
        return []
    
    def consolidate_memories(self) -> Dict[str, Any]:
        """压缩/整合记忆（如果插件支持）"""
        return {"status": "not_supported"}
    
    def export_data(self) -> Dict[str, Any]:
        """导出所有数据"""
        return {
            "user_id": self.user_id,
            "plugin": self.get_plugin_info().id,
            "memories": [m.to_dict() for m in self.get_recent_memories(limit=1000)],
            "entities": self.get_entities(),
            "relationships": self.get_relationships(),
        }
    
    def import_data(self, data: Dict[str, Any]) -> bool:
        """导入数据"""
        raise NotImplementedError("Import not implemented for this plugin")
