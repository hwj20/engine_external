"""
Conversations API - Multi-file split architecture for large conversation files

After uploading an OpenAI conversations.json export, this module automatically
splits it into individual files for fast per-conversation access:

  conversations_split/
  ├── index.json                  # lightweight metadata index
  ├── conversations/
  │   └── conv_<id>.json          # individual conversation (original fields preserved)
  └── .sync/
      └── dirty.json              # IDs of locally-modified conversations
"""
import os
import sys
import json
import time
import shutil
import threading
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from pathlib import Path

logger = logging.getLogger(__name__)

# ==================== Path Configuration ====================

def get_app_data_dir() -> str:
    """Get platform-specific app data directory."""
    if getattr(sys, 'frozen', False):
        # Running as packaged executable
        home = os.path.expanduser("~")
        if sys.platform == "win32":
            return os.path.join(home, "AppData", "Local", "AURORA-Local-Agent")
        elif sys.platform == "darwin":
            return os.path.join(home, "Library", "Application Support", "AURORA-Local-Agent")
        else:  # linux and others
            return os.path.join(home, ".local", "share", "AURORA-Local-Agent")
    else:
        # Running in development
        return os.path.join(os.path.dirname(__file__), "data")

APP_DATA_DIR = get_app_data_dir()
PERSONAL_INFO_DIR = os.path.join(APP_DATA_DIR, "personal_info", "data")
DATA_DIR = APP_DATA_DIR

