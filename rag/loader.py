# rag/loader.py
import os

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import DATA_DIR


def load_pdfs():
    documents = []

    for pdf_file in os.listdir(DATA_DIR):
        if pdf_file.endswith(".pdf"):
            path = os.path.join(DATA_DIR, pdf_file)
            print(f"Loading: {pdf_file}")

            loader = PyMuPDFLoader(path)
            docs = loader.load()  # returns per-page documents

            for doc in docs:
                documents.append(
                    {
                        "source": pdf_file,
                        "page": doc.metadata.get("page"),
                        "content": doc.page_content,
                    }
                )

    print(f"Loaded {len(documents)} pages")
    return documents


def chunk_documents(documents):
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)

    chunks = []
    for doc in documents:
        splits = splitter.split_text(doc["content"])
        for split in splits:
            chunks.append({"text": split, "source": doc["source"], "page": doc["page"]})

    print(f"Created {len(chunks)} chunks")
    return chunks
