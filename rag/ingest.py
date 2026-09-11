import os
import fitz  # PyMuPDF
from typing import List
from memory.lancedb import add_document_chunks_to_vault
from services.logger import log_event

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

def extract_text_from_file(file_path: str) -> str:
    """Extract text from PDF, TXT, MD, or other text files."""
    if not os.path.exists(file_path):
        log_event("ERROR", "RAG", f"File not found at path: {file_path}")
        return ""
    
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        text = ""
        try:
            doc = fitz.open(file_path)
            for page in doc:
                page_text = page.get_text()
                if page_text:
                    text += page_text + "\n"
            doc.close()
            return text
        except Exception as e:
            log_event("ERROR", "RAG", f"Error reading PDF '{os.path.basename(file_path)}' | error: {e}")
            return ""
    else:
        # For .md, .txt, or any non-PDF extension, try reading as UTF-8 text file
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            log_event("ERROR", "RAG", f"Error reading text file '{os.path.basename(file_path)}' | error: {e}")
            return ""

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks for RAG."""
    words = text.split()
    if not words:
        return []
    
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        chunk_str = " ".join(chunk_words).strip()
        if chunk_str:
            chunks.append(chunk_str)
        if len(chunk_words) < chunk_size:
            break
        i += max(1, chunk_size - overlap)
    return chunks

def process_and_ingest_file(file_path: str, filename: str) -> int:
    """Extract, chunk, and ingest document into Knowledge Vault."""
    raw_text = extract_text_from_file(file_path)
    if not raw_text or not raw_text.strip():
        log_event("WARNING", "RAG", f"Extracted empty text from '{filename}'")
        return 0
    
    chunks = chunk_text(raw_text)
    log_event("INFO", "RAG", f"Extracted {len(chunks)} chunks from '{filename}'. Adding to vault...")
    count = add_document_chunks_to_vault(filename, chunks)
    return count

