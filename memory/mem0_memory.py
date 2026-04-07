# memory/mem0_memory.py
from mem0 import Memory

from config import EMBEDDING_MODEL, MEM0_STORE_DIR, OLLAMA_BASE_URL, OLLAMA_MODEL, USERS

HEALTHCARE_EXTRACTION_PROMPT = """Extract professional healthcare facts ONLY. Return valid JSON with a "facts" key.

Categories: role, specialty, communication preferences, clinical focus, workflow preferences, institutional context.

Skip: greetings, small talk, non-professional information.

Format: {{"facts": ["fact1", "fact2"]}} or {{"facts": []}}

NO markdown, NO explanations, NO extra text. Only the JSON object.

Examples:
"Hi there" → {{"facts": []}}
"I'm a cardiologist at SGH" → {{"facts": ["Is a cardiologist", "Works at SGH"]}}
"I prefer bullet points" → {{"facts": ["Prefers bullet point answers"]}}
"Always cite guidelines" → {{"facts": ["Requires guideline citations"]}}
"""


def get_mem0(user_key=None):
    """
    Factory function that creates a customized Mem0 instance.
    If user_key is provided, it customizes the extraction prompt based on config.py.
    """

    # Start with your base prompt
    extraction_prompt = HEALTHCARE_EXTRACTION_PROMPT

    # Dynamically inject User-Specific context if available
    if user_key and user_key in USERS:
        user_data = USERS[user_key]

        # This "Header" tells the LLM how to prioritize extraction for this specific person
        custom_context_header = f"""
        ### BASELINE USER PROFILE (Starting Point):
        - Role: {user_data.get("role")}
        - Initial Focus: {user_data.get("focus")}
        - Initial Style: {user_data.get("style")}

        INSTRUCTION: Use the above as a starting assumption, but **prioritize extracting 
        any deviations**. If this specific user asks for more detail than their profile 
        suggests, or focuses on a new topic, extract that as a 'Updated Preference' 
        so the system can adapt to their unique personality.
        ---
        """

        extraction_prompt = custom_context_header + HEALTHCARE_EXTRACTION_PROMPT

    config = {
        "vector_store": {
            "provider": "faiss",
            "config": {
                "collection_name": "healthcare_memories",
                "path": MEM0_STORE_DIR,
                "distance_strategy": "cosine",
                "embedding_model_dims": 768,
            },
        },
        "llm": {
            "provider": "ollama",
            "config": {
                "model": OLLAMA_MODEL,
                "ollama_base_url": OLLAMA_BASE_URL,
                "temperature": 0.0,  # Lower temperature for more consistent JSON
                "max_tokens": 1000,
            },
        },
        "embedder": {
            "provider": "ollama",
            "config": {"model": EMBEDDING_MODEL, "ollama_base_url": OLLAMA_BASE_URL},
        },
        "custom_fact_extraction_prompt": extraction_prompt,
        "version": "v1.1",
    }
    return Memory.from_config(config)


def add_memory(memory, messages, user_id):
    """Add conversation to memory. Mem0 handles extraction and deduplication internally."""
    try:
        result = memory.add(messages, user_id=user_id)

        # Log what Mem0 did
        if result and isinstance(result, dict) and "results" in result:
            for action in result["results"]:
                event = action.get("event")
                memory_text = action.get("memory", "")
                memory_id = action.get("id", "")

                if event == "ADD":
                    # Truncate long memories for display
                    display_text = (
                        memory_text[:60] + "..."
                        if len(memory_text) > 60
                        else memory_text
                    )
                    print(f"[Mem0] ✓ Added: '{display_text}'")
                elif event == "UPDATE":
                    display_text = (
                        memory_text[:60] + "..."
                        if len(memory_text) > 60
                        else memory_text
                    )
                    # Extract short ID (last 8 chars)
                    short_id = memory_id[-8:] if len(memory_id) > 8 else memory_id
                    print(f"[Mem0] ✓ Updated mem_{short_id}")
                    print(f"[Mem0]   → '{display_text}'")
                elif event == "DELETE":
                    short_id = memory_id[-8:] if len(memory_id) > 8 else memory_id
                    print(f"[Mem0] ✗ Deleted mem_{short_id}")

        return result
    except Exception as e:
        # Only log critical errors that prevent memory from working
        print(f"[Mem0] Critical Memory Error: {e}")
        return None


def search_memory(memory, query, user_id, limit=5):
    """Search memories for a user."""
    results = memory.search(query, user_id=user_id, limit=limit)
    return [r["memory"] for r in results.get("results", [])]


def get_all_memories(memory, user_id):
    """Get all memories for a user."""
    results = memory.get_all(user_id=user_id)
    return [r["memory"] for r in results.get("results", [])]
