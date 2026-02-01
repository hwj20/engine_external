"""
艾宾浩斯遗忘曲线实现
管理记忆的自然衰减和强化
"""

import math
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from schema.models import MemoryNode


@dataclass
class ForgettingConfig:
    """遗忘曲线配置"""
    # 基础衰减率（每天）
    base_decay_rate: float = 0.3
    
    # 最小记忆强度（低于此值可能被清理）
    min_strength: float = 0.1
    
    # 提及强化效果
    mention_boost: float = 0.4
    
    # 重要度对衰减的影响（重要度越高，衰减越慢）
    importance_decay_factor: float = 0.5
    
    # 间隔重复效应（重复次数越多，衰减越慢）
    repetition_decay_factor: float = 0.2
    
    # 理想复习间隔（天数）
    review_intervals: List[int] = None
    
    def __post_init__(self):
        if self.review_intervals is None:
            # 艾宾浩斯推荐的复习间隔
            self.review_intervals = [1, 2, 4, 7, 15, 30, 60, 120]


class ForgettingCurve:
    """
    艾宾浩斯遗忘曲线
    
    核心公式：
    R = e^(-t/S)
    
    其中：
    - R: 记忆保持率 (retention)
    - t: 时间间隔
    - S: 记忆稳定性 (受重要度、重复次数影响)
    
    扩展：
    - 被提及会强化记忆
    - 重要度高的记忆衰减更慢
    - 多次重复会增加稳定性
    """
    
    def __init__(self, config: Optional[ForgettingConfig] = None):
        self.config = config or ForgettingConfig()
    
    def calculate_stability(self, memory: MemoryNode) -> float:
        """
        计算记忆稳定性
        稳定性越高，遗忘越慢
        
        影响因素：
        1. 基础重要度
        2. 被提及次数
        3. 复习时机是否合理
        """
        base_stability = 1.0
        
        # 重要度加成
        importance_bonus = memory.base_importance * self.config.importance_decay_factor
        
        # 重复次数加成（边际效应递减）
        repetition_bonus = math.log1p(memory.mention_count) * self.config.repetition_decay_factor
        
        # 情感强度加成（有情感标签的记忆更持久）
        emotion_bonus = 0.1 * len(memory.emotion_tags)
        
        return base_stability + importance_bonus + repetition_bonus + emotion_bonus
    
    def calculate_retention(
        self, 
        memory: MemoryNode, 
        current_time: Optional[datetime] = None
    ) -> float:
        """
        计算记忆保持率
        
        Returns:
            保持率 [0, 1]
        """
        now = current_time or datetime.now()
        
        # 计算距离上次强化的时间
        last_reinforced = memory.last_mentioned or memory.created_at
        days_elapsed = (now - last_reinforced).total_seconds() / 86400
        
        if days_elapsed <= 0:
            return 1.0
        
        # 计算稳定性
        stability = self.calculate_stability(memory)
        
        # 艾宾浩斯公式
        retention = math.exp(-days_elapsed / (stability * 10))
        
        return max(self.config.min_strength, retention)
    
    def update_memory_strength(
        self, 
        memory: MemoryNode,
        current_time: Optional[datetime] = None
    ) -> float:
        """
        更新记忆强度
        
        Returns:
            更新后的强度
        """
        retention = self.calculate_retention(memory, current_time)
        memory.current_strength = retention
        memory.updated_at = current_time or datetime.now()
        return retention
    
    def reinforce_memory(
        self, 
        memory: MemoryNode,
        current_time: Optional[datetime] = None
    ) -> float:
        """
        强化记忆（被提及时调用）
        
        Returns:
            强化后的强度
        """
        now = current_time or datetime.now()
        
        # 先计算当前强度
        current_retention = self.calculate_retention(memory, now)
        
        # 应用强化
        new_strength = min(1.0, current_retention + self.config.mention_boost)
        
        # 更新记忆
        memory.current_strength = new_strength
        memory.mention_count += 1
        memory.last_mentioned = now
        memory.mention_history.append(now)
        memory.updated_at = now
        
        # 基于复习时机调整基础重要度
        self._adjust_importance_by_review_timing(memory, now)
        
        return new_strength
    
    def _adjust_importance_by_review_timing(
        self, 
        memory: MemoryNode, 
        now: datetime
    ):
        """
        根据复习时机调整重要度
        
        如果用户在"最佳复习时间"附近提及，说明这个记忆对用户重要
        """
        if len(memory.mention_history) < 2:
            return
        
        # 计算平均复习间隔
        intervals = []
        sorted_history = sorted(memory.mention_history)
        for i in range(1, len(sorted_history)):
            interval = (sorted_history[i] - sorted_history[i-1]).days
            intervals.append(interval)
        
        if not intervals:
            return
        
        avg_interval = sum(intervals) / len(intervals)
        
        # 如果用户频繁提及（间隔小于理想间隔的一半），增加重要度
        ideal_interval = self.config.review_intervals[
            min(len(memory.mention_history) - 1, len(self.config.review_intervals) - 1)
        ]
        
        if avg_interval < ideal_interval * 0.5:
            # 频繁提及，增加重要度
            memory.base_importance = min(1.0, memory.base_importance + 0.05)
    
    def batch_update_strengths(
        self, 
        memories: List[MemoryNode],
        current_time: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        批量更新记忆强度
        
        Returns:
            {memory_id: new_strength}
        """
        results = {}
        for memory in memories:
            new_strength = self.update_memory_strength(memory, current_time)
            results[memory.id] = new_strength
        return results
    
    def get_memories_to_surface(
        self,
        memories: List[MemoryNode],
        current_time: Optional[datetime] = None,
        strength_threshold: float = 0.3,
        top_k: int = 5
    ) -> List[MemoryNode]:
        """
        获取应该"浮现"的记忆
        
        适合在对话开始时调用，主动提及一些用户可能感兴趣的记忆
        
        选择标准：
        1. 强度中等（不是太新也不是太旧）
        2. 重要度较高
        3. 正好处于"最佳复习时间"附近
        """
        now = current_time or datetime.now()
        candidates = []
        
        for memory in memories:
            strength = self.calculate_retention(memory, now)
            
            # 太新或太弱的不考虑
            if strength > 0.9 or strength < strength_threshold:
                continue
            
            # 计算"复习紧迫度"
            days_since_mention = (now - (memory.last_mentioned or memory.created_at)).days
            review_count = len(memory.mention_history)
            
            # 根据复习次数确定理想间隔
            ideal_interval = self.config.review_intervals[
                min(review_count, len(self.config.review_intervals) - 1)
            ]
            
            # 越接近理想间隔，紧迫度越高
            urgency = 1.0 - abs(days_since_mention - ideal_interval) / ideal_interval
            urgency = max(0, urgency)
            
            # 综合得分
            score = urgency * memory.base_importance * (1 - strength)
            
            candidates.append((memory, score))
        
        # 按得分排序
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return [m for m, _ in candidates[:top_k]]
    
    def identify_fading_memories(
        self,
        memories: List[MemoryNode],
        current_time: Optional[datetime] = None,
        threshold: float = 0.2
    ) -> List[MemoryNode]:
        """
        识别即将遗忘的记忆
        
        用于：
        1. 提醒用户
        2. 决定是否需要压缩存储
        """
        now = current_time or datetime.now()
        fading = []
        
        for memory in memories:
            strength = self.calculate_retention(memory, now)
            if strength < threshold:
                fading.append(memory)
        
        return fading
    
    def get_memory_forecast(
        self,
        memory: MemoryNode,
        days_ahead: int = 30,
        current_time: Optional[datetime] = None
    ) -> List[Tuple[datetime, float]]:
        """
        预测记忆强度变化
        
        Returns:
            [(时间点, 预测强度), ...]
        """
        now = current_time or datetime.now()
        forecast = []
        
        for day in range(days_ahead + 1):
            future_time = now + timedelta(days=day)
            predicted_strength = self.calculate_retention(memory, future_time)
            forecast.append((future_time, predicted_strength))
        
        return forecast
    
    def suggest_review_time(
        self,
        memory: MemoryNode,
        current_time: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        建议下次复习时间
        """
        now = current_time or datetime.now()
        review_count = len(memory.mention_history)
        
        # 根据复习次数选择间隔
        interval_index = min(review_count, len(self.config.review_intervals) - 1)
        ideal_interval = self.config.review_intervals[interval_index]
        
        # 考虑重要度调整
        adjusted_interval = ideal_interval * (1 + (1 - memory.base_importance) * 0.5)
        
        last_review = memory.last_mentioned or memory.created_at
        suggested = last_review + timedelta(days=adjusted_interval)
        
        # 如果建议时间已过，返回当前时间
        if suggested < now:
            return now
        
        return suggested


class ContextMemorySelector:
    """
    Context 记忆选择器
    
    决定哪些记忆应该注入到对话 context 中
    """
    
    def __init__(
        self,
        forgetting_curve: ForgettingCurve,
        max_context_memories: int = 10,
        min_strength_for_context: float = 0.3
    ):
        self.forgetting_curve = forgetting_curve
        self.max_context_memories = max_context_memories
        self.min_strength_for_context = min_strength_for_context
    
    def select_for_context(
        self,
        all_memories: List[MemoryNode],
        current_topics: List[str] = None,
        current_entities: List[str] = None,
        current_time: Optional[datetime] = None
    ) -> List[MemoryNode]:
        """
        选择应该注入context的记忆
        
        优先级：
        1. 与当前话题相关的记忆
        2. 与当前提及实体相关的记忆
        3. 高重要度且强度足够的记忆
        4. 最近的记忆
        """
        now = current_time or datetime.now()
        scored_memories = []
        
        for memory in all_memories:
            # 计算当前强度
            strength = self.forgetting_curve.calculate_retention(memory, now)
            
            # 强度太低的不考虑
            if strength < self.min_strength_for_context:
                continue
            
            # 计算综合得分
            score = self._calculate_context_score(
                memory, strength, current_topics, current_entities, now
            )
            scored_memories.append((memory, score))
        
        # 排序并选择
        scored_memories.sort(key=lambda x: x[1], reverse=True)
        selected = [m for m, _ in scored_memories[:self.max_context_memories]]
        
        return selected
    
    def _calculate_context_score(
        self,
        memory: MemoryNode,
        strength: float,
        current_topics: List[str],
        current_entities: List[str],
        now: datetime
    ) -> float:
        """计算记忆的context得分"""
        score = 0.0
        
        # 基础分：重要度 × 强度
        base_score = memory.base_importance * strength
        score += base_score * 0.4
        
        # 话题相关性
        if current_topics:
            topic_match = sum(
                1 for t in current_topics 
                if any(t.lower() in tag.lower() for tag in memory.topic_tags)
            )
            score += topic_match * 0.3
        
        # 实体相关性
        if current_entities:
            entity_match = sum(
                1 for e in current_entities if e in memory.linked_entities
            )
            score += entity_match * 0.2
        
        # 时效性（最近的记忆加分）
        days_ago = (now - memory.timestamp).days
        recency_score = 1.0 / (1 + days_ago / 7)  # 一周内的记忆加分
        score += recency_score * 0.1
        
        return score
    
    def generate_context_summary(
        self,
        selected_memories: List[MemoryNode]
    ) -> str:
        """
        生成注入prompt的记忆摘要
        """
        if not selected_memories:
            return ""
        
        lines = ["[相关记忆]"]
        
        for memory in selected_memories:
            timestamp_str = memory.timestamp.strftime("%Y-%m-%d")
            importance_indicator = "★" * int(memory.base_importance * 5)
            lines.append(f"- [{timestamp_str}] {memory.content} {importance_indicator}")
        
        return "\n".join(lines)
