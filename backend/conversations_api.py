"""
Conversations API - Lazy loading for large conversation files
Only loads titles initially, full content loaded on demand
"""
import os
import json
import time
import shutil
from typing import Optional, List
from pydantic import BaseModel

# Path to conversations.json (original, read-only)
PERSONAL_INFO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 
    "personal_info", "data"
)
CONVERSATIONS_FILE = os.path.join(PERSONAL_INFO_DIR, "conversations.json")

# Path to external_engine_conversation.json (new, read-write)
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ENGINE_CONVERSATIONS_FILE = os.path.join(DATA_DIR, "external_engine_conversation.json")


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


# ==================== Engine Conversations (Read-Write) ====================

def init_engine_conversations():
    """
    Initialize external_engine_conversation.json
    If it doesn't exist, copy from conversations.json
    """
    if not os.path.exists(ENGINE_CONVERSATIONS_FILE):
        if os.path.exists(CONVERSATIONS_FILE):
            print(f"[CONVERSATIONS] Copying conversations.json to external_engine_conversation.json", flush=True)
            shutil.copy2(CONVERSATIONS_FILE, ENGINE_CONVERSATIONS_FILE)
        else:
            print(f"[CONVERSATIONS] Creating empty external_engine_conversation.json", flush=True)
            with open(ENGINE_CONVERSATIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f)
    return ENGINE_CONVERSATIONS_FILE


def reload_engine_conversations():
    """
    Reload engine conversations by copying from conversations.json
    """
    if os.path.exists(CONVERSATIONS_FILE):
        print(f"[CONVERSATIONS] Reloading: copying conversations.json to external_engine_conversation.json", flush=True)
        shutil.copy2(CONVERSATIONS_FILE, ENGINE_CONVERSATIONS_FILE)
        return True
    return False


def get_engine_conversations_list() -> list[ConversationSummary]:
    """
    Get list of engine conversations (from external_engine_conversation.json)
    """
    init_engine_conversations()
    
    try:
        with open(ENGINE_CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        summaries = []
        for conv in data:
            # Handle both old format (mapping) and new format (messages array)
            if 'mapping' in conv:
                mapping = conv.get('mapping', {})
                message_count = sum(1 for node in mapping.values() if node.get('message') is not None)
            else:
                message_count = len(conv.get('messages', []))
            
            summary = ConversationSummary(
                conversation_id=conv.get('conversation_id', conv.get('id', '')),
                title=conv.get('title', 'Untitled'),
                create_time=float(conv.get('create_time')) if conv.get('create_time') else None,
                update_time=float(conv.get('update_time')) if conv.get('update_time') else None,
                message_count=message_count
            )
            summaries.append(summary)
        
        summaries.sort(key=lambda x: x.update_time or 0, reverse=True)
        return summaries
        
    except Exception as e:
        print(f"[CONVERSATIONS] Error loading engine conversations list: {e}")
        return []


def get_engine_conversation_detail(conversation_id: str) -> Optional[ConversationDetail]:
    """
    Get conversation detail from engine conversations file
    """
    init_engine_conversations()
    
    try:
        with open(ENGINE_CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        conv = None
        for c in data:
            if c.get('conversation_id', c.get('id', '')) == conversation_id:
                conv = c
                break
        
        if not conv:
            return None
        
        messages = []
        
        # Handle new format (messages array)
        if 'messages' in conv and isinstance(conv['messages'], list):
            for msg in conv['messages']:
                messages.append(ConversationMessage(
                    id=msg.get('id', ''),
                    role=msg.get('role', 'user'),
                    content=msg.get('content', ''),
                    create_time=float(msg.get('create_time')) if msg.get('create_time') else None
                ))
        # Handle old format (mapping)
        elif 'mapping' in conv:
            mapping = conv.get('mapping', {})
            
            def extract_messages_from_node(node_id: str, visited: set):
                if node_id in visited or node_id not in mapping:
                    return
                visited.add(node_id)
                
                node = mapping[node_id]
                msg_data = node.get('message')
                
                if msg_data and msg_data.get('content'):
                    content = msg_data.get('content', {})
                    content_type = content.get('content_type', '')
                    
                    text_content = ''
                    if content_type == 'text':
                        parts = content.get('parts', [])
                        text_content = '\n'.join(str(p) for p in parts if p)
                    
                    if text_content:
                        author = msg_data.get('author', {})
                        role = author.get('role', 'unknown')
                        
                        messages.append(ConversationMessage(
                            id=msg_data.get('id', node_id),
                            role=role,
                            content=text_content,
                            create_time=float(msg_data.get('create_time')) if msg_data.get('create_time') else None
                        ))
                
                children = node.get('children', [])
                for child_id in children:
                    extract_messages_from_node(child_id, visited)
            
            root_ids = [nid for nid, node in mapping.items() if node.get('parent') is None or node.get('parent') not in mapping]
            visited = set()
            for root_id in root_ids:
                extract_messages_from_node(root_id, visited)
            
            messages.sort(key=lambda x: x.create_time or 0)
        
        return ConversationDetail(
            conversation_id=conversation_id,
            title=conv.get('title', 'Untitled'),
            messages=messages,
            create_time=float(conv.get('create_time')) if conv.get('create_time') else None,
            update_time=float(conv.get('update_time')) if conv.get('update_time') else None
        )
        
    except Exception as e:
        print(f"[CONVERSATIONS] Error loading engine conversation detail: {e}")
        return None


def save_engine_conversation(conversation_id: str, title: str, messages: List[dict]) -> bool:
    """
    Save or update a conversation in engine conversations file
    """
    init_engine_conversations()
    
    try:
        with open(ENGINE_CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Find existing conversation
        existing_idx = None
        for i, c in enumerate(data):
            if c.get('conversation_id', c.get('id', '')) == conversation_id:
                existing_idx = i
                break
        
        now = time.time()
        
        conv_data = {
            'conversation_id': conversation_id,
            'title': title,
            'messages': messages,
            'update_time': now
        }
        
        if existing_idx is not None:
            conv_data['create_time'] = data[existing_idx].get('create_time', now)
            data[existing_idx] = conv_data
        else:
            conv_data['create_time'] = now
            data.insert(0, conv_data)  # Add to beginning
        
        with open(ENGINE_CONVERSATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[CONVERSATIONS] Saved conversation: {conversation_id}", flush=True)
        return True
        
    except Exception as e:
        print(f"[CONVERSATIONS] Error saving conversation: {e}")
        return False


def update_conversation_title(conversation_id: str, new_title: str) -> bool:
    """
    Update only the title of a conversation
    """
    init_engine_conversations()
    
    try:
        with open(ENGINE_CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for conv in data:
            if conv.get('conversation_id', conv.get('id', '')) == conversation_id:
                conv['title'] = new_title
                conv['update_time'] = time.time()
                
                with open(ENGINE_CONVERSATIONS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                print(f"[CONVERSATIONS] Updated title: {conversation_id} -> {new_title}", flush=True)
                return True
        
        return False
        
    except Exception as e:
        print(f"[CONVERSATIONS] Error updating title: {e}")
        return False