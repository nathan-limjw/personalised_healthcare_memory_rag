# rag/vectorstore.py
import json
import os

import faiss
import numpy as np
from langchain_ollama import OllamaEmbeddings

from config import EMBEDDING_MODEL, OLLAMA_BASE_URL, RAG_INDEX_DIR


def get_embedder():
    return OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)


def build_index(chunks):
    """Embed chunks and build FAISS index."""
    os.makedirs(RAG_INDEX_DIR, exist_ok=True)

    embedder = get_embedder()
    texts = [c["text"] for c in chunks]
    sources = [c["source"] for c in chunks]

    print("Embedding chunks — this may take a few minutes...")
    embeddings = embedder.embed_documents(texts)
    embeddings_np = np.array(embeddings).astype("float32")

    # Normalise for cosine similarity
    faiss.normalize_L2(embeddings_np)

    dim = embeddings_np.shape[1]
    index = faiss.IndexFlatIP(dim)  # Inner product on normalised = cosine
    index.add(embeddings_np)

    # Save index
    faiss.write_index(index, os.path.join(RAG_INDEX_DIR, "index.faiss"))

    # Save metadata
    with open(os.path.join(RAG_INDEX_DIR, "metadata.json"), "w") as f:
        json.dump({"texts": texts, "sources": sources}, f)

    print(f"Index built with {len(texts)} vectors")
    return index, texts, sources


def load_index():
    """Load existing FAISS index from disk."""
    index_path = os.path.join(RAG_INDEX_DIR, "index.faiss")
    meta_path = os.path.join(RAG_INDEX_DIR, "metadata.json")

    if not os.path.exists(index_path):
        return None, None, None

    index = faiss.read_index(index_path)
    with open(meta_path, "r") as f:
        meta = json.load(f)

    return index, meta["texts"], meta["sources"]


def retrieve(query, index, texts, sources, top_k=4):
    """Retrieve top-k relevant chunks for a query."""
    embedder = get_embedder()
    query_vec = np.array(embedder.embed_query(query)).astype("float32").reshape(1, -1)

    faiss.normalize_L2(query_vec)
    distances, indices = index.search(query_vec, top_k)

    results = []
    for i, idx in enumerate(indices[0]):
        if idx != -1:  # FAISS returns -1 for empty slots
            results.append(
                {
                    "text": texts[idx],
                    "source": sources[idx],
                    "score": float(distances[0][i]),
                }
            )

    return results
