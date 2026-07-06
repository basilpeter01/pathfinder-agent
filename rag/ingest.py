import os
import fitz  # PyMuPDF
from typing import List
from memory.lancedb import add_document_chunks_to_vault

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

def extract_text_from_file(file_path: str) -> str:
    """Extract text from PDF or TXT files."""
    if not os.path.exists(file_path):
        return ""
    
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        text = ""
        try:
            doc = fitz.open(file_path)
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
            return text
        except Exception as e:
            print(f"Error reading PDF {file_path}: {e}")
            return ""
    elif ext == ".txt" or ext == ".md":
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            print(f"Error reading text file {file_path}: {e}")
            return ""
    return ""

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks for RAG."""
    words = text.split()
    if not words:
        return []
    
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        chunk_str = " ".join(chunk_words)
        chunks.append(chunk_str)
        i += (chunk_size - overlap)
    return chunks

def process_and_ingest_file(file_path: str, filename: str) -> int:
    """Extract, chunk, and ingest document into ChromaDB Knowledge Vault."""
    raw_text = extract_text_from_file(file_path)
    if not raw_text.strip():
        return 0
    
    chunks = chunk_text(raw_text)
    count = add_document_chunks_to_vault(filename, chunks)
    return count
