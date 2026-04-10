"""
Healthcare Memory RAG - Streamlit Application
A clinical assistant with RAG retrieval and intelligent memory systems
"""

import traceback
from typing import Callable, List, Tuple

import streamlit as st

from agent.graph import build_graph
from config import USERS
from memory.langmem_memory import get_langmem_store
from memory.mem0_memory import get_mem0
from rag.loader import chunk_documents, load_pdfs
from rag.vectorstore import build_index, load_index

# ═══════════════════════════════════════════════════════════════════════════
# PAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Healthcare Memory RAG",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ═══════════════════════════════════════════════════════════════════════════
# UI RESET HELPERS
# ═══════════════════════════════════════════════════════════════════════════


def reset_chat_ui():
    """Wipes the chat history and stops processing when configurations change."""
    st.session_state.messages = []
    st.session_state.processing = False
    st.session_state.graph = None


# ═══════════════════════════════════════════════════════════════════════════
# MEMORY FRAMEWORK SETUP
# ═══════════════════════════════════════════════════════════════════════════


def initialize_mem0(user_key: str):
    """Initialize Mem0 memory backend."""
    from memory.mem0_memory import add_memory, search_memory

    mem = get_mem0(user_key)

    def retrieve(query: str, user_id: str) -> List[str]:
        return search_memory(mem, query, user_id)

    def persist(user_msg: str, assistant_msg: str, user_id: str):
        add_memory(
            mem,
            [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": assistant_msg},
            ],
            user_id,
        )

    return mem, retrieve, persist


def initialize_langmem(user_key: str):
    """Initialize LangMem memory backend."""
    from memory.langmem_intelligence import intelligent_persist
    from memory.langmem_memory import search_memory

    store = get_langmem_store()

    def retrieve(query: str, user_id: str) -> List[str]:
        return search_memory(store, query, user_id)

    def persist(user_msg: str, assistant_msg: str, user_id: str):
        intelligent_persist(store, user_msg, assistant_msg, user_id)

    return store, retrieve, persist


def setup_memory(framework: str, user_key: str) -> Tuple[Callable, Callable]:
    """
    Setup memory backend and return retrieve/persist functions.

    Args:
        framework: "mem0" or "langmem"
        user_key: User identifier

    Returns:
        Tuple of (retrieve_fn, persist_fn)
    """
    framework = framework.lower()

    # Check if already initialized
    if framework in st.session_state.memory_objects:
        # Reconstruct functions from existing memory object
        if framework == "mem0":
            from memory.mem0_memory import add_memory, search_memory

            mem = st.session_state.memory_objects["mem0"]

            def retrieve(query: str, user_id: str) -> List[str]:
                return search_memory(mem, query, user_id)

            def persist(user_msg: str, assistant_msg: str, user_id: str):
                add_memory(
                    mem,
                    [
                        {"role": "user", "content": user_msg},
                        {"role": "assistant", "content": assistant_msg},
                    ],
                    user_id,
                )

            return retrieve, persist

        elif framework == "langmem":
            from memory.langmem_intelligence import intelligent_persist
            from memory.langmem_memory import search_memory

            store = st.session_state.memory_objects["langmem"]

            def retrieve(query: str, user_id: str) -> List[str]:
                return search_memory(store, query, user_id)

            def persist(user_msg: str, assistant_msg: str, user_id: str):
                intelligent_persist(store, user_msg, assistant_msg, user_id)

            return retrieve, persist

    # Initialize new memory backend
    if framework == "mem0":
        mem, retrieve, persist = initialize_mem0(user_key)
        st.session_state.memory_objects["mem0"] = mem
    elif framework == "langmem":
        store, retrieve, persist = initialize_langmem(user_key)
        st.session_state.memory_objects["langmem"] = store
    else:
        raise ValueError(f"Unknown framework: {framework}")

    return retrieve, persist


def get_all_memories(framework: str, user_id: str) -> List[str]:
    """Retrieve all stored memories for a user."""
    framework = framework.lower()

    try:
        if framework == "mem0" and "mem0" in st.session_state.memory_objects:
            from memory.mem0_memory import get_all_memories

            return get_all_memories(st.session_state.memory_objects["mem0"], user_id)

        elif framework == "langmem" and "langmem" in st.session_state.memory_objects:
            from memory.langmem_memory import get_all_memories

            return get_all_memories(st.session_state.memory_objects["langmem"], user_id)

    except Exception as e:
        st.error(f"Error fetching memories: {e}")
        return []

    return []


def clear_memory(framework: str, user_id: str):
    """Clear memory for a specific user in a framework."""
    framework = framework.lower()

    if framework == "langmem":
        from memory.langmem_memory import delete_all_memories, get_langmem_store

        store = get_langmem_store()
        delete_all_memories(store, user_id)
        print(f"[DEBUG] Cleared langmem SQLite for user {user_id}")

    elif framework == "mem0":
        from memory.mem0_memory import get_mem0

        mem0_instance = get_mem0()
        mem0_instance.delete_all(user_id=user_id)  # Mem0's built-in delete method
        print(f"[DEBUG] Cleared mem0 for user {user_id}")

    # Clear session state object
    if framework in st.session_state.memory_objects:
        del st.session_state.memory_objects[framework]

    print(f"[DEBUG] ✓ Memory cleared for framework: {framework}, user: {user_id}")


