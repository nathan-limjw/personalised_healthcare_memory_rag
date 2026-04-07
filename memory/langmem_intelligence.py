import json
import re

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

from config import OLLAMA_BASE_URL, OLLAMA_MODEL, USERS

# ── LLM for extraction + reconciliation ───────────────────────
extractor_llm = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.1,  # Low temp for high consistency
)

# ── HEALTHCARE EXTRACTION TEMPLATE ────────────────────────────
HEALTHCARE_EXTRACTION_TEMPLATE = """
You are a memory extraction assistant for a healthcare AI agent.
Extract medically and professionally relevant facts about the healthcare professional.

### BASELINE USER PROFILE (Starting Point):
{user_context}

INSTRUCTION: Use the above as a starting assumption, but PRIORITIZE extracting 
any deviations. If this user asks for a different style, focus, or role than 
their profile suggests, extract that as an 'Updated Preference'.

Extract ONLY facts from these categories:
1. Professional role and specialty (e.g. cardiologist, researcher)
2. Communication preferences (e.g. wants 3-paragraph answers, bullet points)
3. Clinical focus areas (e.g. hypertension, drug interactions)
4. Workflow preferences (e.g. always cite guidelines)
5. Institutional context (e.g. works at SGH)

DO NOT extract small talk, greetings, or irrelevant filler.

Input:
User: {user_msg}
Assistant: {assistant_msg}

Return ONLY a JSON object: {{"facts": ["fact1", "fact2"]}}
If nothing relevant is found, return: {{"facts": []}}
NO explanations, NO markdown, NO extra text.
"""

# ── RECONCILIATION PROMPT ──────────────────────────────────────
RECONCILIATION_PROMPT = """
You are a memory reconciliation assistant. 

### CRITICAL RULE:
If the NEW fact is a Communication Preference (like '3-paragraph' or 'Longer answers') 
and the EXISTING memory is also a Communication Preference (like 'Concise' or 'BLUF'), 
the NEW fact MUST replace the old one. 

- DECISION: "UPDATE"
- updated_fact: [The NEW preference only]

Existing memories:
{existing_memories}

New fact: {new_fact}

Return ONLY a valid JSON object with NO extra text before or after.
NO explanations, NO markdown backticks, NO conversational text.
Valid format: {{"decision": "UPDATE", "update_id": "mem_123", "updated_fact": "New Fact"}}
Or: {{"decision": "ADD"}}
Or: {{"decision": "NOOP"}}
"""


def clean_json_response(raw_text):
    """
    Aggressively extract JSON from LLM response, removing any text artifacts.
    This prevents LangMem's internal JSON from leaking into the UI.
    """
    # Remove markdown code blocks
    cleaned = re.sub(r"```(?:json)?", "", raw_text)
    cleaned = re.sub(r"```", "", cleaned)
    cleaned = cleaned.strip()

    # Find the actual JSON object
    start = cleaned.find("{")
    if start == -1:
        return None

    # Count braces to find matching closing brace
    brace_count = 0
    end = start

    for i in range(start, len(cleaned)):
        if cleaned[i] == "{":
            brace_count += 1
        elif cleaned[i] == "}":
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break

    if end > start:
        json_str = cleaned[start:end]
        # Validate it's actually valid JSON
        try:
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError:
            return None

    return None


def extract_facts(user_msg, assistant_msg, user_id):
    """Extracts facts using the Healthcare-Specific prompt and User context."""
    user_data = USERS.get(user_id, {})
    user_context = (
        f"- Role: {user_data.get('role')}\n"
        f"- Initial Focus: {user_data.get('focus')}\n"
        f"- Initial Style: {user_data.get('style')}"
    )

    prompt = (
        "SYSTEM: Output ONLY raw JSON. No conversational text. No markdown.\n"
        + HEALTHCARE_EXTRACTION_TEMPLATE.format(
            user_context=user_context,
            user_msg=user_msg,
            assistant_msg=assistant_msg[:400],
        )
    )

    try:
        result = extractor_llm.invoke([HumanMessage(content=prompt)])
        raw = result.content.strip()

        # ✨ Clean the response to extract only JSON
        json_str = clean_json_response(raw)

        if not json_str:
            print("[LangMem] No valid JSON in extraction response")
            print(f"[DEBUG] Raw response was: {raw[:200]}")  # Add this debug line
            return []

        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(
                f"Error in new_retrieved_facts: {e}"
            )  # This might be your error message!
            print(f"[DEBUG] Failed to parse: {json_str[:200]}")
            return []

        facts = [f.strip() for f in parsed.get("facts", []) if f.strip()]

        # ✨ Filter out any facts that contain JSON metadata
        clean_facts = []
        for fact in facts:
            # Skip if the fact contains LangMem metadata
            if any(
                marker in fact
                for marker in ['"decision"', '"update_id"', "mem_", '"facts"']
            ):
                continue
            clean_facts.append(fact)

        return clean_facts

    except json.JSONDecodeError as e:
        print(f"[LangMem] JSON parsing failed: {e}")
        return []
    except Exception as e:
        print(f"[LangMem] Extraction failed: {e}")
        return []


