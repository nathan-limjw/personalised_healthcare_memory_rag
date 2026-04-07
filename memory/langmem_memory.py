# memory/langmem_memory.py
# Custom persistent memory store using plain SQLite
# Bypasses SqliteStore which has macOS compatibility issues

import sqlite3
import uuid

from config import LANGMEM_DB_PATH


# ── Setup database ─────────────────────────────────────────────
def _get_conn():
    conn = sqlite3.connect(LANGMEM_DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            key TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            fact TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


# Module-level connection — stays open for app lifetime
_conn = _get_conn()


def get_langmem_store():
    """Returns the connection — acts as our store."""
    return _conn


def add_memory(store, fact, user_id):
    """Store a unique fact for a user."""
    # Check if this exact fact already exists for this user to avoid UI clutter
    cursor = store.execute(
        "SELECT 1 FROM memories WHERE user_id = ? AND fact = ?", (user_id, fact)
    )
    if cursor.fetchone():
        return None  # Skip duplicates

    key = f"mem_{uuid.uuid4().hex[:8]}"
    store.execute(
        "INSERT INTO memories (key, user_id, fact) VALUES (?, ?, ?)",
        (key, user_id, fact),
    )
    store.commit()
    return key


def search_memory(store, query, user_id, limit=5):
    """
    Retrieve memories for this user.
    No semantic search — returns most recent facts.
    LLM uses all of them as context.
    """
    cursor = store.execute(
        """SELECT fact FROM memories
           WHERE user_id = ?
           ORDER BY created_at DESC
           LIMIT ?""",
        (user_id, limit),
    )
    return [row[0] for row in cursor.fetchall()]


def search_memory_with_keys(store, query, user_id, limit=5):
    """Returns key + fact for reconciliation."""
    cursor = store.execute(
        """SELECT key, fact FROM memories
           WHERE user_id = ?
           ORDER BY created_at DESC
           LIMIT ?""",
        (user_id, limit),
    )
    return [{"key": row[0], "fact": row[1]} for row in cursor.fetchall()]


def update_memory(store, key, new_fact):
    """Update an existing memory by key."""
    store.execute("UPDATE memories SET fact = ? WHERE key = ?", (new_fact, key))
    store.commit()


def get_all_memories(store, user_id):
    """Get all memories for a user."""
    cursor = store.execute(
        """SELECT fact FROM memories
           WHERE user_id = ?
           ORDER BY created_at DESC""",
        (user_id,),
    )
    return [row[0] for row in cursor.fetchall()]


def delete_all_memories(store, user_id):
    """Wipe all memories for a user."""
    store.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
    store.commit()
