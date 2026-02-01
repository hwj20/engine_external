"""
Memory Plugin API
基于插件系统的记忆 API
"""

import os
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from memory_plugins import MemoryPluginManager


# ==================== Pydantic 请求模型 ====================

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


class SwitchPluginRequest(BaseModel):
    plugin_id: str


class PluginConfigRequest(BaseModel):
    plugin_id: str
    config: Dict[str, Any]


# ==================== Memory Plugin Service ====================

class MemoryPluginService:
    """
    记忆插件服务
    统一管理记忆插件的 API 入口
    """
    
    _instance: Optional['MemoryPluginService'] = None
    
    def __init__(self, user_id: str = "default_user", storage_path: str = None):
        if storage_path is None:
            storage_path = os.path.join(os.path.dirname(__file__), "data", "memory_plugins")
        
        self.manager = MemoryPluginManager.get_instance(
            user_id=user_id,
            storage_path=storage_path
        )
        print(f"[MemoryPluginService] Initialized with user: {user_id}")
    
    @classmethod
    def get_instance(cls, user_id: str = "default_user") -> 'MemoryPluginService':
        """单例模式获取实例"""
        if cls._instance is None:
            cls._instance = cls(user_id=user_id)
        return cls._instance
    
    # ==================== 插件管理 ====================
    
    def get_available_plugins(self) -> List[Dict[str, Any]]:
        """获取所有可用插件"""
        plugins = self.manager.get_available_plugins()
        return [p.to_dict() for p in plugins]
    
    def get_active_plugin(self) -> Dict[str, Any]:
        """获取当前激活的插件信息"""
        plugin_id = self.manager.get_active_plugin_id()
        info = self.manager.get_plugin_info(plugin_id)
        return {
            "id": plugin_id,
            "info": info.to_dict() if info else None,
            "config": self.manager.get_plugin_config(plugin_id)
        }
    
    def switch_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """切换插件"""
        success = self.manager.switch_plugin(plugin_id)
        return {
            "success": success,
            "active_plugin": self.manager.get_active_plugin_id()
        }
    
    def set_plugin_config(self, plugin_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """设置插件配置"""
        success = self.manager.set_plugin_config(plugin_id, config)
        return {
            "success": success,
            "plugin_id": plugin_id,
            "config": self.manager.get_plugin_config(plugin_id)
        }
    
    # ==================== 记忆操作 ====================
    
    def add_memory(
        self,
        content: str,
        importance: float = 0.5,
        emotion_tags: List[str] = None,
        topic_tags: List[str] = None,
        entities: List[Dict[str, Any]] = None
    ) -> str:
        """添加记忆"""
        return self.manager.add_memory(
            content=content,
            importance=importance,
            emotion_tags=emotion_tags or [],
            topic_tags=topic_tags or [],
            entities=entities
        )
    
    def search_memories(
        self,
        query: str = None,
        time_hint: str = None,
        topic: str = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """搜索记忆"""
        tags = [topic] if topic else None
        results = self.manager.search(query=query, tags=tags, limit=limit)
        return [r.to_dict() for r in results]
    
    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        return self.manager.delete_memory(memory_id)
    
    def get_context_for_conversation(self, query: str = None, limit: int = 10) -> Dict[str, Any]:
        """获取对话上下文"""
        return self.manager.get_context_for_conversation(query, limit)
    
    # ==================== 数据获取 ====================
    
    def get_visualization_data(self) -> Dict[str, Any]:
        """获取可视化数据"""
        return self.manager.get_visualization_data()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.manager.get_stats()
    
    def get_recent_memories(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近记忆"""
        memories = self.manager.get_recent_memories(limit)
        return [m.to_dict() for m in memories]
    
    def get_entities(self) -> List[Dict[str, Any]]:
        """获取实体（如果插件支持）"""
        return self.manager.get_entities()
    
    def get_relationships(self) -> List[Dict[str, Any]]:
        """获取关系（如果插件支持）"""
        return self.manager.get_relationships()
    
    # ==================== 其他操作 ====================
    
    def add_demo_data(self) -> Dict[str, Any]:
        """添加演示数据"""
        return self.manager.add_demo_data()
    
    def clear_all(self) -> bool:
        """清空所有记忆"""
        return self.manager.clear_all()
    
    def save(self) -> bool:
        """保存"""
        return self.manager.save()
