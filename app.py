import streamlit as st
from langchain_core.messages import HumanMessage

from agent.graph import build_graph
from config import USERS
from rag.loader import chunk_documents, load_pdfs
from rag.vectorstore import build_index, load_index

st.set_page_config(page_title="Healthcare Memory RAG", page_icon="🏥", layout="wide")


# ── MEMORY SETUP ───────────────────────────────────────────────────────────
def setup_memory(framework_name, user_key=None, reset=False):
    """Initialise memory backend and return retrieve/persist functions."""

    if reset:
        if framework_name in st.session_state.memory_objects:
            del st.session_state.memory_objects[framework_name]

    if framework_name == "mem0":
        from memory.mem0_memory import add_memory, get_mem0, search_memory

        if "mem0" not in st.session_state.memory_objects:
            st.session_state.memory_objects["mem0"] = get_mem0(user_key)

        mem = st.session_state.memory_objects["mem0"]

        def retrieve(query, user_id):
            return search_memory(mem, query, user_id)

        def persist(user_msg, assistant_msg, user_id):
            add_memory(
                mem,
                [
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": assistant_msg},
                ],
                user_id,
            )

    elif framework_name == "langmem":
        from memory.langmem_intelligence import intelligent_persist
        from memory.langmem_memory import get_langmem_store

        if "langmem" not in st.session_state.memory_objects:
            st.session_state.memory_objects["langmem"] = get_langmem_store()
        store = st.session_state.memory_objects["langmem"]

        def retrieve(query, user_id):
            # Ensure this matches your langmem_memory.py function signature
            from memory.langmem_memory import search_memory

            return search_memory(store, query, user_id)

        def persist(user_msg, assistant_msg, user_id):
            # ── THIS IS THE KEY CHANGE ──
            # We now pass the user_id so extract_facts can find the USERS config
            intelligent_persist(store, user_msg, assistant_msg, user_id)

    return retrieve, persist


def get_all_memories_for_user(framework_name, user_id, memory_objects):
    """Get all stored memories for current user."""
    try:
        if framework_name == "mem0" and "mem0" in memory_objects:
            from memory.mem0_memory import get_all_memories

            return get_all_memories(memory_objects["mem0"], user_id)
        elif framework_name == "langmem" and "langmem" in memory_objects:
            from memory.langmem_memory import get_all_memories

            return get_all_memories(memory_objects["langmem"], user_id)
    except Exception as e:
        return [f"Error fetching memories: {e}"]
    return []


# ── SESSION STATE INIT ─────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "memory_objects" not in st.session_state:
    st.session_state.memory_objects = {}
if "graph" not in st.session_state:
    st.session_state.graph = None
if "current_framework" not in st.session_state:
    st.session_state.current_framework = None
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "processing" not in st.session_state:
    st.session_state.processing = False

# ── SIDEBAR ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏥 Healthcare RAG")
    st.divider()

    # Framework selector
    st.subheader("Memory Framework")
    framework = st.selectbox(
        "Select framework:", ["Mem0", "LangMem"], key="framework_select"
    )

    # User selector
    st.subheader("User")
    user_key = st.selectbox(
        "Select user:",
        list(USERS.keys()),
        format_func=lambda x: USERS[x]["name"],
        key="user_select",
    )
    user = USERS[user_key]

    st.info(f"""
    **{user["name"]}**
    {user["role"]}

    *Style:* {user["style"]}
    """)

    st.divider()

    # Data setup
    st.subheader("Setup")

    if st.button("📚 Build RAG Index", use_container_width=True):
        with st.spinner("Loading and indexing PDFs..."):
            docs = load_pdfs()
            if docs:
                chunks = chunk_documents(docs)
                build_index(chunks)
                st.success(f"Indexed {len(chunks)} chunks!")
            else:
                st.error("No PDFs found in ./data folder")

    index, texts, sources = load_index()
    if index is not None:
        st.success(f"✅ RAG index loaded ({index.ntotal} vectors)")
    else:
        st.warning("⚠️ No RAG index. Click Build above.")

    st.divider()

    # Memory viewer
    st.subheader("🧠 Memory Store")

    memories = get_all_memories_for_user(
        framework.lower(), user_key, st.session_state.memory_objects
    )

    if memories:
        for m in memories:
            st.markdown(f"- {m}")
    else:
        st.info("No memories stored yet.")

    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ── REBUILD GRAPH IF FRAMEWORK OR USER CHANGES ────────────────────────────
fw_key = framework.lower()
if (
    st.session_state.current_framework != fw_key
    or st.session_state.current_user != user_key
):
    # Clear all old memory objects
    st.session_state.memory_objects = {}

    # Setup new memory for the selected framework and user
    retrieve_fn, persist_fn = setup_memory(fw_key, user_key)

    # Rebuild the graph with fresh memory
    st.session_state.graph = build_graph(retrieve_fn, persist_fn)

    # Update current framework/user
    st.session_state.current_framework = fw_key
    st.session_state.current_user = user_key
    st.session_state.messages = []

# ── MAIN CHAT UI ───────────────────────────────────────────────────────────
st.title(f"🏥 Healthcare Assistant — {framework}")
st.caption(f"Logged in as: **{user['name']}** | {user['role']}")
st.divider()

# Display chat history
for msg in st.session_state.messages:
    role = "user" if msg["role"] == "user" else "assistant"
    with st.chat_message(role):
        st.markdown(msg["content"])

# 1. Capture the input
prompt = st.chat_input(
    "Ask a clinical question...",
    disabled=st.session_state.processing,  # This will now be TRUE when it reruns
)

if prompt:
    # 2. IMMEDIATELY lock and rerun to gray out the bar
    st.session_state.processing = True
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

# 3. If we are processing, run the graph logic
if st.session_state.processing and st.session_state.messages:
    # Get the last message
    last_user_msg = st.session_state.messages[-1]["content"]

    with st.chat_message("assistant"):
        config = {
            "configurable": {
                "thread_id": f"{user_key}_{fw_key}_thread",
                "user_id": user_key,
            }
        }
        placeholder = st.empty()
        full_response = ""

        with st.spinner("Processing and updating memory..."):
            for chunk in st.session_state.graph.stream(
                {
                    "messages": [HumanMessage(content=last_user_msg.strip())],
                    "user_id": user_key,
                    "user_name": user["name"],
                },
                config=config,
                stream_mode="messages",
            ):
                message_chunk, metadata = chunk

                if metadata.get("langgraph_node") == "agent":
                    # Extract the text content from the message
                    content = getattr(message_chunk, "content", "")

                # ── AGGRESSIVE GUARD: Block JSON and internal Memory Logs ──
                # If the chunk contains JSON brackets OR the LangMem internal tags, skip it.
                forbidden_markers = ["{", "}", '"facts"', '"decision"', "[LangMem]"]

                if any(marker in content for marker in forbidden_markers):
                    print(f"DEBUG: Blocked background logic leak: {content.strip()}")
                    continue

                    # If it's real text, add it to the UI
                if content:
                    full_response += content
                    placeholder.markdown(full_response + "▌")

        # 4. Finalize
        placeholder.markdown(full_response)
        st.toast("Clinical memory updated!", icon="🧠")

        # Save response and UNLOCK
        st.session_state.messages.append(
            {"role": "assistant", "content": full_response}
        )
        st.session_state.processing = False
        st.rerun()  # Refresh to clear the spinner and re-enable input
