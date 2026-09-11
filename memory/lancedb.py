import os
import time
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
import hashlib
from typing import List, Dict, Any
from services.logger import log_event

# We use LanceDB + FastEmbed as the zero-server embedded vector engine.
try:
    import lancedb
    from fastembed import TextEmbedding
    _HAS_LANCE = True
except ImportError:
    _HAS_LANCE = False

LANCEDB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "lancedb")
os.makedirs(LANCEDB_DIR, exist_ok=True)

TABLE_NAME = "knowledge_vault"

class FallbackEmbedder:
    """Deterministic 384-dimensional semantic n-gram/hash embedding fallback when FastEmbed model download is unavailable."""
    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, texts: List[str]) -> List[List[float]]:
        results = []
        for text in texts:
            vec = [0.0] * self.dim
            words = text.lower().split()
            for i, word in enumerate(words):
                h = int(hashlib.md5(word.encode("utf-8", errors="ignore")).hexdigest(), 16)
                idx = h % self.dim
                vec[idx] += 1.0
                if i < len(words) - 1:
                    bigram = f"{word}_{words[i+1]}"
                    bh = int(hashlib.md5(bigram.encode("utf-8", errors="ignore")).hexdigest(), 16)
                    vec[bh % self.dim] += 1.5
            norm = sum(x * x for x in vec) ** 0.5
            if norm > 0:
                vec = [x / norm for x in vec]
            results.append(vec)
        return results

_embed_model_instance = None
_embed_model_tried = False
_db_instance = None

def get_embed_model():
    global _embed_model_instance, _embed_model_tried
    if _embed_model_instance is not None:
        return _embed_model_instance
    
    if _HAS_LANCE and not _embed_model_tried:
        _embed_model_tried = True
        try:
            log_event("INFO", "LANCEDB", "Initializing FastEmbed model: BAAI/bge-small-en-v1.5...")
            _embed_model_instance = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            log_event("INFO", "LANCEDB", "FastEmbed model initialized successfully (ONNX)")
            return _embed_model_instance
        except Exception as e:
            log_event("WARNING", "LANCEDB", f"FastEmbed initialization warning: {e}. Using FallbackEmbedder.")
    
    if _embed_model_instance is None:
        _embed_model_instance = FallbackEmbedder(dim=384)
    return _embed_model_instance

def get_lancedb_connection():
    global _db_instance
    if _db_instance is not None:
        return _db_instance
    if not _HAS_LANCE:
        return None
    try:
        _db_instance = lancedb.connect(LANCEDB_DIR)
        return _db_instance
    except Exception as e:
        print(f"[LanceDB] Connect error: {e}")
        return None

def get_vault_table():
    """Get the LanceDB table if it exists, else return None."""
    db = get_lancedb_connection()
    if db is None:
        return None
    try:
        return db.open_table(TABLE_NAME)
    except Exception:
        return None

def get_row_count_safe(table) -> int:
    """Safe helper to count rows across LanceDB versions."""
    if table is None:
        return 0
    try:
        return table.count_rows()
    except Exception:
        return len(table)

def add_document_chunks_to_vault(filename: str, chunks: List[str]) -> int:
    """Store text chunks into LanceDB vector store with ONNX embeddings and metadata."""
    if not chunks:
        print(f"[Knowledge Vault] No chunks provided for {filename}.")
        return 0
    
    db = get_lancedb_connection()
    if db is None:
        print("[Knowledge Vault] LanceDB connection unavailable.")
        return 0
    
    embedder = get_embed_model()
    try:
        vectors = list(embedder.embed(chunks))
        data = []
        for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
            chunk_id = hashlib.md5(f"{filename}_{idx}_{chunk[:20]}".encode("utf-8", errors="ignore")).hexdigest()
            data.append({
                "id": chunk_id,
                "vector": [float(x) for x in vec],
                "text": chunk,
                "source": filename,
                "chunk_index": idx
            })
            
        table = get_vault_table()
        if table is not None:
            try:
                table.delete(f"source = '{filename}'")
            except Exception as e:
                print(f"Prior chunk cleanup info: {e}")
            table.add(data)
        else:
            try:
                table = db.create_table(TABLE_NAME, data=data)
            except Exception as e_create:
                log_event("INFO", "LANCEDB", f"Table already initialized ({e_create}), appending chunks...")
                table = db.open_table(TABLE_NAME)
                table.add(data)
            
        log_event("INFO", "LANCEDB", f"Successfully indexed {len(data)} chunks for '{filename}'")
        return len(data)
    except Exception as e:
        log_event("WARNING", "LANCEDB", f"Direct table add failed ({e}), attempting open_table fallback...")
        try:
            tbl = db.open_table(TABLE_NAME)
            tbl.add(data)
            log_event("INFO", "LANCEDB", f"Successfully added {len(data)} chunks via open_table fallback")
            return len(data)
        except Exception as e2:
            log_event("ERROR", "LANCEDB", f"Table addition failed | error: {e2}")
        return 0

def query_vault(query_text: str, n_results: int = 3) -> List[Dict[str, Any]]:
    """Retrieve top relevant chunks from LanceDB for a given query."""
    table = get_vault_table()
    if table is None or get_row_count_safe(table) == 0:
        log_event("INFO", "LANCEDB", "Knowledge Vault is empty or table not found (0 chunks)")
        return []
    
    embedder = get_embed_model()
    try:
        t0 = time.time()
        query_vec = list(embedder.embed([query_text]))[0]
        query_vec = [float(x) for x in query_vec]
        
        actual_k = min(n_results, get_row_count_safe(table))
        try:
            results = table.search(query_vec).metric("cosine").limit(actual_k).to_list()
        except Exception:
            results = table.search(query_vec).limit(actual_k).to_list()
        
        extracted_chunks = []
        for r in results:
            extracted_chunks.append({
                "text": r.get("text", ""),
                "source": r.get("source", "Unknown PDF")
            })
        dur_ms = int((time.time() - t0) * 1000)
        log_event("INFO", "LANCEDB", f"Vector query returned {len(extracted_chunks)} chunks ({dur_ms}ms) for: \"{query_text[:35]}...\"")
        return extracted_chunks
    except Exception as e:
        log_event("ERROR", "LANCEDB", f"Vector search failed | error: {e}")
        return []

def list_vault_documents() -> List[str]:
    """List unique source files stored in vault."""
    table = get_vault_table()
    if table is None or get_row_count_safe(table) == 0:
        return []
    
    try:
        rows = table.search().select(["source"]).limit(10000).to_list()
        sources = set(row.get("source") for row in rows if row.get("source"))
        return sorted(list(sources))
    except Exception:
        try:
            arrow_tbl = table.to_arrow()
            sources = set(arrow_tbl["source"].to_pylist())
            return sorted(list(sources))
        except Exception as e2:
            print(f"Error listing documents from LanceDB: {e2}")
            return []