# ═══════════════════════════════════════════════════════════════════════════
# SESSION STATE INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════


def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        "messages": [],
        "memory_objects": {},
        "graph": None,
        "current_framework": None,
        "current_user": None,
        "processing": False,
        "rag_loaded": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# ═══════════════════════════════════════════════════════════════════════════
# RAG MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════


def build_rag_index() -> Tuple[bool, str]:
    """Build RAG index from PDFs."""
    try:
        docs = load_pdfs()
        if not docs:
            return False, "No PDFs found in ./data folder"

        chunks = chunk_documents(docs)
        build_index(chunks)
        st.session_state.rag_loaded = True
        return True, f"Successfully indexed {len(chunks)} chunks"

    except Exception as e:
        return False, f"Error building index: {str(e)}"


def check_rag_status() -> Tuple[bool, int]:
    """Check if RAG index is loaded."""
    try:
        index, texts, sources = load_index()
        if index is not None:
            return True, index.ntotal
        return False, 0
    except Exception:
        return False, 0


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR UI
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.title("🏥 Healthcare RAG")
    st.divider()

    # ─── Framework Selection ───────────────────────────────────────────────
    st.subheader("Memory Framework")
    framework = st.selectbox(
        "Select framework:",
        ["Mem0", "LangMem"],
        key="framework_select",
        on_change=reset_chat_ui,
        help="Choose the memory backend for storing clinical context",
    )

    # ─── User Selection ────────────────────────────────────────────────────
    st.subheader("User Profile")
    user_key = st.selectbox(
        "Select user:",
        list(USERS.keys()),
        format_func=lambda x: USERS[x]["name"],
        key="user_select",
        on_change=reset_chat_ui,
        help="Select which healthcare professional you are",
    )

    user = USERS[user_key]
    st.info(f"""
    **{user["name"]}**  
    {user["role"]}
    
    *Communication Style:* {user["style"]}
    """)

    st.divider()

    # ─── RAG Index Management ──────────────────────────────────────────────
    st.subheader("📚 RAG Index")

    if st.button("Build Index from PDFs", use_container_width=True):
        with st.spinner("Loading and indexing documents..."):
            success, message = build_rag_index()
            if success:
                st.success(message)
            else:
                st.error(message)

    # Check RAG status
    rag_loaded, vector_count = check_rag_status()
    if rag_loaded:
        st.success(f"✅ Index ready ({vector_count:,} vectors)")
    else:
        st.warning("⚠️ No index found. Build one above.")

    st.divider()

    # ─── Memory Viewer ─────────────────────────────────────────────────────
    st.subheader("🧠 Memory Store")

    with st.expander("View Stored Memories", expanded=False):
        memories = get_all_memories(framework.lower(), user_key)

        if memories:
            for i, mem in enumerate(memories, 1):
                st.markdown(f"{i}. {mem}")
        else:
            st.info("No memories stored yet.")

    # ─── Actions ───────────────────────────────────────────────────────────
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.success("Chat cleared!")
            print("[DEBUG] Cleared chat history")
            st.rerun()

    with col2:
        if st.button("♻️ Reset Memory", use_container_width=True):
            clear_memory(framework.lower(), user_key)  # Pass user_key!
            st.success(f"Memory cleared for {USERS[user_key]['name']}!")
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# GRAPH MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════


def should_rebuild_graph(framework: str, user_key: str) -> bool:
    """Check if graph needs rebuilding."""
    fw_key = framework.lower()
    return (
        st.session_state.graph is None
        or st.session_state.current_framework != fw_key
        or st.session_state.current_user != user_key
    )


def rebuild_graph(framework: str, user_key: str):
    """Rebuild the agent graph with current configuration."""
    fw_key = framework.lower()

    # Setup memory functions
    retrieve_fn, persist_fn = setup_memory(fw_key, user_key)

    # Build graph
    st.session_state.graph = build_graph(retrieve_fn, persist_fn)

    # Update current state
    st.session_state.current_framework = fw_key
    st.session_state.current_user = user_key


# Rebuild graph if needed
if should_rebuild_graph(framework, user_key):
    rebuild_graph(framework, user_key)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN CHAT INTERFACE
# ═══════════════════════════════════════════════════════════════════════════

st.title(f"🏥 Healthcare Assistant — {framework}")
st.caption(f"Logged in as: **{user['name']}** ({user['role']})")
st.divider()

# ─── Display Chat History ──────────────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ─── Chat Input ────────────────────────────────────────────────────────────

prompt = st.chat_input(
    "Ask a clinical question...",
    disabled=st.session_state.processing,
)

