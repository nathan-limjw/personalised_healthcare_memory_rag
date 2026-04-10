# agent/graph.py
import json
import os
import re
import sqlite3
from typing import Literal

import streamlit as st
from langchain_core.messages import SystemMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from typing import Literal

from agent.state import AgentState
from config import OLLAMA_BASE_URL, OLLAMA_MODEL, SQLITE_DB_PATH, USERS
from memory.langmem_memory import get_langmem_store
from memory.langmem_memory import search_memory as langmem_search
from memory.mem0_memory import get_mem0
from memory.mem0_memory import search_memory as mem0_search
from rag.vectorstore import load_index, retrieve

# Load RAG index once
rag_index, rag_texts, rag_sources = load_index()

os.environ["OLLAMA_USE_GPU"] = "0"

llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)


def format_memory_context(memories):
    """
    Unified memory formatter that aggressively removes JSON and metadata leaks.
    Returns clean, natural language context.
    """

    if not memories:
        return "No previous interactions."

    output = []

    if isinstance(memories, str):
        memories = [memories]  # Normalize to list

    for mem in memories:
        # Convert dict-like strings to dicts
        if isinstance(mem, str):
            try:
                parsed = json.loads(mem)
                mem = parsed
            except (json.JSONDecodeError, TypeError):
                pass

        # Case: dict with 'facts' key
        if isinstance(mem, dict):
            facts = mem.get("facts", [])
            if isinstance(facts, list):
                for f in facts:
                    if f and not any(
                        marker in f
                        for marker in ['"decision":', "mem_", "UPDATE", '"facts":']
                    ):
                        output.append(f"  • {f}")
            continue

        # Case: string
        if isinstance(mem, str):
            # Skip JSON-looking strings
            if mem.startswith("{") and mem.endswith("}"):
                continue
            # Skip short/noisy strings
            cleaned = mem.strip()
            if cleaned and len(cleaned) > 5:
                output.append(f"  • {cleaned}")

    if output:
        return "Previous conversation context:\n" + "\n".join(output)
    else:
        return "No previous interactions."


### FOR OTHER MODELS

# -------------------------------------------------------------------------------------
# def relevance_node(state: AgentState):
#     user_message = state["messages"][-1]
#     structured_llm = llm.with_structured_output(RelevanceOutput)
#     system_prompt = """
#         Classify the following user message on whether it is relevant

#         RELEVANT QUERIES:
#         - Medical or Clinical Questions
#         - The user's preferred response format or style (e.g. paragraphs, bullet points, less than XXX words)

#         Everything that does not fall under this category is considered irrelevant
#         """

#     response = structured_llm.invoke([SystemMessage(system_prompt), user_message])

#     return {"relevance": response.relevance, "reason": response.reason}
# -------------------------------------------------------------------------------------


def router(state: AgentState) -> Literal["agent", "non_medical"]:
    if state["relevance"] == "relevant":
        return "agent"
    else:
        return "non_medical"

<<<<<<< Updated upstream

=======
>>>>>>> Stashed changes
### FOR QWEN


# -------------------------------------------------------------------------------------
def relevance_node(state):
    user_message = state["messages"][-1].content

    prompt = f"""
Classify this as:
relevant OR irrelevant

Message: {user_message}
"""

    response = llm.invoke(prompt)
    text = response.content.lower()

    if "relevant" in text:
        return {"relevance": "relevant"}
    return {"relevance": "irrelevant"}


# -------------------------------------------------------------------------------------