def reconcile_fact(new_fact, existing_memories, store, user_id):
    """Decides whether to create a new row or update an existing SQL row."""
    if not existing_memories:
        return ("ADD", None)

    # 1. Prepare the memories for the prompt
    existing_str = "\n".join(
        [f"ID: {m['key']} | Fact: {m['fact']}" for m in existing_memories]
    )

    prompt = RECONCILIATION_PROMPT.format(
        new_fact=new_fact, existing_memories=existing_str
    )

    try:
        # 2. Invoke the LLM
        result = extractor_llm.invoke([HumanMessage(content=prompt)])
        raw = result.content.strip()

        # ✨ 3. Aggressive JSON Extraction with Artifact Filtering
        json_str = clean_json_response(raw)

        if not json_str:
            print("[LangMem] No valid JSON in reconciliation response")
            return ("ADD", None)

        # ✨ Additional safety: Check if the raw response leaked into main output
        # This shouldn't happen, but let's be defensive
        if len(raw) > 500:  # Suspiciously long for a simple decision JSON
            print(
                f"[LangMem Warning] Reconciliation response too long: {len(raw)} chars"
            )

        parsed = json.loads(json_str)

        # 4. Extract Decision
        decision = parsed.get("decision", "ADD")

        # 5. Execute SQL Update if necessary
        if decision == "UPDATE":
            from memory.langmem_memory import update_memory

            update_id = parsed.get("update_id")
            updated_fact = parsed.get("updated_fact", new_fact)

            if update_id:
                update_memory(store, update_id, updated_fact)
                print(f"[LangMem] ✓ Updated {update_id}")
                return ("UPDATE", update_id)  # ← Return tuple with ID
            else:
                print("[LangMem] Warning: UPDATE decision but no update_id")
                return ("ADD", None)

        return (decision, None)  # Returns ("ADD", None) or ("NOOP", None)

    except json.JSONDecodeError as e:
        print(f"[LangMem] JSON decode error in reconciliation: {e}")
        return ("ADD", None)
    except Exception as e:
        print(f"[LangMem] Reconciliation error: {e}")
        return ("ADD", None)


def intelligent_persist(store, user_msg, assistant_msg, user_id):
    """The main entry point for the App to save memories via LangMem."""
    from memory.langmem_memory import add_memory, search_memory_with_keys

    # Step 1: Extract facts using Healthcare Logic
    facts = extract_facts(user_msg, assistant_msg, user_id)

    if not facts:
        return  # ✨ Silent return - no noise

    # Step 2: Get existing memories ONCE (not per fact)
    existing = search_memory_with_keys(store, "", user_id, limit=10)

    # Track which memories we've already updated in this batch
    updated_ids = set()

    # Step 3: Reconcile against SQLite database
    for fact in facts:
        # ✨ Enhanced sanitization
        # Skip if too long or contains JSON artifacts
        if len(fact) > 250:
            continue

        if any(
            marker in fact
            for marker in ["{", '"decision"', '"update_id"', "mem_", '"facts":']
        ):
            print(f"[LangMem] Skipping fact with JSON artifacts: {fact[:50]}...")
            continue

        # Filter out memories we've already updated in this iteration
        available_existing = [m for m in existing if m["key"] not in updated_ids]

        decision, updated_id = reconcile_fact(fact, available_existing, store, user_id)

        if decision == "ADD":
            add_memory(store, fact, user_id)
            print(f"[LangMem] ✓ Added: '{fact[:60]}...'")
        elif decision == "UPDATE":
            # Track that we updated this memory so we don't update it again
            if updated_id:
                updated_ids.add(updated_id)
            print("[LangMem] ✓ Updated existing memory")
        # NOOP: do nothing
