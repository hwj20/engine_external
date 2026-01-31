"""
时间线性记忆树
按时间层级组织记忆，支持按需展开细节
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from collections import defaultdict
import json

from .models import MemoryNode, MemoryType


class TemporalMemoryTree:
    """
    时间记忆树
    
    结构示例：
    2024
    ├── 2024-01 (1月)
    │   ├── 2024-W01 (第1周)
    │   │   ├── 2024-01-01 (周一)
    │   │   │   ├── event_001: "和小明吃了火锅"
    │   │   │   ├── event_002: "讨论了工作的事"
    │   │   │   └── event_003: "用户提到最近压力大"
    │   │   └── 2024-01-02
    │   └── 2024-W02
    └── 2024-02
    """
    
    def __init__(self):
        # 所有节点的扁平存储
        self.nodes: Dict[str, MemoryNode] = {}
        
        # 时间索引：快速定位
        self.year_index: Dict[str, str] = {}      # "2024" -> node_id
        self.month_index: Dict[str, str] = {}     # "2024-01" -> node_id
        self.week_index: Dict[str, str] = {}      # "2024-W01" -> node_id
        self.day_index: Dict[str, str] = {}       # "2024-01-01" -> node_id
        
        # 根节点（虚拟）
        self.root_children: List[str] = []        # 年份节点列表
    
    def _get_time_keys(self, dt: datetime) -> Dict[str, str]:
        """获取时间的各级key"""
        return {
            "year": dt.strftime("%Y"),
            "month": dt.strftime("%Y-%m"),
            "week": f"{dt.year}-W{dt.isocalendar()[1]:02d}",
            "day": dt.strftime("%Y-%m-%d")
        }
    
    def _ensure_time_hierarchy(self, dt: datetime) -> str:
        """
        确保时间层级存在，返回日节点ID
        如果不存在则创建
        """
        keys = self._get_time_keys(dt)
        
        # 确保年节点
        if keys["year"] not in self.year_index:
            year_node = MemoryNode(
                time_grain="year",
                timestamp=datetime(dt.year, 1, 1),
                content=f"{dt.year}年的记忆"
            )
            self.nodes[year_node.id] = year_node
            self.year_index[keys["year"]] = year_node.id
            self.root_children.append(year_node.id)
        
        year_id = self.year_index[keys["year"]]
        
        # 确保月节点
        if keys["month"] not in self.month_index:
            month_node = MemoryNode(
                time_grain="month",
                timestamp=datetime(dt.year, dt.month, 1),
                content=f"{dt.year}年{dt.month}月的记忆",
                parent_id=year_id
            )
            self.nodes[month_node.id] = month_node
            self.month_index[keys["month"]] = month_node.id
            self.nodes[year_id].children_ids.append(month_node.id)
        
        month_id = self.month_index[keys["month"]]
        
        # 确保周节点
        if keys["week"] not in self.week_index:
            # 计算这周的开始日期
            week_start = dt - timedelta(days=dt.weekday())
            week_node = MemoryNode(
                time_grain="week",
                timestamp=week_start,
                content=f"{dt.year}年第{dt.isocalendar()[1]}周的记忆",
                parent_id=month_id
            )
            self.nodes[week_node.id] = week_node
            self.week_index[keys["week"]] = week_node.id
            self.nodes[month_id].children_ids.append(week_node.id)
        
        week_id = self.week_index[keys["week"]]
        
        # 确保日节点
        if keys["day"] not in self.day_index:
            day_node = MemoryNode(
                time_grain="day",
                timestamp=datetime(dt.year, dt.month, dt.day),
                content=f"{dt.month}月{dt.day}日的记忆",
                parent_id=week_id
            )
            self.nodes[day_node.id] = day_node
            self.day_index[keys["day"]] = day_node.id
            self.nodes[week_id].children_ids.append(day_node.id)
        
        return self.day_index[keys["day"]]
    
    def add_memory(self, memory: MemoryNode) -> str:
        """
        添加一条记忆到树中
        
        Args:
            memory: 记忆节点
            
        Returns:
            记忆节点ID
        """
        # 确保时间层级存在
        day_id = self._ensure_time_hierarchy(memory.timestamp)
        
        # 设置父节点为日节点
        memory.parent_id = day_id
        memory.time_grain = "event"
        
        # 存储
        self.nodes[memory.id] = memory
        self.nodes[day_id].children_ids.append(memory.id)
        
        # 更新日节点的摘要
        self._update_day_summary(day_id)
        
        return memory.id
    
    def _update_day_summary(self, day_id: str):
        """更新日节点的摘要"""
        day_node = self.nodes[day_id]
        events = [self.nodes[cid] for cid in day_node.children_ids]
        
        if events:
            # 按重要度排序，取top事件生成摘要
            top_events = sorted(
                events, 
                key=lambda x: x.calculate_effective_importance(), 
                reverse=True
            )[:3]
            
            summaries = [e.content for e in top_events]
            day_node.content = "；".join(summaries)
            day_node.base_importance = max(e.base_importance for e in events)
    
    def get_memory(self, memory_id: str) -> Optional[MemoryNode]:
        """获取指定记忆"""
        return self.nodes.get(memory_id)
    
    def get_day_memories(self, date: datetime) -> List[MemoryNode]:
        """获取某天的所有记忆"""
        day_key = date.strftime("%Y-%m-%d")
        if day_key not in self.day_index:
            return []
        
        day_id = self.day_index[day_key]
        day_node = self.nodes[day_id]
        
        return [self.nodes[cid] for cid in day_node.children_ids]
    
    def get_range_memories(
        self, 
        start: datetime, 
        end: datetime,
        min_importance: float = 0.0
    ) -> List[MemoryNode]:
        """
        获取时间范围内的记忆
        
        Args:
            start: 开始时间
            end: 结束时间
            min_importance: 最低重要度阈值
        """
        memories = []
        current = start
        
        while current <= end:
            day_memories = self.get_day_memories(current)
            for mem in day_memories:
                if mem.calculate_effective_importance() >= min_importance:
                    memories.append(mem)
            current += timedelta(days=1)
        
        return memories
    
    def get_tree_view(
        self, 
        grain: str = "month",
        year: Optional[int] = None,
        month: Optional[int] = None,
        expand_important: bool = True,
        importance_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        获取树形视图
        
        Args:
            grain: 展示粒度 (year/month/week/day)
            year: 指定年份
            month: 指定月份
            expand_important: 是否展开高重要度节点
            importance_threshold: 高重要度阈值
            
        Returns:
            树形结构字典
        """
        result = {"type": "root", "children": []}
        
        # 确定要展示的年份
        years_to_show = [year] if year else [int(y) for y in self.year_index.keys()]
        
        for y in sorted(years_to_show):
            year_key = str(y)
            if year_key not in self.year_index:
                continue
            
            year_node = self.nodes[self.year_index[year_key]]
            year_view = {
                "type": "year",
                "label": f"{y}年",
                "id": year_node.id,
                "importance": year_node.base_importance,
                "children": []
            }
            
            if grain == "year":
                year_view["summary"] = year_node.content
            else:
                # 展开到月
                for month_id in year_node.children_ids:
                    month_node = self.nodes[month_id]
                    
                    # 如果指定了月份，只展示该月
                    if month and month_node.timestamp.month != month:
                        continue
                    
                    month_view = self._build_month_view(
                        month_node, grain, expand_important, importance_threshold
                    )
                    year_view["children"].append(month_view)
            
            result["children"].append(year_view)
        
        return result
    
    def _build_month_view(
        self, 
        month_node: MemoryNode,
        grain: str,
        expand_important: bool,
        importance_threshold: float
    ) -> Dict[str, Any]:
        """构建月视图"""
        month_view = {
            "type": "month",
            "label": month_node.timestamp.strftime("%Y年%m月"),
            "id": month_node.id,
            "importance": month_node.base_importance,
            "children": []
        }
        
        if grain == "month":
            month_view["summary"] = month_node.content
            # 展示高重要度事件
            if expand_important:
                important_events = self._get_important_events(
                    month_node, importance_threshold
                )
                month_view["highlighted_events"] = important_events
        else:
            # 展开到周或日
            for week_id in month_node.children_ids:
                week_node = self.nodes[week_id]
                week_view = self._build_week_view(
                    week_node, grain, expand_important, importance_threshold
                )
                month_view["children"].append(week_view)
        
        return month_view
    
    def _build_week_view(
        self,
        week_node: MemoryNode,
        grain: str,
        expand_important: bool,
        importance_threshold: float
    ) -> Dict[str, Any]:
        """构建周视图"""
        week_view = {
            "type": "week",
            "label": f"第{week_node.timestamp.isocalendar()[1]}周",
            "id": week_node.id,
            "importance": week_node.base_importance,
            "children": []
        }
        
        if grain == "week":
            week_view["summary"] = week_node.content
            if expand_important:
                important_events = self._get_important_events(
                    week_node, importance_threshold
                )
                week_view["highlighted_events"] = important_events
        else:
            # 展开到日
            for day_id in week_node.children_ids:
                day_node = self.nodes[day_id]
                day_view = self._build_day_view(day_node)
                week_view["children"].append(day_view)
        
        return week_view
    
    def _build_day_view(self, day_node: MemoryNode) -> Dict[str, Any]:
        """构建日视图"""
        events = []
        for event_id in day_node.children_ids:
            event = self.nodes[event_id]
            events.append({
                "id": event.id,
                "content": event.content,
                "importance": event.calculate_effective_importance(),
                "emotion_tags": event.emotion_tags,
                "mention_count": event.mention_count
            })
        
        return {
            "type": "day",
            "label": day_node.timestamp.strftime("%m月%d日"),
            "id": day_node.id,
            "importance": day_node.base_importance,
            "events": sorted(events, key=lambda x: x["importance"], reverse=True)
        }
    
    def _get_important_events(
        self, 
        parent_node: MemoryNode, 
        threshold: float
    ) -> List[Dict[str, Any]]:
        """递归获取高重要度事件"""
        important = []
        
        def traverse(node_id: str):
            node = self.nodes[node_id]
            if node.time_grain == "event":
                if node.calculate_effective_importance() >= threshold:
                    important.append({
                        "id": node.id,
                        "content": node.content,
                        "importance": node.calculate_effective_importance(),
                        "timestamp": node.timestamp.isoformat()
                    })
            else:
                for child_id in node.children_ids:
                    traverse(child_id)
        
        traverse(parent_node.id)
        return sorted(important, key=lambda x: x["importance"], reverse=True)
    
    def search_by_content(
        self, 
        query: str,
        limit: int = 10,
        min_importance: float = 0.0
    ) -> List[MemoryNode]:
        """
        简单的内容搜索
        实际使用中应该接入向量数据库
        """
        results = []
        
        for node in self.nodes.values():
            if node.time_grain != "event":
                continue
            
            if node.calculate_effective_importance() < min_importance:
                continue
            
            # 简单的关键词匹配
            if query.lower() in node.content.lower():
                results.append(node)
            elif node.detail and query.lower() in node.detail.lower():
                results.append(node)
        
        # 按重要度排序
        results.sort(key=lambda x: x.calculate_effective_importance(), reverse=True)
        
        return results[:limit]
    
    def search_by_time_and_topic(
        self,
        time_hint: Optional[str] = None,  # "昨天", "上周", "去年"
        topic: Optional[str] = None,
        reference_time: Optional[datetime] = None
    ) -> List[MemoryNode]:
        """
        根据时间提示和话题搜索
        
        Args:
            time_hint: 时间描述词
            topic: 话题关键词
            reference_time: 参考时间（默认当前时间）
        """
        ref = reference_time or datetime.now()
        
        # 解析时间提示
        start, end = self._parse_time_hint(time_hint, ref)
        
        # 获取时间范围内的记忆
        memories = self.get_range_memories(start, end)
        
        # 如果有话题，进一步过滤
        if topic:
            memories = [
                m for m in memories 
                if topic.lower() in m.content.lower() or
                   any(topic.lower() in tag.lower() for tag in m.topic_tags)
            ]
        
        return memories
    
    def _parse_time_hint(
        self, 
        hint: Optional[str], 
        ref: datetime
    ) -> Tuple[datetime, datetime]:
        """解析时间提示词"""
        if not hint:
            # 默认返回最近一周
            return ref - timedelta(days=7), ref
        
        hint = hint.lower()
        
        if "昨天" in hint or "昨晚" in hint:
            yesterday = ref - timedelta(days=1)
            return datetime(yesterday.year, yesterday.month, yesterday.day), \
                   datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59)
        
        if "前天" in hint:
            day = ref - timedelta(days=2)
            return datetime(day.year, day.month, day.day), \
                   datetime(day.year, day.month, day.day, 23, 59, 59)
        
        if "上周" in hint:
            start = ref - timedelta(days=ref.weekday() + 7)
            end = start + timedelta(days=6)
            return start, end
        
        if "上个月" in hint or "上月" in hint:
            first_of_month = datetime(ref.year, ref.month, 1)
            last_month_end = first_of_month - timedelta(days=1)
            last_month_start = datetime(last_month_end.year, last_month_end.month, 1)
            return last_month_start, last_month_end
        
        if "去年" in hint:
            return datetime(ref.year - 1, 1, 1), datetime(ref.year - 1, 12, 31)
        
        # 默认最近一周
        return ref - timedelta(days=7), ref
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "year_index": self.year_index,
            "month_index": self.month_index,
            "week_index": self.week_index,
            "day_index": self.day_index,
            "root_children": self.root_children
        }
    
    def save(self, filepath: str):
        """保存到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, filepath: str) -> 'TemporalMemoryTree':
        """从文件加载"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        tree = cls()
        # 重建节点（需要实现from_dict方法）
        # 这里简化处理
        tree.year_index = data["year_index"]
        tree.month_index = data["month_index"]
        tree.week_index = data["week_index"]
        tree.day_index = data["day_index"]
        tree.root_children = data["root_children"]
        
        return tree
