"""
Memory Plugin API
基于插件系统的记忆 API
"""

import os
import re
import sys
import json
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from memory_plugins import MemoryPluginManager


# Determine the data directory based on whether we're running packaged or in development
def get_data_dir():
    if getattr(sys, 'frozen', False):
        # Running as packaged executable
        return os.path.join(os.path.expanduser("~"), "AppData", "Local", "AURORA-Local-Agent")
    else:
        # Running in development
        return os.path.join(os.path.dirname(__file__), "data")


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


class EvaluateMemoriesRequest(BaseModel):
    """LLM评估记忆重要性的请求"""
    memory_ids: List[str] = []  # 空列表表示评估所有记忆


class UpdateMemoryImportanceRequest(BaseModel):
    """更新记忆重要性的请求"""
    memory_id: str
    importance: float


# ==================== Memory Plugin Service ====================

class MemoryPluginService:
    """
    记忆插件服务
    统一管理记忆插件的 API 入口
    """
    
    _instance: Optional['MemoryPluginService'] = None
    
    def __init__(self, user_id: str = "default_user", storage_path: str = None):
        if storage_path is None:
            # Use the correct data directory based on environment
            data_dir = get_data_dir()
            storage_path = os.path.join(data_dir, "memory_plugins")
            os.makedirs(storage_path, exist_ok=True)
        
        self.manager = MemoryPluginManager.get_instance(
            user_id=user_id,
            storage_path=storage_path
        )
        print(f"[MemoryPluginService] Initialized with user: {user_id}, storage_path: {storage_path}")
    
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
        print(f"[search_memories] Query: '{query}', topic: '{topic}', limit: {limit}", flush=True)
        tags = [topic] if topic else None
        results = self.manager.search(query=query, tags=tags, limit=limit)
        result_dicts = [r.to_dict() for r in results]
        print(f"[search_memories] Returned {len(result_dicts)} results", flush=True)
        return result_dicts
    
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
        result = [m.to_dict() for m in memories]
        print(f"[get_recent_memories] Retrieved {len(result)} memories from manager (limit={limit})", flush=True)
        if result:
            for i, m in enumerate(result[:3]):
                print(f"  Memory {i+1}: importance={m.get('importance', 0)}, content={m.get('content', '')[:50]}...", flush=True)
        return result
    
    def get_core_memories(self, min_importance: float = 0.8) -> List[Dict[str, Any]]:
        """获取核心记忆（importance >= 0.8）"""
        all_memories = self.get_recent_memories(limit=1000)
        core_memories = [m for m in all_memories if m.get('importance', 0) >= min_importance]
        print(f"[get_core_memories] Filtered {len(core_memories)} core memories (importance >= {min_importance}) from {len(all_memories)} total", flush=True)
        return core_memories
    
    def get_relevant_memories(self, query: str, limit: int = 30) -> List[Dict[str, Any]]:
        """
        根据查询获取相关记忆（向量相似度排序）
        用于对话上下文的记忆检索
        
        使用关键词向量相似度（Jaccard相似度）计算：
        1. 提取query的关键词
        2. 与所有记忆的关键词计算相似度
        3. 按相似度排序，返回top-5
        """
        print(f"\n[get_relevant_memories] ========== START ==========", flush=True)
        print(f"[get_relevant_memories] Query: '{query}', limit={limit}", flush=True)
        
        if not query:
            print(f"[get_relevant_memories] Query is empty, returning []", flush=True)
            return []
        
        # 提取查询关键词
        query_keywords = self._extract_keywords(query)
        print(f"[get_relevant_memories] Extracted query keywords: {query_keywords}", flush=True)
        
        if not query_keywords:
            print(f"[get_relevant_memories] No keywords extracted, falling back to search_memories", flush=True)
            # 如果无法提取关键词，回退到简单搜索
            search_results = self.search_memories(query=query, limit=limit * 2)
            print(f"[get_relevant_memories] Search returned {len(search_results)} results", flush=True)
            relevant = []
            for result in search_results:
                memory = result.get('memory', {})
                if memory.get('importance', 0) < 0.8:  # 排除核心记忆
                    relevant.append(memory)
            print(f"[get_relevant_memories] After filtering core memories: {len(relevant)} results", flush=True)
            return relevant[:limit]
        
        # 获取所有非核心记忆
        print(f"[get_relevant_memories] Fetching all memories...", flush=True)
        all_memories = self.get_recent_memories(limit=1000)
        print(f"[get_relevant_memories] Got {len(all_memories)} total memories", flush=True)
        
        library_memories = [m for m in all_memories if m.get('importance', 0) < 0.8]
        print(f"[get_relevant_memories] Filtered to {len(library_memories)} library memories (importance < 0.8)", flush=True)
        
        if not library_memories:
            print(f"[get_relevant_memories] No library memories found, returning []", flush=True)
            return []
        
        # 计算每条记忆与query的相似度
        scored_memories = []
        for idx, memory in enumerate(library_memories):
            content = memory.get('content', '')
            memory_keywords = self._extract_keywords(content)
            
            # 计算 Jaccard 相似度
            similarity = self._calculate_similarity(query_keywords, memory_keywords)
            
            # 综合评分：70% 相似度 + 30% 重要性
            importance = memory.get('importance', 0.5)
            final_score = similarity * 0.7 + importance * 0.3
            
            scored_memories.append({
                'memory': memory,
                'similarity': similarity,
                'final_score': final_score,
                'keywords': memory_keywords
            })
            
            # 打印前5条的详细信息
            if idx < 5:
                print(f"  Memory {idx+1}: keywords={memory_keywords}, sim={similarity:.3f}, importance={importance:.2f}, score={final_score:.3f}", flush=True)
        
        # 按相似度降序排序
        scored_memories.sort(key=lambda x: x['final_score'], reverse=True)
        
        # 过滤掉相似度为0的（完全无关）
        relevant = [item['memory'] for item in scored_memories if item['similarity'] > 0]
        
        # 打印调试信息
        print(f"\n[get_relevant_memories] After sorting by final_score (top 30):", flush=True)
        print(f"  Total memories with similarity > 0: {len(relevant)}", flush=True)
        for i, item in enumerate(scored_memories[:30]):
            print(f"  Rank {i+1}: score={item['final_score']:.3f}, sim={item['similarity']:.3f}, imp={item['memory'].get('importance', 0):.2f}, content={item['memory'].get('content', '')[:40]}...", flush=True)
        
        result = relevant[:limit]
        print(f"[get_relevant_memories] ========== RETURN {len(result)} results ==========\n", flush=True)
        return result
    
    def _extract_keywords(self, text: str) -> set:
        """
        从文本中提取关键词（用于向量相似度计算）
        支持中文和英文
        
        中文使用 字符级 + bigram 分词，确保能匹配到如"戒指"这样的词
        """
        if not text:
            return set()
        
        keywords = set()
        
        # 中文处理：提取所有汉字，然后生成 单字 + bigram
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        for i in range(len(chinese_chars)):
            # 单字（用于匹配单字词）
            keywords.add(chinese_chars[i])
            # bigram（连续两字，用于匹配如"戒指"、"记得"等词）
            if i < len(chinese_chars) - 1:
                bigram = chinese_chars[i] + chinese_chars[i + 1]
                keywords.add(bigram)
        
        # 英文处理：按单词切分
        english_words = re.findall(r'[a-zA-Z]+', text.lower())
        for w in english_words:
            if len(w) > 1:  # 至少2个字符
                keywords.add(w)
        
        return keywords
    
    def _calculate_similarity(self, keywords1: set, keywords2: set) -> float:
        """
        计算两个关键词集合的 Jaccard 相似度
        Jaccard = |A ∩ B| / |A ∪ B|
        """
        if not keywords1 or not keywords2:
            return 0.0
        
        intersection = len(keywords1 & keywords2)
        union = len(keywords1 | keywords2)
        
        return intersection / union if union > 0 else 0.0
    
    def get_conversation_context(self, query: str, user_profile: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        获取完整的对话上下文
        返回格式化好的上下文信息，用于构建 LLM 消息
        
        Args:
            query: 当前用户消息（用于检索相关记忆）
            user_profile: 用户基本信息（可选）
        
        Returns:
            {
                "user_info": str,  # 用户信息卡片
                "core_memories": str,  # 核心记忆卡片
                "relevant_memories": str,  # 相关记忆卡片
            }
        """
        print(f"\n[get_conversation_context] ========== START ==========", flush=True)
        print(f"[get_conversation_context] Query: '{query}'", flush=True)
        print(f"[get_conversation_context] User profile: {user_profile}", flush=True)
        
        result = {
            "user_info": "",
            "core_memories": "",
            "relevant_memories": "",
        }
        
        # 1. 用户信息
        if user_profile:
            user_info_parts = []
            if user_profile.get('name'):
                user_info_parts.append(f"姓名: {user_profile['name']}")
            if user_profile.get('age'):
                user_info_parts.append(f"年龄: {user_profile['age']}")
            if user_profile.get('gender'):
                user_info_parts.append(f"性别: {user_profile['gender']}")
            if user_profile.get('occupation'):
                user_info_parts.append(f"职业: {user_profile['occupation']}")
            if user_profile.get('location'):
                user_info_parts.append(f"所在地: {user_profile['location']}")
            if user_profile.get('bio'):
                user_info_parts.append(f"简介: {user_profile['bio']}")
            
            if user_info_parts:
                result["user_info"] = "【用户信息】\n" + "\n".join(user_info_parts)
                print(f"[get_conversation_context] User info: {len(user_info_parts)} fields", flush=True)
        
        # 2. 核心记忆
        print(f"[get_conversation_context] Getting core memories...", flush=True)
        core_memories = self.get_core_memories()
        if core_memories:
            core_texts = [f"• {m['content']}" for m in core_memories[:10]]  # 最多10条
            result["core_memories"] = "【核心记忆】\n" + "\n".join(core_texts)
            print(f"[get_conversation_context] Got {len(core_texts)} core memory texts", flush=True)
        else:
            print(f"[get_conversation_context] No core memories found", flush=True)
        
        # 3. 相关记忆（基于当前查询）
        print(f"[get_conversation_context] Getting relevant memories...", flush=True)
        relevant_memories = self.get_relevant_memories(query, limit=30)
        if relevant_memories:
            relevant_texts = [f"• {m['content']}" for m in relevant_memories]
            result["relevant_memories"] = "【相关记忆】\n" + "\n".join(relevant_texts)
            print(f"[get_conversation_context] Got {len(relevant_texts)} relevant memory texts", flush=True)
        else:
            print(f"[get_conversation_context] No relevant memories found", flush=True)
        
        print(f"[get_conversation_context] ========== END ==========\n", flush=True)
        return result
    
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
    
    # ==================== LLM 记忆评估 ====================
    
    def evaluate_memories_with_llm(
        self,
        llm_client,
        memory_ids: List[str] = None
    ) -> Dict[str, Any]:
        """
        使用 LLM 评估记忆的重要性
        
        严格标准：只有以下类型的记忆才能被标记为核心记忆（importance >= 0.8）：
        1. 用户的真实姓名、昵称
        2. 用户的年龄、生日、出生年份
        3. 用户的性别
        4. 用户的职业、工作单位、学校
        5. 用户的家庭成员关系（父母、兄弟姐妹、配偶、子女）
        6. 用户的居住地点（城市、国家）
        7. 用户的重要身份信息（如国籍、学历）
        8. 用户和你的关系
        9. 用户和你之间的称呼
        
        排除的类型：
        - 游戏角色、虚构人物的提及
        - 用户的兴趣爱好（除非是职业相关）
        - 用户的情绪状态描述
        - 用户的习惯偏好
        - 单次事件或活动的记录
        """
        # 获取所有记忆
        all_memories = self.get_recent_memories(limit=1000)
        
        # 如果指定了 memory_ids，只评估指定的记忆
        if memory_ids:
            all_memories = [m for m in all_memories if m.get('id') in memory_ids]
        
        if not all_memories:
            return {
                "success": True,
                "evaluated_count": 0,
                "core_memories": [],
                "message": "没有找到需要评估的记忆"
            }
        
        # 构建序号到ID的映射，用序号代替长UUID以节省token
        index_to_id = {}
        memory_list_text = ""
        for i, mem in enumerate(all_memories):
            idx = i + 1  # 序号从1开始
            index_to_id[idx] = mem.get('id')
            memory_list_text += f"{idx}. {mem.get('content', '')}\n"
        
        # 严格的 LLM 评估 Prompt
        evaluation_prompt = f"""你是一个严格的记忆分类专家。你的任务是**为一个情感陪伴agent**从用户的对话记忆中识别出重要的信息。

        严格标准：只有以下类型的记忆才能被标记为核心记忆：
        1. 用户的真实姓名、昵称
        2. 用户的年龄、生日、出生年份
        3. 用户的性别
        4. 用户的职业、工作单位、学校
        5. 用户的家庭成员关系（父母、兄弟姐妹、配偶、子女）
        6. 用户的居住地点（城市、国家）
        7. 用户的重要身份信息（如国籍、学历）
        8. 用户和agent的关系（非常重要)
        9. 用户和agent之间的称呼和小习惯（非常重要)
        
        排除的类型：
        - 游戏角色、虚构人物的提及
        - 用户的兴趣爱好（除非是职业相关）
        - 用户的情绪状态描述
        - 用户的习惯偏好
        - 单次事件或活动的记录

