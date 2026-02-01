"""
Agent记忆框架使用示例
演示完整的使用流程
"""

import asyncio
from datetime import datetime, timedelta
import sys
import os

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schema.models import MemoryNode, EntityType, RelationType
from schema.temporal_tree import TemporalMemoryTree
from schema.knowledge_graph import KnowledgeGraph
from core.forgetting_curve import ForgettingCurve, ContextMemorySelector
from core.consolidation import MemoryConsolidator, MemoryMigrator
from core.memory_manager import MemoryManager


def demo_basic_usage():
    """基础使用示例"""
    print("=" * 60)
    print("1. 基础使用示例")
    print("=" * 60)
    
    # 创建记忆管理器
    manager = MemoryManager(user_id="demo_user")
    
    # 模拟一周的对话记忆
    memories_data = [
        {
            "content": "用户说今天心情不太好，工作压力大",
            "timestamp": datetime.now() - timedelta(days=6),
            "importance": 0.7,
            "emotion_tags": ["压力", "负面"],
            "topic_tags": ["工作", "情绪"]
        },
        {
            "content": "和用户聊了小明的事，小明是用户的大学室友",
            "timestamp": datetime.now() - timedelta(days=5),
            "importance": 0.5,
            "topic_tags": ["朋友", "回忆"],
            "entities": [
                {"name": "小明", "type": "person", "relation": "朋友", "relation_desc": "大学室友"}
            ]
        },
        {
            "content": "用户说晚上和女朋友小红一起吃了火锅",
            "timestamp": datetime.now() - timedelta(days=3),
            "importance": 0.6,
            "emotion_tags": ["开心"],
            "topic_tags": ["美食", "约会"],
            "entities": [
                {"name": "小红", "type": "person", "relation": "恋人", "relation_desc": "女朋友"}
            ]
        },
        {
            "content": "用户提到最近在学Python，想做一个个人项目",
            "timestamp": datetime.now() - timedelta(days=2),
            "importance": 0.6,
            "topic_tags": ["学习", "编程"]
        },
        {
            "content": "用户说小明下周要来北京出差",
            "timestamp": datetime.now() - timedelta(days=1),
            "importance": 0.5,
            "topic_tags": ["朋友", "计划"],
            "entities": [
                {"name": "小明", "type": "person"}
            ]
        },
        {
            "content": "今天用户很开心，说项目进展顺利",
            "timestamp": datetime.now(),
            "importance": 0.5,
            "emotion_tags": ["开心"],
            "topic_tags": ["工作"]
        }
    ]
    
    # 添加记忆
    for data in memories_data:
        memory_id = manager.add_memory(**data)
        print(f"✓ 添加记忆: {data['content'][:30]}...")
    
    print(f"\n当前共有 {manager.get_stats()['total_memories']} 条记忆")
    
    return manager


def demo_memory_query(manager: MemoryManager):
    """记忆查询示例"""
    print("\n" + "=" * 60)
    print("2. 记忆查询示例")
    print("=" * 60)
    
    # 查询示例1：时间查询
    print("\n【查询】昨天聊了什么？")
    result = manager.answer_memory_query("昨天我们聊了什么？")
    if result["found"]:
        print(f"找到 {len(result['memories'])} 条相关记忆:")
        print(result["answer_hint"])
    
    # 查询示例2：实体查询
    print("\n【查询】小明是谁？")
    entity_info = manager.get_entity_info("小明")
    if entity_info:
        print(f"实体: {entity_info['basic_info']['name']}")
        print(f"提及次数: {entity_info['basic_info']['mention_count']}")
        if entity_info['relationships']:
            print(f"关系: {entity_info['relationships']}")
    
    # 查询示例3：关键词搜索
    print("\n【查询】关于火锅的记忆")
    memories = manager.search_memories(query="火锅")
    for m in memories:
        print(f"- [{m.timestamp.strftime('%m-%d')}] {m.content}")


def demo_forgetting_curve(manager: MemoryManager):
    """艾宾浩斯遗忘曲线示例"""
    print("\n" + "=" * 60)
    print("3. 艾宾浩斯遗忘曲线示例")
    print("=" * 60)
    
    # 获取所有事件记忆
    all_events = [n for n in manager.memory_tree.nodes.values() if n.time_grain == "event"]
    
    print("\n各记忆当前强度:")
    for memory in sorted(all_events, key=lambda x: x.timestamp):
        strength = manager.forgetting_curve.calculate_retention(memory)
        importance = memory.calculate_effective_importance()
        bar = "█" * int(strength * 20)
        print(f"  [{memory.timestamp.strftime('%m-%d')}] {memory.content[:25]:25s} 强度:{strength:.2f} {bar}")
    
    # 模拟强化某条记忆
    print("\n模拟用户再次提起'小明'...")
    xiaoming_memories = manager.search_memories(entity_name="小明")
    if xiaoming_memories:
        old_strength = xiaoming_memories[0].current_strength
        new_strength = manager.reinforce_memory(xiaoming_memories[0].id)
        print(f"记忆强度: {old_strength:.2f} → {new_strength:.2f}")


