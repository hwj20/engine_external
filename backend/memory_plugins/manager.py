"""
记忆插件管理器
管理插件的注册、切换和配置
"""

import os
import json
from typing import Dict, Any, Optional, Type, List

from .base import MemoryPluginBase, PluginInfo
from .temporal_tree_plugin import TemporalTreePlugin
from .vector_plugin import VectorMemoryPlugin
from .simple_sqlite_plugin import SimpleSQLitePlugin


class MemoryPluginManager:
    """
    记忆插件管理器
    
    功能：
    - 注册和管理多个记忆插件
    - 切换当前使用的插件
    - 保存和加载配置
    - 提供统一的访问接口
    """
    
    # 内置插件列表
    BUILTIN_PLUGINS: Dict[str, Type[MemoryPluginBase]] = {
        "temporal_tree": TemporalTreePlugin,
        "vector_memory": VectorMemoryPlugin,
        "simple_sqlite": SimpleSQLitePlugin,
    }
    
    _instance: Optional['MemoryPluginManager'] = None
    
    def __init__(
        self, 
        user_id: str = "default_user",
        storage_path: str = None,
        config_path: str = None
    ):
        self.user_id = user_id
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "memory_plugins"
        )
        self.config_path = config_path or os.path.join(self.storage_path, "plugin_config.json")
        
        # 确保存储路径存在
        os.makedirs(self.storage_path, exist_ok=True)
        
        # 注册的插件类
        self._registered_plugins: Dict[str, Type[MemoryPluginBase]] = dict(self.BUILTIN_PLUGINS)
        
        # 已实例化的插件
        self._plugin_instances: Dict[str, MemoryPluginBase] = {}
        
        # 当前激活的插件
        self._active_plugin_id: str = "simple_sqlite"  # 默认使用简单插件
        
        # 插件配置
        self._plugin_configs: Dict[str, Dict[str, Any]] = {}
        
        # 加载配置
        self._load_config()
        
        print(f"[MemoryPluginManager] Initialized with {len(self._registered_plugins)} plugins")
    
    @classmethod
    def get_instance(
        cls, 
        user_id: str = "default_user",
        storage_path: str = None
    ) -> 'MemoryPluginManager':
        """单例模式获取实例"""
        if cls._instance is None:
            cls._instance = cls(user_id=user_id, storage_path=storage_path)
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """重置单例（用于测试）"""
        cls._instance = None
    
    def _load_config(self):
        """加载配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self._active_plugin_id = config.get("active_plugin", "simple_sqlite")
                    self._plugin_configs = config.get("plugin_configs", {})
                    print(f"[MemoryPluginManager] Loaded config: active={self._active_plugin_id}")
            except Exception as e:
                print(f"[MemoryPluginManager] Failed to load config: {e}")
    
    def _save_config(self):
        """保存配置"""
        try:
            config = {
                "active_plugin": self._active_plugin_id,
                "plugin_configs": self._plugin_configs
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"[MemoryPluginManager] Config saved")
        except Exception as e:
            print(f"[MemoryPluginManager] Failed to save config: {e}")
    
    def register_plugin(self, plugin_class: Type[MemoryPluginBase]) -> bool:
        """注册新插件"""
        try:
            info = plugin_class.get_plugin_info()
            self._registered_plugins[info.id] = plugin_class
            print(f"[MemoryPluginManager] Registered plugin: {info.id} ({info.name})")
            return True
        except Exception as e:
            print(f"[MemoryPluginManager] Failed to register plugin: {e}")
            return False
    
    def unregister_plugin(self, plugin_id: str) -> bool:
        """注销插件"""
        if plugin_id in self._registered_plugins:
            # 如果是当前激活的插件，切换到默认插件
            if self._active_plugin_id == plugin_id:
                self._active_plugin_id = "simple_sqlite"
            
            # 销毁实例
            if plugin_id in self._plugin_instances:
                del self._plugin_instances[plugin_id]
            
            del self._registered_plugins[plugin_id]
            print(f"[MemoryPluginManager] Unregistered plugin: {plugin_id}")
            return True
        return False
    
    def get_available_plugins(self) -> List[PluginInfo]:
        """获取所有可用插件的信息"""
        plugins = []
        for plugin_id, plugin_class in self._registered_plugins.items():
            info = plugin_class.get_plugin_info()
            plugins.append(info)
        return plugins
    
    def get_plugin_info(self, plugin_id: str) -> Optional[PluginInfo]:
        """获取指定插件的信息"""
        if plugin_id in self._registered_plugins:
            return self._registered_plugins[plugin_id].get_plugin_info()
        return None
    
    def get_active_plugin_id(self) -> str:
        """获取当前激活的插件ID"""
        return self._active_plugin_id
    
    def get_active_plugin(self) -> MemoryPluginBase:
        """获取当前激活的插件实例"""
        return self._get_or_create_plugin(self._active_plugin_id)
    
    def _get_or_create_plugin(self, plugin_id: str) -> MemoryPluginBase:
        """获取或创建插件实例"""
        if plugin_id not in self._plugin_instances:
            if plugin_id not in self._registered_plugins:
                raise ValueError(f"Unknown plugin: {plugin_id}")
            
            plugin_class = self._registered_plugins[plugin_id]
            config = self._plugin_configs.get(plugin_id, {})
            
            # 创建插件专用的存储路径
            plugin_storage = os.path.join(self.storage_path, plugin_id)
            
            plugin = plugin_class(
                user_id=self.user_id,
                storage_path=plugin_storage,
                config=config
            )
            plugin.initialize()
            
            self._plugin_instances[plugin_id] = plugin
            print(f"[MemoryPluginManager] Created plugin instance: {plugin_id}")
        
        return self._plugin_instances[plugin_id]
    
    def switch_plugin(self, plugin_id: str) -> bool:
        """切换到指定插件"""
        if plugin_id not in self._registered_plugins:
            print(f"[MemoryPluginManager] Unknown plugin: {plugin_id}")
            return False
        
        # 保存当前插件的数据
        if self._active_plugin_id in self._plugin_instances:
            self._plugin_instances[self._active_plugin_id].save()
        
        self._active_plugin_id = plugin_id
        self._save_config()
        
        # 确保新插件已初始化
        self._get_or_create_plugin(plugin_id)
        
        print(f"[MemoryPluginManager] Switched to plugin: {plugin_id}")
        return True
    
    def set_plugin_config(self, plugin_id: str, config: Dict[str, Any]) -> bool:
        """设置插件配置"""
        if plugin_id not in self._registered_plugins:
            return False
        
        self._plugin_configs[plugin_id] = config
        self._save_config()
        
        # 如果插件已实例化，重新初始化
        if plugin_id in self._plugin_instances:
            del self._plugin_instances[plugin_id]
            self._get_or_create_plugin(plugin_id)
        
        return True
    
    def get_plugin_config(self, plugin_id: str) -> Dict[str, Any]:
        """获取插件配置"""
        return self._plugin_configs.get(plugin_id, {})
    
    # ==================== 代理方法（转发到当前激活的插件）====================
    
    def add_memory(self, **kwargs) -> str:
        """添加记忆"""
        return self.get_active_plugin().add_memory(**kwargs)
    
    def get_memory(self, memory_id: str):
        """获取记忆"""
        return self.get_active_plugin().get_memory(memory_id)
    
    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        return self.get_active_plugin().delete_memory(memory_id)
    
    def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆"""
        return self.get_active_plugin().update_memory(memory_id, updates)
    
    def search(self, **kwargs):
        """搜索记忆"""
        return self.get_active_plugin().search(**kwargs)
    
    def get_recent_memories(self, limit: int = 20):
        """获取最近记忆"""
        return self.get_active_plugin().get_recent_memories(limit)
    
    def get_important_memories(self, limit: int = 20, min_importance: float = 0.5):
        """获取重要记忆"""
        return self.get_active_plugin().get_important_memories(limit, min_importance)
    
    def get_context_for_conversation(self, query: str = None, limit: int = 10):
        """获取对话上下文"""
        return self.get_active_plugin().get_context_for_conversation(query, limit)
    
    def get_stats(self):
        """获取统计信息"""
        stats = self.get_active_plugin().get_stats()
        stats["active_plugin"] = self._active_plugin_id
        return stats
    
    def get_visualization_data(self):
        """获取可视化数据"""
        data = self.get_active_plugin().get_visualization_data()
        data["active_plugin"] = self._active_plugin_id
        data["available_plugins"] = [p.to_dict() for p in self.get_available_plugins()]
        return data
    
    def save(self) -> bool:
        """保存当前插件数据"""
        return self.get_active_plugin().save()
    
    def clear_all(self) -> bool:
        """清空当前插件的所有记忆"""
        return self.get_active_plugin().clear_all()
    
    def add_demo_data(self):
        """添加演示数据"""
        plugin = self.get_active_plugin()
        if hasattr(plugin, 'add_demo_data'):
            return plugin.add_demo_data()
        return {"added": 0}
    
    # ==================== 知识图谱方法（如果插件支持）====================
    
    def get_entities(self):
        """获取实体"""
        plugin = self.get_active_plugin()
        if hasattr(plugin, 'get_entities'):
            return plugin.get_entities()
        return []
    
    def get_relationships(self):
        """获取关系"""
        plugin = self.get_active_plugin()
        if hasattr(plugin, 'get_relationships'):
            return plugin.get_relationships()
        return []
    
    def add_entity(self, name: str, entity_type: str, attributes: Dict[str, Any] = None) -> str:
        """添加实体"""
        plugin = self.get_active_plugin()
        if hasattr(plugin, 'add_entity'):
            return plugin.add_entity(name, entity_type, attributes)
        raise NotImplementedError("Current plugin does not support knowledge graph")
    
    def add_relationship(self, source_id: str, target_id: str, relation_type: str) -> str:
        """添加关系"""
        plugin = self.get_active_plugin()
        if hasattr(plugin, 'add_relationship'):
            return plugin.add_relationship(source_id, target_id, relation_type)
        raise NotImplementedError("Current plugin does not support knowledge graph")