## 需要评估的记忆列表：

{memory_list_text}

## 请严格按照以下 JSON 格式输出（使用记忆的序号）：

```json
{{
  "core_indices": [1, 3, 5]
}}
```

注意：
- core_indices 是符合核心标准的记忆序号列表
- 如果没有任何记忆符合核心标准，返回空列表 `"core_indices": []`
- 宁可漏掉，不可错判 - 只有 100% 确定是核心身份信息的才放入列表
- 只输出 JSON，不要有其他解释文字"""
        
        try:
            # 创建一个允许更大 token 限制的 LLM 客户端副本，用于记忆评估
            # 这允许评估所有记忆而不截断
            from agent.llm import OpenAICompatibleClient
            eval_llm_client = OpenAICompatibleClient(
                base_url=llm_client.base_url,
                api_key=llm_client.api_key,
                model=llm_client.model,
                max_input_tokens=100000  # 设置非常高的限制，允许大量记忆输入
            )
            
            # 调用 LLM
            response_text, _ = eval_llm_client.chat(
                messages=[{"role": "user", "content": evaluation_prompt}],
                max_tokens=500,  # 只需要返回序号列表，减少输出token
                temperature=0.1  # 低温度确保稳定输出
            )
            
            # 解析响应，获取序号列表
            core_indices = self._parse_llm_evaluation_response(response_text)
            
            # 将序号映射回真实的 memory ID
            core_ids = []
            for idx in core_indices:
                if isinstance(idx, int) and idx in index_to_id:
                    core_ids.append(index_to_id[idx])
                elif isinstance(idx, str) and idx.isdigit() and int(idx) in index_to_id:
                    core_ids.append(index_to_id[int(idx)])
            
            # 更新记忆重要性
            updated_count = 0
            for mem in all_memories:
                mem_id = mem.get('id')
                if mem_id in core_ids:
                    # 核心记忆设为高重要性
                    self._update_memory_importance(mem_id, 0.9)
                    updated_count += 1
                else:
                    # 非核心记忆设为低重要性
                    self._update_memory_importance(mem_id, 0.3)
            
            # 重新获取所有记忆以获取最新的分类状态
            updated_all_memories = self.get_recent_memories(limit=1000)
            
            # 分离核心记忆和库记忆
            core_memories = []
            library_memories = []
            for mem in updated_all_memories:
                if mem.get('importance', 0.5) >= 0.8:
                    core_memories.append({
                        "id": mem.get('id'),
                        "content": mem.get('content', ''),
                        "importance": mem.get('importance', 0.5)
                    })
                else:
                    library_memories.append({
                        "id": mem.get('id'),
                        "content": mem.get('content', ''),
                        "importance": mem.get('importance', 0.5)
                    })
            
            return {
                "success": True,
                "evaluated_count": len(all_memories),
                "core_count": len(core_ids),
                "core_memory_ids": core_ids,
                "core_memories": core_memories,
                "library_memories": library_memories,
                "message": f"评估完成，共 {len(all_memories)} 条记忆，{len(core_ids)} 条被标记为核心记忆"
            }
            
        except Exception as e:
            print(f"[MemoryPluginService] LLM evaluation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "LLM 评估失败"
            }
    
    def _parse_llm_evaluation_response(self, response_text: str) -> List[int]:
        """解析 LLM 评估响应，提取核心记忆序号列表"""
        try:
            # 尝试提取 JSON 块 - 优先查找 core_indices
            json_match = re.search(r'\{[^{}]*"core_indices"[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                return data.get("core_indices", [])
            
            # 兼容旧格式 core_memory_ids（以防万一）
            json_match = re.search(r'\{[^{}]*"core_memory_ids"[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                return data.get("core_memory_ids", [])
            
            # 尝试直接匹配数字数组 [1, 2, 3]
            array_match = re.search(r'\[[\d,\s]*\]', response_text)
            if array_match:
                return json.loads(array_match.group())
            
            # 如果没有找到标准格式，尝试直接解析整个响应
            data = json.loads(response_text)
            return data.get("core_indices", data.get("core_memory_ids", []))
            
        except Exception as e:
            print(f"[MemoryPluginService] Parse LLM response error: {e}")
            print(f"Response was: {response_text}")
            return []
    
    def _update_memory_importance(self, memory_id: str, importance: float) -> bool:
        """更新记忆的重要性"""
        try:
            # 获取当前活动插件
            plugin = self.manager.get_active_plugin()
            if plugin:
                # 对于 simple_sqlite_plugin，直接更新数据库
                if hasattr(plugin, 'conn') and plugin.conn:
                    cursor = plugin.conn.cursor()
                    cursor.execute(
                        "UPDATE memories SET importance = ? WHERE id = ?",
                        (importance, memory_id)
                    )
                    plugin.conn.commit()
                    print(f"[MemoryPluginService] Updated importance for {memory_id} to {importance}")
                    return True
                # 对于有 update_memory 方法的插件
                elif hasattr(plugin, 'update_memory'):
                    return plugin.update_memory(memory_id, {"importance": importance})
            return False
        except Exception as e:
            print(f"[MemoryPluginService] Update importance error: {e}")
            return False
    
    def update_memory_importance(self, memory_id: str, importance: float) -> Dict[str, Any]:
        """公开的更新记忆重要性接口"""
        success = self._update_memory_importance(memory_id, importance)
        return {
            "success": success,
            "memory_id": memory_id,
            "importance": importance
        }