def make_agent_node(memory_retrieve_fn, memory_persist_fn):
    """
    Factory that creates an agent node wired to a specific memory backend.
    memory_retrieve_fn: fn(query, user_id) -> list of memory strings
    memory_persist_fn:  fn(user_msg, assistant_msg, user_id) -> None
    """

    def sanitize(raw_text):
        """
        Aggressively remove JSON structures and metadata from an LLM response,
        returning clean, human-readable text only.
        """
        if not raw_text:
            return ""

        try:
            # Try parsing as JSON first
            parsed = json.loads(raw_text)
            output_lines = []

            # Handle dict with 'facts'
            if isinstance(parsed, dict):
                facts = parsed.get("facts", [])
                if isinstance(facts, list):
                    for f in facts:
                        if f and not any(
                            marker in f for marker in ['"decision":', "mem_", "UPDATE"]
                        ):
                            output_lines.append(f.strip())
            # Handle list of strings
            elif isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, str):
                        output_lines.append(item.strip())
            else:
                # Fallback: treat as string
                output_lines.append(str(parsed).strip())

            # Join lines cleanly
            clean_text = "\n".join(output_lines)
            clean_text = re.sub(r"\n\s*\n", "\n", clean_text).strip()
            return clean_text if clean_text else raw_text

        except json.JSONDecodeError:
            # Not JSON, fallback to aggressive regex cleanup
            text = re.sub(r"\{.*?\}|\[.*?\]", "", raw_text, flags=re.DOTALL)
            # Remove common LangMem markers
            markers = [
                '"decision":',
                '"update_id":',
                '"facts":',
                "mem_",
                "UPDATE",
                "CREATE",
                "DELETE",
            ]
            for m in markers:
                text = text.replace(m, "")
            # Clean whitespace
            text = re.sub(r"\n\s*\n", "\n", text).strip()
            return text

    def agent_node(state: AgentState) -> dict:
        user_id = state["user_id"]
        user_name = state["user_name"]
        user_message = state["messages"][-1].content

        # ── 0. GET STATIC DEFAULTS ─────────────────────────────────
        user_profile = USERS.get(user_id, {})
        default_style = user_profile.get("style")

        # ── RETRIEVE MEMORIES ──────────────────────────────────────
        raw_memories = memory_retrieve_fn(user_message, user_id)

        # print(f"[DEBUG MEMORY] Query: {user_message}")
        # print(f"[DEBUG MEMORY] Retrieved memories: {raw_memories}")
        # print(
        #     f"[DEBUG MEMORY] Memory count: {len(raw_memories) if isinstance(raw_memories, list) else 'not a list'}"
        # )

        memory_context = format_memory_context(raw_memories)
        # print(f"[DEBUG MEMORY] Formatted context: {memory_context[:200]}")

        # ✨ Format memories uniformly regardless of source
        memory_context = format_memory_context(raw_memories)

        # ✨ Final sanitization before feeding to LLM
        memory_context = sanitize(memory_context)

        # ── RETRIEVE RAG CONTEXT ───────────────────────────────────
        rag_context = ""
        if rag_index is not None:
            chunks = retrieve(user_message, rag_index, rag_texts, rag_sources)
            # 🔒 HARD GATING
            if not chunks or len(chunks) == 0:
                return {
                    "messages": [
                        "I cannot find information on this in the available clinical guidelines."
                    ]
                }
            rag_context = "\n\n".join(f"[{c['source']}]\n{c['text']}" for c in chunks)
        else:
            rag_context = "No clinical manuals loaded yet."

        # ── BUILD THE ADAPTIVE SYSTEM PROMPT ────────────────────
        system_prompt = f"""You are a clinical assistant for healthcare professionals.

## USER CONTEXT
- Name: {user_name}
- Role: {user_profile.get("role", "Unknown")}
- CRITICAL STYLE REQUIREMENT - OVERRIDE ALL OTHER FORMATTING: {default_style}

## WHAT YOU REMEMBER ABOUT {user_name.upper()}
{memory_context}

**CRITICAL**: The memory section above is for your context only. Never output JSON structures, field names like "facts:", "decision:", "update_id:", "mem_", or any technical metadata to the user. Always speak in natural, professional language.

## AUTHORIZED CLINICAL GUIDELINES
{rag_context}

## STRICT OPERATIONAL RULES (MANDATORY — NO EXCEPTIONS)

### Information Boundaries
- You MUST ONLY use information from the AUTHORIZED CLINICAL GUIDELINES above
- You MUST NOT use prior training knowledge, general medical knowledge, or external sources

- If the answer is NOT directly supported by the guidelines:
  → Respond EXACTLY: "I cannot find information on this in the available clinical guidelines."

- If guidelines are partially relevant but incomplete:
  → State what you found and cite the source
  → Clearly state what information is missing
  → Do NOT fill gaps with general knowledge

### Citation Requirements
- Each sentence containing clinical information MUST include its own citation
- Do NOT group multiple claims under a single citation
- If a sentence has no citation → it MUST NOT be included

When citing guidelines, ALWAYS include:
1. Guideline name (e.g., "Singapore Hypertension Guidelines")
2. Year if known (e.g., "2020")
3. Specific section if applicable

Example: "According to Singapore Hypertension Guidelines (2020), 
Section 4.2 on Blood Pressure Targets...

- DO NOT use placeholder text like "Document Name" or "Section" - use the real source from the context above
- If you cannot cite it from the guidelines above, DO NOT state it

### Communication Style
- Adapt your tone and formatting to {user_name}'s preferences as noted in memory
- Maintain professional clinical accuracy while matching their preferred style
- Balance personalization with precision
- NEVER expose internal JSON, memory IDs, or system metadata in your response

## SAFETY IMPERATIVE
Patient safety depends on accuracy. Fabricating medical information, drug names, dosages, recommendations, or citations is STRICTLY PROHIBITED. When uncertain, acknowledge limitations rather than guess.

## SELF-CHECK BEFORE RESPONDING
✓ Is every claim grounded in the AUTHORIZED CLINICAL GUIDELINES?
✓ Does every clinical statement have a valid, specific citation (not a placeholder)?
✓ Have I removed all JSON/technical metadata from my response?
✓ If any check fails → REFUSE to answer that portion
✓ Does my response format match {user_name}'s style: "{default_style}"? Also format nicely and present answer in a clear manner.

"""

        messages_for_llm = [SystemMessage(content=system_prompt)] + state["messages"]

        # ── RESPOND ────────────────────────────────────────────────
        response = llm.invoke(messages_for_llm)

        # ✨ Sanitize before persisting and returning
        clean_response_content = sanitize(response.content)

        # Persist memory safely
        try:
            memory_persist_fn(
                user_msg=user_message,
                assistant_msg=clean_response_content,
                user_id=user_id,
            )
        except Exception as e:
            print(f"Memory Sync Error: {e}")

        # Return sanitized response to UI
        return {"messages": [clean_response_content]}

    return agent_node