if prompt:
    # Add user message and lock UI
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.processing = True
    st.rerun()


# ─── Process Pending Message ───────────────────────────────────────────────

if st.session_state.processing and st.session_state.messages:
    # Get the last user message
    last_user_msg = st.session_state.messages[-1]["content"]

    # Configuration for the graph
    config = {
        "configurable": {
            "thread_id": f"{user_key}_{framework.lower()}_thread",
            "user_id": user_key,
        }
    }

    # Display assistant response
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""

        try:
            with st.spinner("🤖 Thinking..."):
                # Stream response from graph
                for chunk in st.session_state.graph.stream(
                    {
                        "messages": [last_user_msg],
                        "user_id": user_key,
                        "user_name": USERS[user_key]["name"],
                    },
                    config,
                ):
                    # Parse LangGraph chunk structure
                    # print(f"[DEBUG] Received chunk with nodes: {list(chunk.keys())}")

                    for node_name, node_output in chunk.items():
                        print(f"[DEBUG] Processing node: {node_name}")

                        if node_name in ["agent", "non_medical"]:
                            # Extract content from various possible structures
                            content = ""

                            # print(f"[DEBUG] Raw node_output type: {type(node_output)}")
                            # print(f"[DEBUG] Raw node_output: {node_output}")

                            # Handle dict with 'messages' key (your actual structure)
                            if (
                                isinstance(node_output, dict)
                                and "messages" in node_output
                            ):
                                messages = node_output["messages"]
                                content = (
                                    messages[-1]
                                    if isinstance(messages, list)
                                    else messages
                                )
                                # print(
                                #     f"[DEBUG] Found messages key, type: {type(messages)}, value: {messages}"
                                # )
                                # Messages could be a list or a single item
                                if isinstance(messages, list):
                                    # Join all messages or take the last one
                                    content = messages[-1] if messages else ""
                                    # print(f"[DEBUG] Extracted from list: {content}")
                                else:
                                    content = messages
                                    # print(f"[DEBUG] Extracted direct: {content}")
                            # Handle message objects with content attribute
                            elif hasattr(node_output, "content"):
                                content = node_output.content
                                # print(f"[DEBUG] Extracted from .content: {content}")
                            # Handle dict with 'content' key
                            elif (
                                isinstance(node_output, dict)
                                and "content" in node_output
                            ):
                                content = node_output["content"]
                                # print(f"[DEBUG] Extracted from ['content']: {content}")
                            # Handle raw strings
                            elif isinstance(node_output, str):
                                content = node_output
                                # print(f"[DEBUG] Direct string: {content}")
                            else:
                                # Fallback: convert to string
                                content = str(node_output)
                                # print(f"[DEBUG] Fallback str(): {content}")

                            # Debug: Log what we're receiving
                            # print(
                            #     f"[DEBUG] Final extracted content type: {type(content)}"
                            # )
                            # print(f"[DEBUG] Final extracted content: {content}")

                            # Filter out internal JSON/logging artifacts
                            # Only block content that looks like raw JSON memory dumps
                            is_memory_log = isinstance(content, str) and (
                                content.strip().startswith("[LangMem]")
                                or content.strip().startswith("[Mem0]")
                                or (
                                    content.strip().startswith("{")
                                    and '"facts"' in content
                                )
                                or (
                                    content.strip().startswith("{")
                                    and '"decision"' in content
                                )
                            )

                            if is_memory_log:
                                # Skip internal memory processing logs
                                # print("[DEBUG] FILTERED as memory log")
                                continue

                            # Append valid content
                            if content and isinstance(content, str) and content.strip():
                                # print(f"[DEBUG] ADDING to response: {content[:100]}")
                                full_response += content
                                placeholder.markdown(full_response + "▌")
                            else:
                                print("[DEBUG] SKIPPED - empty or not string")

            # Finalize display
            placeholder.markdown(full_response)

            # Persist conversation to memory
            retrieve_fn, persist_fn = setup_memory(framework.lower(), user_key)
            persist_fn(last_user_msg, full_response, user_key)

            # Show success notification
            st.toast("✅ Memory updated", icon="🧠")

            # Save assistant response
            st.session_state.messages.append(
                {"role": "assistant", "content": full_response}
            )

        except Exception as e:
            # Display error to user (keep visible, don't auto-hide)
            st.error("❌ **Error processing request**")
            st.error(f"**Error:** {str(e)}")

            with st.expander("Full Stack Trace", expanded=True):
                st.code(traceback.format_exc())

            # DON'T remove the user message - keep it for debugging
            # We want to see what caused the error

            st.warning(
                "⚠️ Check the error above. You can retry by sending a new message."
            )

            # Mark that we had an error
            error_occurred = True

        else:
            # No error occurred
            error_occurred = False

        finally:
            # Always unlock the UI
            st.session_state.processing = False
            # Only rerun if successful (no error)
            if not error_occurred:
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════

st.divider()
st.caption(
    "💡 This assistant uses RAG + intelligent memory to provide clinical insights"
)