os.makedirs(PERSONAL_INFO_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Source file (uploaded OpenAI export)
CONVERSATIONS_FILE = os.path.join(PERSONAL_INFO_DIR, "conversations.json")

# Split architecture directories
SPLIT_DIR = os.path.join(DATA_DIR, "conversations_split")
SPLIT_INDEX_FILE = os.path.join(SPLIT_DIR, "index.json")
SPLIT_CONVS_DIR = os.path.join(SPLIT_DIR, "conversations")
SPLIT_SYNC_DIR = os.path.join(SPLIT_DIR, ".sync")
DIRTY_FILE = os.path.join(SPLIT_SYNC_DIR, "dirty.json")

# In-memory index cache (avoids re-reading index.json on every request)
_index_cache: Optional[Dict] = None
_index_lock = threading.Lock()


# ==================== Pydantic Models ====================

class ConversationSummary(BaseModel):
    """Summary of a conversation (for list view)"""
    conversation_id: str
    title: str
    create_time: Optional[float] = None
    update_time: Optional[float] = None
    message_count: int = 0


class ConversationMessage(BaseModel):
    """A single message in a conversation"""
    id: str
    role: str  # 'user', 'assistant', 'system', 'tool'
    content: str
    create_time: Optional[float] = None


class ConversationDetail(BaseModel):
    """Full conversation detail with messages"""
    conversation_id: str
    title: str
    messages: list[ConversationMessage]
    create_time: Optional[float] = None
    update_time: Optional[float] = None
    conversation_tree: Optional[Dict[str, Any]] = None
    active_path: Optional[List[str]] = None


# ==================== Internal Helpers ====================

def _count_messages(conv: dict) -> int:
    """Count meaningful text messages in a conversation object."""
    normalized_tree, normalized_active_path = _normalize_conversation_tree(conv)
    if isinstance(normalized_tree, dict):
        nodes = normalized_tree.get('nodes')
        if isinstance(nodes, dict) and isinstance(normalized_active_path, list) and normalized_active_path:
            count = 0
            for node_id in normalized_active_path:
                node = nodes.get(node_id)
                if not isinstance(node, dict):
                    continue
                if (node.get('content') or '').strip():
                    count += 1
            if count > 0:
                return count

    # OpenAI mapping format
    mapping = conv.get('mapping')
    if mapping and isinstance(mapping, dict):
        count = 0
        for node in mapping.values():
            msg = node.get('message')
            if msg and isinstance(msg, dict):
                content = msg.get('content')
                if content and content.get('content_type') == 'text':
                    parts = content.get('parts', [])
                    if any(p for p in parts if p):
                        count += 1
        return count
    # Simple messages array format
    if isinstance(conv.get('messages'), list):
        return len(conv['messages'])
    return 0


def _extract_messages(conv: dict) -> List[ConversationMessage]:
    """Extract ordered messages from a conversation (both OpenAI and simple formats)."""
    messages: List[ConversationMessage] = []

    # ── Preferred: normalized tree with active path (internal + OpenAI mapping) ──
    normalized_tree, normalized_active_path = _normalize_conversation_tree(conv)
    if isinstance(normalized_tree, dict):
        nodes = normalized_tree.get('nodes')
        if isinstance(nodes, dict) and isinstance(normalized_active_path, list):
            for node_id in normalized_active_path:
                node = nodes.get(node_id)
                if not isinstance(node, dict):
                    continue
                content = (node.get('content') or '').strip()
                if not content:
                    continue
                create_time = node.get('create_time')
                try:
                    create_time_val = float(create_time) if create_time is not None else None
                except Exception:
                    create_time_val = None
                messages.append(ConversationMessage(
                    id=node.get('id', node_id),
                    role=node.get('role', 'unknown'),
                    content=content,
                    create_time=create_time_val,
                ))

            if messages:
                return messages

    # ── Format 1: Simple messages array ──
    if isinstance(conv.get('messages'), list):
        for msg in conv['messages']:
            messages.append(ConversationMessage(
                id=msg.get('id', ''),
                role=msg.get('role', 'user'),
                content=msg.get('content', ''),
                create_time=float(msg['create_time']) if msg.get('create_time') else None,
            ))
        return messages

    # ── Format 2: OpenAI mapping tree ──
    mapping = conv.get('mapping')
    if not mapping or not isinstance(mapping, dict):
        return messages

    def _walk(node_id: str, visited: set):
        if node_id in visited or node_id not in mapping:
            return
        visited.add(node_id)

        node = mapping[node_id]
        msg_data = node.get('message')

        if msg_data and isinstance(msg_data, dict) and msg_data.get('content'):
            content = msg_data['content']
            if content.get('content_type') == 'text':
                parts = content.get('parts', [])
                text = '\n'.join(str(p) for p in parts if p)
                if text:
                    role = msg_data.get('author', {}).get('role', 'unknown')
                    messages.append(ConversationMessage(
                        id=msg_data.get('id', node_id),
                        role=role,
                        content=text,
                        create_time=float(msg_data['create_time']) if msg_data.get('create_time') else None,
                    ))

        for child_id in node.get('children', []):
            _walk(child_id, visited)

    # Find root nodes
    roots = [
        nid for nid, node in mapping.items()
        if node.get('parent') is None or node.get('parent') not in mapping
    ]
    visited: set = set()
    for root in roots:
        _walk(root, visited)

    messages.sort(key=lambda m: m.create_time or 0)
    return messages


def _normalize_conversation_tree(conv: dict) -> tuple[Optional[Dict[str, Any]], Optional[List[str]]]:
    """Normalize conversation into internal tree + active_path, supporting both internal and OpenAI mapping formats."""
    tree = conv.get('conversation_tree')
    active_path = conv.get('active_path')
    if isinstance(tree, dict) and isinstance(tree.get('nodes'), dict):
        if isinstance(active_path, list) and active_path:
            return tree, active_path
        fallback = tree.get('active_path')
        if isinstance(fallback, list) and fallback:
            return tree, fallback
        return tree, []

    mapping = conv.get('mapping')
    if not isinstance(mapping, dict) or not mapping:
        return None, None

    nodes: Dict[str, Dict[str, Any]] = {}
    fallback_path: List[str] = []

    def _extract_text(msg_data: dict) -> str:
        content = msg_data.get('content') if isinstance(msg_data, dict) else None
        if not isinstance(content, dict) or content.get('content_type') != 'text':
            return ''
        parts = content.get('parts', [])
        if not isinstance(parts, list):
            return ''
        text = '\n'.join(str(p) for p in parts if p)
        return text.strip()

    # Build tree nodes from mapping
    for node_id, node in mapping.items():
        if not isinstance(node, dict):
            continue
        msg_data = node.get('message')
        if not isinstance(msg_data, dict):
            continue
        text = _extract_text(msg_data)
        if not text:
            continue

        role = msg_data.get('author', {}).get('role', 'unknown')
        create_time = msg_data.get('create_time')
        try:
            create_time_val = float(create_time) if create_time is not None else None
        except Exception:
            create_time_val = None

        parent_id = node.get('parent')
        if parent_id not in mapping:
            parent_id = None

        children = node.get('children', [])
        if not isinstance(children, list):
            children = []

        nodes[node_id] = {
            'id': msg_data.get('id', node_id),
            'role': role,
            'content': text,
            'parent_id': parent_id,
            'children': [child_id for child_id in children if child_id in mapping],
            'create_time': create_time_val,
        }

    # Remove non-message parents from parent links by climbing to nearest message ancestor
    for node_id, node in list(nodes.items()):
        parent_id = node.get('parent_id')
        guard = set()
        while parent_id and parent_id not in nodes and parent_id in mapping and parent_id not in guard:
            guard.add(parent_id)
            parent_id = mapping[parent_id].get('parent')
        if parent_id not in nodes:
            parent_id = None
        node['parent_id'] = parent_id

    # Rebuild children from normalized parent links
    for node in nodes.values():
        node['children'] = []
    for node_id, node in nodes.items():
        parent_id = node.get('parent_id')
        if parent_id and parent_id in nodes:
            nodes[parent_id]['children'].append(node_id)

    # Build active path from current_node first
    current_node_id = conv.get('current_node')
    active_path: List[str] = []
    if isinstance(current_node_id, str) and current_node_id in mapping:
        cursor = current_node_id
        guard = set()
        temp_path = []
        while cursor and cursor in mapping and cursor not in guard:
            guard.add(cursor)
            if cursor in nodes:
                temp_path.append(cursor)
            cursor = mapping[cursor].get('parent')
        active_path = list(reversed(temp_path))

    # Fallback: pick the deepest latest leaf path
    if not active_path and nodes:
        roots = [nid for nid, n in nodes.items() if not n.get('parent_id')]
        visited = set()

        def _walk(node_id: str):
            if node_id in visited or node_id not in nodes:
                return
            visited.add(node_id)
            fallback_path.append(node_id)
            children = nodes[node_id].get('children', [])
            if children:
                # Prefer child with latest create_time
                children_sorted = sorted(
                    children,
                    key=lambda cid: (nodes.get(cid, {}).get('create_time') or 0),
                    reverse=True,
                )
                _walk(children_sorted[0])

        root_sorted = sorted(roots, key=lambda rid: (nodes.get(rid, {}).get('create_time') or 0))
        if root_sorted:
            _walk(root_sorted[0])
        active_path = fallback_path

    root_id = active_path[0] if active_path else None
    normalized_tree = {
        'version': '1.0',
        'root_id': root_id,
        'nodes': nodes,
    }
    return normalized_tree, active_path


def _find_conversations_json(base_dir: str) -> Optional[str]:
    """
    Locate conversations.json in *base_dir* or one level of subdirectories.
    OpenAI exports sometimes nest inside a folder.
    """
    direct = os.path.join(base_dir, "conversations.json")
    if os.path.exists(direct):
        return direct
    try:
        for item in os.listdir(base_dir):
            candidate = os.path.join(base_dir, item, "conversations.json")
            if os.path.isfile(candidate):
                return candidate
    except OSError:
        pass
    return None


# ==================== Index / Dirty helpers ====================

def _load_index() -> Optional[Dict]:
    """Return the in-memory index, loading from disk on first call."""
    global _index_cache

    with _index_lock:
        if _index_cache is not None:
            return _index_cache

    if not os.path.exists(SPLIT_INDEX_FILE):
        return None

    try:
        with open(SPLIT_INDEX_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        with _index_lock:
            _index_cache = data
        return data
    except Exception as e:
        logger.error(f"Error loading split index: {e}")
        return None


def _save_index(index_data: Dict):
    """Persist index to disk and refresh cache."""
    global _index_cache

    index_data["last_modified"] = datetime.now().isoformat()
    index_data["total_conversations"] = len(index_data.get("conversations", []))

    os.makedirs(os.path.dirname(SPLIT_INDEX_FILE), exist_ok=True)
    with open(SPLIT_INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    with _index_lock:
        _index_cache = index_data


def _invalidate_index_cache():
    global _index_cache
    with _index_lock:
        _index_cache = None


def _load_dirty() -> List[str]:
    try:
        with open(DIRTY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def _save_dirty(dirty_ids: List[str]):
    os.makedirs(SPLIT_SYNC_DIR, exist_ok=True)
    with open(DIRTY_FILE, 'w', encoding='utf-8') as f:
        json.dump(dirty_ids, f, ensure_ascii=False)


# ==================== Split Operation ====================

def is_split_available() -> bool:
    """Return True if the split directory has a valid index."""
    return os.path.exists(SPLIT_INDEX_FILE)


def split_conversations_file(source_path: str = None) -> dict:
    """
    Parse a conversations.json and split it into the multi-file architecture.

    This is the **core migration** function.  It is called automatically after
    a zip upload – no separate migrate script is needed.

    Args:
        source_path: path to conversations.json.  Falls back to the default
                     CONVERSATIONS_FILE location.

    Returns:
        ``{"total": N, "elapsed": seconds, "split_dir": path}``
    """
    global _index_cache

    source = source_path or CONVERSATIONS_FILE
    if not os.path.exists(source):
        raise FileNotFoundError(f"Source file not found: {source}")

    file_size = os.path.getsize(source)
    size_mb = file_size / (1024 * 1024)
    print(f"[SPLIT] Starting split of {source} ({size_mb:.1f} MB)", flush=True)
    logger.info(f"Splitting conversations: {source} ({size_mb:.1f} MB)")

    t0 = time.time()

    # Prepare directories (clear previous split if any)
    if os.path.exists(SPLIT_CONVS_DIR):
        shutil.rmtree(SPLIT_CONVS_DIR)
    os.makedirs(SPLIT_CONVS_DIR, exist_ok=True)
    os.makedirs(SPLIT_SYNC_DIR, exist_ok=True)

    # Load source file
    print("[SPLIT] Loading source file into memory …", flush=True)
    with open(source, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("conversations.json must be a top-level JSON array")

    total = len(data)
    print(f"[SPLIT] Parsed {total} conversations, writing individual files …", flush=True)

    index_entries: List[Dict[str, Any]] = []

    for i, conv in enumerate(data):
        conv_id = conv.get('conversation_id') or conv.get('id') or f'unknown_{i}'
        title = conv.get('title') or 'Untitled'
        create_time = float(conv['create_time']) if conv.get('create_time') else None
        update_time = float(conv['update_time']) if conv.get('update_time') else None
        message_count = _count_messages(conv)

        # Write individual file (no indent to save disk space)
        conv_file = os.path.join(SPLIT_CONVS_DIR, f"conv_{conv_id}.json")
        with open(conv_file, 'w', encoding='utf-8') as f:
            json.dump(conv, f, ensure_ascii=False)

        index_entries.append({
            "id": conv_id,
            "title": title,
            "create_time": create_time,
            "update_time": update_time,
            "message_count": message_count,
            "dirty": False,
            "origin": "openai",
        })

        if (i + 1) % 100 == 0 or (i + 1) == total:
            print(f"[SPLIT] Progress: {i + 1}/{total}", flush=True)

    # Free the huge list
    del data

    # Sort by update_time descending
    index_entries.sort(key=lambda e: e.get('update_time') or 0, reverse=True)

    index_data = {
        "version": "1.0",
        "last_modified": datetime.now().isoformat(),
        "total_conversations": len(index_entries),
        "conversations": index_entries,
    }

    with open(SPLIT_INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    # Initialize empty dirty list
    _save_dirty([])

    with _index_lock:
        _index_cache = index_data

    elapsed = round(time.time() - t0, 1)
    print(f"[SPLIT] Done! {total} conversations split in {elapsed}s", flush=True)
    logger.info(f"Split complete: {total} conversations in {elapsed}s")

    return {"total": total, "elapsed": elapsed, "split_dir": SPLIT_DIR}


# ==================== Public Read API ====================

def get_conversations_list() -> list[ConversationSummary]:
    """
    Get conversation summaries.

    Reads from the lightweight index.json when available,
    otherwise falls back to parsing the full conversations.json.
    """
    if is_split_available():
        index = _load_index()
        if index:
            return [
                ConversationSummary(
                    conversation_id=e["id"],
                    title=e.get("title", "Untitled"),
                    create_time=e.get("create_time"),
                    update_time=e.get("update_time"),
                    message_count=e.get("message_count", 0),
                )
                for e in index.get("conversations", [])
            ]

    # Legacy fallback — read entire file
    return _get_conversations_list_legacy()


def get_conversation_detail(conversation_id: str) -> Optional[ConversationDetail]:
    """
    Load a single conversation's full detail.

    Uses the split per-file when available; otherwise
    falls back to scanning the monolithic JSON.
    """
    if is_split_available():
        conv_file = os.path.join(SPLIT_CONVS_DIR, f"conv_{conversation_id}.json")
        if os.path.exists(conv_file):
            try:
                with open(conv_file, 'r', encoding='utf-8') as f:
                    conv = json.load(f)
                normalized_tree, normalized_active_path = _normalize_conversation_tree(conv)
                return ConversationDetail(
                    conversation_id=conversation_id,
                    title=conv.get('title', 'Untitled'),
                    messages=_extract_messages(conv),
                    create_time=float(conv['create_time']) if conv.get('create_time') else None,
                    update_time=float(conv['update_time']) if conv.get('update_time') else None,
                    conversation_tree=normalized_tree,
                    active_path=normalized_active_path,
                )
            except Exception as e:
                logger.error(f"Error loading split conversation {conversation_id}: {e}")

    # Legacy fallback
    return _get_conversation_detail_legacy(conversation_id)


def search_conversations(query: str, limit: int = 10000) -> list[ConversationSummary]:
    """Search conversations by title (case-insensitive substring match)."""
    all_convs = get_conversations_list()
    q = query.lower()
    return [c for c in all_convs if q in c.title.lower()][:limit]


# ==================== Public Write API (Engine Conversations) ====================
# These replace the old external_engine_conversation.json based functions.
# In the split architecture, "engine" and "original" conversations share the
# same storage; the *origin* field in the index tracks provenance.

def get_engine_conversations_list() -> list[ConversationSummary]:
    """Alias – both endpoints now read from the same split store."""
    return get_conversations_list()


def get_engine_conversation_detail(conversation_id: str) -> Optional[ConversationDetail]:
    """Alias – both endpoints now read from the same split store."""
    return get_conversation_detail(conversation_id)


def save_engine_conversation(
    conversation_id: str,
    title: str,
    messages: List[dict],
    conversation_tree: Optional[Dict[str, Any]] = None,
    active_path: Optional[List[str]] = None,
) -> bool:
    """Save or update a conversation (individual file + index)."""
    try:
        _ensure_split_dirs()

        now = time.time()

        # Build conversation payload
        conv_data: Dict[str, Any] = {
            "conversation_id": conversation_id,
            "title": title,
            "messages": messages,
            "update_time": now,
        }
        if conversation_tree is not None:
            conv_data["conversation_tree"] = conversation_tree
        if active_path is not None:
            conv_data["active_path"] = active_path

        # Load current index (or create empty)
        index = _load_index() or _empty_index()

        # Check for existing entry
        existing = None
        for entry in index["conversations"]:
            if entry["id"] == conversation_id:
                existing = entry
                break

        if existing:
            conv_data["create_time"] = existing.get("create_time", now)

            # Preserve original OpenAI fields — only overwrite title/messages/update_time
            conv_file = os.path.join(SPLIT_CONVS_DIR, f"conv_{conversation_id}.json")
            if os.path.exists(conv_file):
                try:
                    with open(conv_file, 'r', encoding='utf-8') as f:
                        old = json.load(f)
                    old["title"] = title
                    old["messages"] = messages
                    old["update_time"] = now
                    if conversation_tree is not None:
                        old["conversation_tree"] = conversation_tree
                    if active_path is not None:
                        old["active_path"] = active_path
                    conv_data = old
                except Exception:
                    pass

            message_count = len(messages)
            if isinstance(conversation_tree, dict) and isinstance(active_path, list):
                nodes = conversation_tree.get("nodes", {})
                if isinstance(nodes, dict):
                    message_count = sum(1 for node_id in active_path if node_id in nodes)

            existing["title"] = title
            existing["update_time"] = now
            existing["message_count"] = message_count
            existing["dirty"] = True
        else:
            conv_data["create_time"] = now
            conv_data["origin"] = "engine"

            message_count = len(messages)
            if isinstance(conversation_tree, dict) and isinstance(active_path, list):
                nodes = conversation_tree.get("nodes", {})
                if isinstance(nodes, dict):
                    message_count = sum(1 for node_id in active_path if node_id in nodes)

            index["conversations"].insert(0, {
                "id": conversation_id,
                "title": title,
                "create_time": now,
                "update_time": now,
                "message_count": message_count,
                "dirty": True,
                "origin": "engine",
            })

        # Write individual file
        conv_file = os.path.join(SPLIT_CONVS_DIR, f"conv_{conversation_id}.json")
        with open(conv_file, 'w', encoding='utf-8') as f:
            json.dump(conv_data, f, ensure_ascii=False, indent=2)

        # Mark dirty
        dirty = _load_dirty()
        if conversation_id not in dirty:
            dirty.append(conversation_id)
        _save_dirty(dirty)

        _save_index(index)
        print(f"[SPLIT] Saved conversation: {conversation_id}", flush=True)
        return True

    except Exception as e:
        logger.error(f"Error saving conversation: {e}")
        print(f"[SPLIT] Error saving conversation: {e}", flush=True)
        return False


def update_conversation_title(conversation_id: str, new_title: str) -> bool:
    """Update only the title of a conversation."""
    try:
        if not is_split_available():
            return False

        index = _load_index()
        if not index:
            return False

        found = False
        for entry in index["conversations"]:
            if entry["id"] == conversation_id:
                entry["title"] = new_title
                entry["update_time"] = time.time()
                found = True
                break

        if not found:
            return False

        # Also update the individual file
        conv_file = os.path.join(SPLIT_CONVS_DIR, f"conv_{conversation_id}.json")
        if os.path.exists(conv_file):
            try:
                with open(conv_file, 'r', encoding='utf-8') as f:
                    conv = json.load(f)
                conv["title"] = new_title
                conv["update_time"] = time.time()
                with open(conv_file, 'w', encoding='utf-8') as f:
                    json.dump(conv, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[SPLIT] Warning: could not update title in file: {e}", flush=True)

        _save_index(index)
        print(f"[SPLIT] Updated title: {conversation_id} → {new_title}", flush=True)
        return True

    except Exception as e:
        logger.error(f"Error updating title: {e}")
        return False


def delete_engine_conversation(conversation_id: str) -> bool:
    """Delete a conversation from the split architecture."""
    try:
        if not is_split_available():
            return False

        index = _load_index()
        if not index:
            return False

        original_len = len(index["conversations"])
        index["conversations"] = [
            e for e in index["conversations"]
            if e["id"] != conversation_id
        ]

        if len(index["conversations"]) == original_len:
            return False  # not found

        # Remove individual file
        conv_file = os.path.join(SPLIT_CONVS_DIR, f"conv_{conversation_id}.json")
        if os.path.exists(conv_file):
            os.remove(conv_file)

        # Remove from dirty list
        dirty = [d for d in _load_dirty() if d != conversation_id]
        _save_dirty(dirty)

        _save_index(index)
        print(f"[SPLIT] Deleted conversation: {conversation_id}", flush=True)
        return True

    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        return False


def reload_engine_conversations() -> bool:
    """
    Re-split from the source conversations.json.

    Clears the existing split directory and rebuilds from scratch.
    """
    source = _find_conversations_json(PERSONAL_INFO_DIR) or CONVERSATIONS_FILE
    if not os.path.exists(source):
        return False

    try:
        if os.path.exists(SPLIT_DIR):
            shutil.rmtree(SPLIT_DIR)
        _invalidate_index_cache()
        split_conversations_file(source)
        return True
    except Exception as e:
        logger.error(f"Error reloading (re-split): {e}")
        print(f"[SPLIT] Re-split failed: {e}", flush=True)
        return False


def init_engine_conversations():
    """
    Initialise the split architecture on startup.

    * If a split directory already exists → do nothing (fast path).
    * If conversations.json exists → split it.
    * Otherwise → create an empty split structure.
    """
    if is_split_available():
        print(f"[SPLIT] Split directory already exists ({SPLIT_DIR})", flush=True)
        return

    source = _find_conversations_json(PERSONAL_INFO_DIR)
    if source:
        print(f"[SPLIT] Found {source}, splitting …", flush=True)
        try:
            split_conversations_file(source)
            return
        except Exception as e:
            print(f"[SPLIT] Init split failed: {e}", flush=True)
            logger.error(f"Init split failed: {e}")

    # Create empty structure
    _ensure_split_dirs()
    _save_index(_empty_index())
    _save_dirty([])
    print("[SPLIT] Created empty split structure", flush=True)


# ==================== Private Utilities ====================

def _empty_index() -> Dict:
    return {
        "version": "1.0",
        "last_modified": datetime.now().isoformat(),
        "total_conversations": 0,
        "conversations": [],
    }


def _ensure_split_dirs():
    """Create split directory tree if it doesn't exist yet."""
    os.makedirs(SPLIT_CONVS_DIR, exist_ok=True)
    os.makedirs(SPLIT_SYNC_DIR, exist_ok=True)


# ==================== Legacy Fallback (monolithic JSON) ====================

def _get_conversations_list_legacy() -> list[ConversationSummary]:
    """Fallback: read entire conversations.json in one go."""
    if not os.path.exists(CONVERSATIONS_FILE):
        return []

    try:
        with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        summaries = []
        for conv in data:
            mapping = conv.get('mapping', {})
            message_count = sum(
                1 for n in mapping.values()
                if n.get('message') is not None
            )
            summaries.append(ConversationSummary(
                conversation_id=conv.get('conversation_id', conv.get('id', '')),
                title=conv.get('title', 'Untitled'),
                create_time=float(conv['create_time']) if conv.get('create_time') else None,
                update_time=float(conv['update_time']) if conv.get('update_time') else None,
                message_count=message_count,
            ))

        summaries.sort(key=lambda x: x.update_time or 0, reverse=True)
        return summaries

    except Exception as e:
        print(f"[CONVERSATIONS] Legacy load error: {e}", flush=True)
        return []


def _get_conversation_detail_legacy(conversation_id: str) -> Optional[ConversationDetail]:
    """Fallback: search inside monolithic conversations.json."""
    if not os.path.exists(CONVERSATIONS_FILE):
        return None

    try:
        with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        conv = None
        for c in data:
            if c.get('conversation_id', c.get('id', '')) == conversation_id:
                conv = c
                break

        if not conv:
            return None

        normalized_tree, normalized_active_path = _normalize_conversation_tree(conv)

        return ConversationDetail(
            conversation_id=conversation_id,
            title=conv.get('title', 'Untitled'),
            messages=_extract_messages(conv),
            create_time=float(conv['create_time']) if conv.get('create_time') else None,
            update_time=float(conv['update_time']) if conv.get('update_time') else None,
            conversation_tree=normalized_tree,
            active_path=normalized_active_path,
        )

    except Exception as e:
        print(f"[CONVERSATIONS] Legacy detail load error: {e}", flush=True)
        return None
