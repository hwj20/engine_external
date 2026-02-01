"""
Conversations API - Lazy loading for large conversation files
Only loads titles initially, full content loaded on demand
"""
import os
import json
from typing import Optional
from pydantic import BaseModel

# Path to conversations.json
PERSONAL_INFO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 
    "personal_info", "data"
)
CONVERSATIONS_FILE = os.path.join(PERSONAL_INFO_DIR, "conversations.json")


class ConversationSummary(BaseModel):
    """Summary of a conversation (title only for list view)"""
    conversation_id: str
    title: str
    create_time: Optional[float] = None
    update_time: Optional[float] = None
    message_count: int = 0


class ConversationMessage(BaseModel):
    """A single message in a conversation"""
    id: str
    role: str  # 'user', 'assistant', 'system'
    content: str
    create_time: Optional[float] = None


class ConversationDetail(BaseModel):
    """Full conversation detail with messages"""
    conversation_id: str
    title: str
    messages: list[ConversationMessage]
    create_time: Optional[float] = None
    update_time: Optional[float] = None


def get_conversations_list() -> list[ConversationSummary]:
    """
    Get list of conversations with titles only (lazy loading)
    Only parses minimal data for performance
    """
    if not os.path.exists(CONVERSATIONS_FILE):
        return []
    
    try:
        with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        summaries = []
        for conv in data:
            # Count messages in mapping
            mapping = conv.get('mapping', {})
            message_count = sum(
                1 for node in mapping.values() 
                if node.get('message') is not None
            )
            
            summary = ConversationSummary(
                conversation_id=conv.get('conversation_id', conv.get('id', '')),
                title=conv.get('title', 'Untitled'),
                create_time=float(conv.get('create_time')) if conv.get('create_time') else None,
                update_time=float(conv.get('update_time')) if conv.get('update_time') else None,
                message_count=message_count
            )
            summaries.append(summary)
        
        # Sort by update_time descending (most recent first)
        summaries.sort(key=lambda x: x.update_time or 0, reverse=True)
        return summaries
        
    except Exception as e:
        print(f"[CONVERSATIONS] Error loading list: {e}")
        return []


def get_conversation_detail(conversation_id: str) -> Optional[ConversationDetail]:
    """
    Get full conversation detail by ID
    Parses the mapping structure to extract messages in order
    """
    if not os.path.exists(CONVERSATIONS_FILE):
        return None
    
    try:
        with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Find the conversation
        conv = None
        for c in data:
            if c.get('conversation_id', c.get('id', '')) == conversation_id:
                conv = c
                break
        
        if not conv:
            return None
        
        # Extract messages from mapping in order
        mapping = conv.get('mapping', {})
        messages = []
        
        # Build the message chain from the tree structure
        # Start from root and follow children
        def extract_messages_from_node(node_id: str, visited: set):
            if node_id in visited or node_id not in mapping:
                return
            visited.add(node_id)
            
            node = mapping[node_id]
            msg_data = node.get('message')
            
            if msg_data and msg_data.get('content'):
                content = msg_data.get('content', {})
                content_type = content.get('content_type', '')
                
                # Extract text content
                text_content = ''
                if content_type == 'text':
                    parts = content.get('parts', [])
                    text_content = '\n'.join(str(p) for p in parts if p)
                
                if text_content:
                    author = msg_data.get('author', {})
                    role = author.get('role', 'unknown')
                    
                    # Map role names
                    if role == 'assistant':
                        role = 'assistant'
                    elif role == 'user':
                        role = 'user'
                    elif role == 'system':
                        role = 'system'
                    
                    messages.append(ConversationMessage(
                        id=msg_data.get('id', node_id),
                        role=role,
                        content=text_content,
                        create_time=float(msg_data.get('create_time')) if msg_data.get('create_time') else None
                    ))
            
            # Follow children
            children = node.get('children', [])
            for child_id in children:
                extract_messages_from_node(child_id, visited)
        
        # Find root node (node with no parent or parent is None)
        root_ids = []
        for node_id, node in mapping.items():
            parent = node.get('parent')
            if parent is None or parent not in mapping:
                root_ids.append(node_id)
        
        visited = set()
        for root_id in root_ids:
            extract_messages_from_node(root_id, visited)
        
        # Sort messages by create_time if available
        messages.sort(key=lambda x: x.create_time or 0)
        
        return ConversationDetail(
            conversation_id=conversation_id,
            title=conv.get('title', 'Untitled'),
            messages=messages,
            create_time=float(conv.get('create_time')) if conv.get('create_time') else None,
            update_time=float(conv.get('update_time')) if conv.get('update_time') else None
        )
        
    except Exception as e:
        print(f"[CONVERSATIONS] Error loading detail: {e}")
        return None


def search_conversations(query: str, limit: int = 10000) -> list[ConversationSummary]:
    """
    Search conversations by title
    """
    all_convs = get_conversations_list()
    query_lower = query.lower()
    
    results = [
        conv for conv in all_convs 
        if query_lower in conv.title.lower()
    ]
    
    return results[:limit]
