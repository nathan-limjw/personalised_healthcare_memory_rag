import os

# ════════════════════════════════
# CORE MODELS
# ════════════════════════════════

OLLAMA_BASE_URL = "http://localhost:11434"
# OLLAMA_MODEL = "llama3.2:3b"
# OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_MODEL = "qwen3.5:4b"
# OLLAMA_MODEL = "qwen3.5:9b"
EMBEDDING_MODEL = "nomic-embed-text"  # pull via: ollama pull nomic-embed-text

# ════════════════════════════════
# EVALUATION FILES
# ════════════════════════════════

EXCEL_PATH = "eval/gold_standard_test_cases.xlsx"
PERSISTENT_CSV = "data/evaluation_results/summary_of_results.csv"


# ════════════════════════════════
# STORAGE PATHS
# ════════════════════════════════

DATA_DIR = "./data/documents"
RAG_INDEX_DIR = "./data/rag_index"
MEMORY_DIR = "./data/memory_stores"
EVAL_DIR = "./data/evaluation_results"

MEM0_STORE_DIR = os.path.join(MEMORY_DIR, "mem0")
LANGMEM_DIR = os.path.join(MEMORY_DIR, "langmem")
SQLITE_DB_PATH = os.path.join(MEMORY_DIR, "checkpoints.db")

os.makedirs(LANGMEM_DIR, exist_ok=True)
os.makedirs(MEM0_STORE_DIR, exist_ok=True)
os.makedirs(EVAL_DIR, exist_ok=True)

LANGMEM_DB_PATH = os.path.join(LANGMEM_DIR, "langmem_store.db")

# 3 User Personas
USERS = {
    "dr_sarah": {
        "name": "Dr. Sarah",
        "role": "Consultant Cardiologist",
        "style": "Likes answers in bullet points and concise.",
    },
    "james": {
        "name": "James",
        "role": "Senior Clinical Pharmacist",
        "style": "Has a short attention span, answers have to be STRICTLY less than 100 words",
    },
    "priya": {
        "name": "Priya",
        "role": "Principal Clinical Researcher",
        "style": "Likes answers in paragraphs, more details and concepts that flow and connect with one another. NO BULLET POINTS at all",
    },
}


# Test queries per user across 4 sessions
TEST_SESSIONS = {
    "dr_sarah": [
        # Session 1
        [
            "Hi I'm Dr. Sarah, a cardiologist. What are the first-line drugs for hypertension?",
            "What are the contraindications for ACE inhibitors?",
        ],
        # Session 2
        [
            "What do you remember about me?",
            "My patient has both hypertension and diabetes, what should I prescribe?",
        ],
        # Session 3
        [
            "Actually I prefer you always give drug class first before specific drug names.",
            "What are the BP targets for diabetic patients?",
        ],
        # Session 4
        [
            "Based on what you know about me, what would be the best treatment approach for a hypertensive patient with CKD?"
        ],
    ],
    "james": [
        # Session 1
        [
            "Hi, I'm James, a pharmacist. Can you list all drug interactions for metformin?",
            "Which guideline covers this? Always cite your source.",
        ],
        # Session 2
        [
            "What do you remember about me?",
            "What are the adverse effects of SGLT-2 inhibitors? Cite the manual.",
        ],
        # Session 3
        [
            "I want you to always include the page reference when citing guidelines.",
            "What are the dosing guidelines for insulin in Type 2 DM?",
        ],
        # Session 4
        [
            "Based on my focus area, what interactions should I watch for in a patient on both antihypertensives and diabetes medication?"
        ],
    ],
    "priya": [
        # Session 1
        [
            "Hi I'm Priya, a clinical researcher. What is the evidence quality for metformin as first-line therapy?",
            "What studies support the use of SGLT-2 inhibitors?",
        ],
        # Session 2
        [
            "What do you remember about me?",
            "What does the data say about cardiovascular outcomes in hypertensive diabetic patients?",
        ],
        # Session 3
        [
            "I always want confidence intervals or NNT when discussing evidence.",
            "What is the comparative effectiveness of ACE inhibitors vs ARBs?",
        ],
        # Session 4
        [
            "Based on my research focus, what gaps exist in current hypertension guidelines for diabetic patients?"
        ],
    ],
}
