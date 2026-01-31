"""
记忆压缩（Consolidation）
模拟睡眠时的记忆整理过程
每24小时自动执行
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json

# 为了独立运行，这里重新定义必要的类型
class EntityType(Enum):
    USER = "user"
    PERSON = "person"
    PLACE = "place"
    ORGANIZATION = "organization"
    EVENT = "event"
    CONCEPT = "concept"
    OBJECT = "object"


@dataclass
class ConsolidationConfig:
    """压缩配置"""
    consolidation_interval_hours: int = 24
    short_term_retention_hours: int = 48
    min_importance_to_keep: float = 0.2
    daily_summary_max_length: int = 500
    enable_entity_extraction: bool = True
    enable_relationship_inference: bool = True


class MemoryConsolidator:
    """
    记忆压缩器
    
    职责：
    1. 定期将短期记忆压缩为长期记忆
    2. 生成日/周/月摘要
    3. 提取实体和关系到知识图谱
    4. 清理低重要度的细节
    """
    
    def __init__(
        self,
        memory_tree,
        knowledge_graph,
        forgetting_curve,
        config: Optional[ConsolidationConfig] = None,
        llm_client: Any = None
    ):
        self.memory_tree = memory_tree
        self.knowledge_graph = knowledge_graph
        self.forgetting_curve = forgetting_curve
        self.config = config or ConsolidationConfig()
        self.llm_client = llm_client
        self.last_consolidation: Optional[datetime] = None
    
    def should_consolidate(self, current_time: Optional[datetime] = None) -> bool:
        """检查是否需要执行压缩"""
        now = current_time or datetime.now()
        if self.last_consolidation is None:
            return True
        hours_since_last = (now - self.last_consolidation).total_seconds() / 3600
        return hours_since_last >= self.config.consolidation_interval_hours
    
    async def consolidate(self, current_time: Optional[datetime] = None) -> Dict[str, Any]:
        """执行记忆压缩"""
        now = current_time or datetime.now()
        report = {"timestamp": now.isoformat(), "actions": [], "stats": {}}
        
        # 1. 更新所有记忆的强度
        all_memories = list(self.memory_tree.nodes.values())
        event_memories = [m for m in all_memories if m.time_grain == "event"]
        self.forgetting_curve.batch_update_strengths(event_memories, now)
        report["stats"]["total_memories"] = len(event_memories)
        
        # 2. 识别需要处理的记忆
        short_term_cutoff = now - timedelta(hours=self.config.short_term_retention_hours)
        memories_to_consolidate = [
            m for m in event_memories
            if m.timestamp < short_term_cutoff and not m.is_consolidated
        ]
        report["stats"]["to_consolidate"] = len(memories_to_consolidate)
        
        # 3. 按天分组并生成摘要
        days_processed = {}
        for memory in memories_to_consolidate:
            day_key = memory.timestamp.strftime("%Y-%m-%d")
            if day_key not in days_processed:
                days_processed[day_key] = []
            days_processed[day_key].append(memory)
        
        for day_key, day_memories in days_processed.items():
            summary = await self._generate_daily_summary(day_key, day_memories)
            report["actions"].append({
                "type": "daily_summary",
                "day": day_key,
                "summary": summary,
                "memory_count": len(day_memories)
            })
        
        # 4. 标记已压缩
        for memory in memories_to_consolidate:
            memory.is_consolidated = True
        
        # 5. 清理低重要度记忆
        cleaned = self._clean_low_importance_details(event_memories, now)
        report["stats"]["details_cleaned"] = cleaned
        
        self.last_consolidation = now
        return report
    
    async def _generate_daily_summary(self, day_key: str, memories: List) -> str:
        """生成每日摘要"""
        if not memories:
            return ""
        sorted_memories = sorted(
            memories,
            key=lambda m: m.calculate_effective_importance(),
            reverse=True
        )
        top_contents = [m.content for m in sorted_memories[:5]]
        return "；".join(top_contents)[:self.config.daily_summary_max_length]
    
    def _clean_low_importance_details(self, memories: List, current_time: datetime) -> int:
        """清理低重要度记忆的详细内容"""
        cleaned = 0
        for memory in memories:
            if memory.is_consolidated:
                continue
            effective_importance = memory.calculate_effective_importance()
            strength = self.forgetting_curve.calculate_retention(memory, current_time)
            if effective_importance < self.config.min_importance_to_keep and strength < 0.3:
                if hasattr(memory, 'raw_conversation') and memory.raw_conversation:
                    memory.raw_conversation = None
                    cleaned += 1
        return cleaned


class MemoryMigrator:
    """记忆迁移器 - 用于模型更换时迁移记忆"""
    
    @staticmethod
    def export_memory_snapshot(
        memory_tree,
        knowledge_graph,
        include_raw_conversations: bool = False
    ) -> Dict[str, Any]:
        """导出记忆快照"""
        snapshot = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "memory_tree": memory_tree.to_dict(),
            "knowledge_graph": knowledge_graph.to_dict()
        }
        if not include_raw_conversations:
            for node_data in snapshot["memory_tree"]["nodes"].values():
                node_data.pop("raw_conversation", None)
        return snapshot
    
    @staticmethod
    def export_to_file(memory_tree, knowledge_graph, filepath: str, **kwargs):
        """导出到文件"""
        snapshot = MemoryMigrator.export_memory_snapshot(memory_tree, knowledge_graph, **kwargs)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def generate_migration_summary(memory_tree, knowledge_graph) -> str:
        """生成迁移摘要"""
        lines = []
        total_memories = sum(1 for n in memory_tree.nodes.values() if n.time_grain == "event")
        lines.append(f"共有 {total_memories} 条记忆。")
        
        if memory_tree.year_index:
            years = sorted(memory_tree.year_index.keys())
            lines.append(f"时间跨度: {years[0]} - {years[-1]}")
        
        profile = knowledge_graph.user_profile
        if profile.name:
            lines.append(f"用户: {profile.name}")
        
        people = knowledge_graph.get_entities_by_type(EntityType.PERSON)
        if people:
            important_people = sorted(people, key=lambda x: x.importance, reverse=True)[:5]
            names = [p.name for p in important_people]
            lines.append(f"重要人物: {', '.join(names)}")
        
        return "\n".join(lines)