def non_medical_node(state: AgentState):
    user_id = state["user_id"]
    user_name = state["user_name"]
    user_message = state["messages"][-1].content

    # Get user profile for style
    user_profile = USERS.get(user_id, {})
    default_style = user_profile.get("style", "")
    role = user_profile.get("role", "healthcare professional")

    # Get the memory retrieval function based on framework
    framework = st.session_state.get("framework", "langmem").lower()

    if framework == "langmem":
        store = get_langmem_store()
        memories = langmem_search(store, user_message, user_id, limit=5)
    else:  # mem0
        mem0_instance = get_mem0(user_id)
        memories = mem0_search(mem0_instance, user_message, user_id, limit=5)

    # Format memory context
    memory_context = (
        "\n".join([f"- {m}" for m in memories])
        if memories
        else "No prior clinical discussions"
    )

    # Build contextual prompt
    prompt = f"""You are a clinical assistant speaking to {user_name}, a {role}.

What you remember about this user:
{memory_context}

Current question: "{user_message}"

This question is not clinical/medical. Respond warmly but redirect:
1. If memories show recent clinical topics, acknowledge them naturally
2. Politely explain you can only help with clinical questions from guidelines
3. Offer to help with any clinical topics from memory
4. **IMPORTANT**: If memory shows NO prior clinical topics, you MUST say you don't know what they're referring to. Do NOT guess or make assumptions.

Style: {default_style}

Keep response natural and brief."""

    response = llm.invoke(prompt)
    content = response.content.strip().strip('"').strip("'")

    if not content:
        content = "I can only assist with clinical and medical questions based on the provided guidelines."

    return {"messages": [content]}


def build_graph(memory_retrieve_fn, memory_persist_fn):
    """Build LangGraph agent with given memory functions."""

    # 1. Create a LOCAL connection inside the function
    # This ensures each graph instance has its own clean DB handle
    local_conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(local_conn)

    # 2. Get the node from your factory
    agent_node = make_agent_node(memory_retrieve_fn, memory_persist_fn)

    # 3. Build as usual
    builder = StateGraph(AgentState)
    builder.add_node("relevance", relevance_node)
    builder.add_node("non_medical", non_medical_node)
    builder.add_node("agent", agent_node)

    builder.add_edge(START, "relevance")
    builder.add_conditional_edges(
        "relevance",
        router,
        {
            "agent": "agent",
            "non_medical": "non_medical",
        },
    )
    builder.add_edge("agent", END)
    builder.add_edge("non_medical", END)

    # 4. Compile with the local checkpointer
    return builder.compile(checkpointer=checkpointer)
