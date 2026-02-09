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

if getattr(sys, 'frozen', False):
    # Running as packaged executable
    PERSONAL_INFO_DIR = os.path.join(
        os.path.expanduser("~"),
        "AppData", "Local", "AURORA-Local-Agent",
        "personal_info", "data"
    )
    DATA_DIR = os.path.join(
        os.path.expanduser("~"),
        "AppData", "Local", "AURORA-Local-Agent"
    )
else:
    # Running in development
    PERSONAL_INFO_DIR = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "personal_info", "data"
    )
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

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


# ==================== Internal Helpers ====================

def _count_messages(conv: dict) -> int:
    """Count meaningful text messages in a conversation object."""
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
                return ConversationDetail(
                    conversation_id=conversation_id,
                    title=conv.get('title', 'Untitled'),
                    messages=_extract_messages(conv),
                    create_time=float(conv['create_time']) if conv.get('create_time') else None,
                    update_time=float(conv['update_time']) if conv.get('update_time') else None,
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


def save_engine_conversation(conversation_id: str, title: str, messages: List[dict]) -> bool:
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
                    # If switching from mapping→messages, drop the mapping key
                    if "mapping" in old and messages:
                        del old["mapping"]
                    conv_data = old
                except Exception:
                    pass

            existing["title"] = title
            existing["update_time"] = now
            existing["message_count"] = len(messages)
            existing["dirty"] = True
        else:
            conv_data["create_time"] = now
            conv_data["origin"] = "engine"
            index["conversations"].insert(0, {
                "id": conversation_id,
                "title": title,
                "create_time": now,
                "update_time": now,
                "message_count": len(messages),
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

        return ConversationDetail(
            conversation_id=conversation_id,
            title=conv.get('title', 'Untitled'),
            messages=_extract_messages(conv),
            create_time=float(conv['create_time']) if conv.get('create_time') else None,
            update_time=float(conv['update_time']) if conv.get('update_time') else None,
        )

    except Exception as e:
        print(f"[CONVERSATIONS] Legacy detail load error: {e}", flush=True)
        return None