def demo_context_injection(manager: MemoryManager):
    """Context注入示例"""
    print("\n" + "=" * 60)
    print("4. Context注入示例")
    print("=" * 60)
    
    # 场景：用户正在聊工作的话题
    print("\n【场景】用户说'最近工作好累'，Agent需要获取相关context")
    
    context = manager.get_full_context(
        current_topics=["工作", "压力"],
        current_entities=[]
    )
    
    print("\n注入到prompt的context:")
    print("-" * 40)
    print(context)
    print("-" * 40)


def demo_knowledge_graph(manager: MemoryManager):
    """知识图谱示例"""
    print("\n" + "=" * 60)
    print("5. 知识图谱示例")
    print("=" * 60)
    
    # 获取社交圈
    social_circle = manager.get_social_circle()
    
    print("\n用户的社交圈:")
    for circle_name, people in social_circle.get("circles", {}).items():
        if people:
            names = [p["name"] for p in people]
            print(f"  {circle_name}: {', '.join(names)}")
    
    # 更新用户画像
    manager.update_user_profile({
        "demographics": {"location": "北京", "occupation": "程序员"},
        "interests": ["编程", "火锅", "旅行"],
        "preferences": {"communication_style": "直接简洁"}
    })
    
    print("\n更新后的用户画像:")
    profile = manager.knowledge_graph.get_user_profile()
    print(f"  位置: {profile.get('demographics', {}).get('location')}")
    print(f"  兴趣: {profile.get('interests')}")


def demo_tree_view(manager: MemoryManager):
    """时间树视图示例"""
    print("\n" + "=" * 60)
    print("6. 时间树视图示例")
    print("=" * 60)
    
    # 获取周粒度视图
    tree_view = manager.memory_tree.get_tree_view(
        grain="day",
        expand_important=True,
        importance_threshold=0.5
    )
    
    def print_tree(node, indent=0):
        prefix = "  " * indent
        label = node.get("label", node.get("type"))
        print(f"{prefix}├─ {label}")
        
        # 打印事件
        if "events" in node:
            for event in node["events"][:3]:
                imp = "★" * int(event["importance"] * 5)
                print(f"{prefix}│   • {event['content'][:30]}... {imp}")
        
        # 打印高亮事件
        if "highlighted_events" in node:
            for event in node["highlighted_events"][:2]:
                print(f"{prefix}│   ⭐ {event['content'][:30]}...")
        
        # 递归子节点
        for child in node.get("children", []):
            print_tree(child, indent + 1)
    
    print("\n记忆时间树:")
    for year_node in tree_view.get("children", []):
        print_tree(year_node)


def demo_migration(manager: MemoryManager):
    """迁移示例"""
    print("\n" + "=" * 60)
    print("7. 模型迁移示例")
    print("=" * 60)
    
    # 生成迁移摘要
    summary = manager.get_migration_summary()
    print("\n迁移摘要（用于新模型快速了解历史）:")
    print("-" * 40)
    print(summary)
    print("-" * 40)
    
    # 导出快照（演示）
    print("\n可以调用 manager.export_for_migration('backup.json') 导出完整数据")


async def demo_consolidation(manager: MemoryManager):
    """记忆压缩示例"""
    print("\n" + "=" * 60)
    print("8. 记忆压缩示例（模拟24小时后）")
    print("=" * 60)
    
    # 强制触发压缩
    manager.consolidator.last_consolidation = None
    report = await manager.run_consolidation()
    
    print(f"\n压缩报告:")
    print(f"  处理时间: {report['timestamp']}")
    print(f"  总记忆数: {report['stats'].get('total_memories', 0)}")
    print(f"  压缩数量: {report['stats'].get('to_consolidate', 0)}")
    
    if report['actions']:
        print("\n生成的每日摘要:")
        for action in report['actions']:
            if action['type'] == 'daily_summary':
                print(f"  [{action['day']}] {action['summary'][:50]}...")


def main():
    """主函数"""
    print("\n" + "🧠 Agent 终身记忆框架演示 🧠".center(60))
    print("=" * 60)
    
    # 运行所有演示
    manager = demo_basic_usage()
    demo_memory_query(manager)
    demo_forgetting_curve(manager)
    demo_context_injection(manager)
    demo_knowledge_graph(manager)
    demo_tree_view(manager)
    demo_migration(manager)
    
    # 异步演示
    asyncio.run(demo_consolidation(manager))
    
    # 最终统计
    print("\n" + "=" * 60)
    print("最终统计")
    print("=" * 60)
    stats = manager.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n✅ 演示完成!")


if __name__ == "__main__":
    main()
