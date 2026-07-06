import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
import hashlib
from typing import List, Dict, Any

# We use LanceDB + FastEmbed as the zero-server embedded vector engine.
try:
    import lancedb
    from fastembed import TextEmbedding
    _HAS_LANCE = True
except ImportError:
    _HAS_LANCE = False

LANCEDB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "lancedb")
os.makedirs(LANCEDB_DIR, exist_ok=True)

# Initialize LanceDB connection and FastEmbed model
if _HAS_LANCE:
    try:
        db = lancedb.connect(LANCEDB_DIR)
        embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    except Exception as e:
        print(f"LanceDB / FastEmbed init warning: {e}")
        db = None
        embed_model = None
else:
    db = None
    embed_model = None

TABLE_NAME = "knowledge_vault"

def get_vault_table():
    """Get the LanceDB table if it exists, else return None."""
    if db is None:
        return None
    try:
        if TABLE_NAME in db.list_tables():
            return db.open_table(TABLE_NAME)
    except Exception as e:
        print(f"Error opening table {TABLE_NAME}: {e}")
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
    if not chunks or not _HAS_LANCE or db is None or embed_model is None:
        return 0
    
    try:
        # Generate ONNX vector embeddings for chunks
        vectors = list(embed_model.embed(chunks))
        
        data = []
        for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
            chunk_id = hashlib.md5(f"{filename}_{idx}_{chunk[:20]}".encode()).hexdigest()
            data.append({
                "id": chunk_id,
                "vector": list(vec),
                "text": chunk,
                "source": filename,
                "chunk_index": idx
            })
            
        table = get_vault_table()
        if table is not None:
            # Clean up prior version of this file if re-ingesting
            try:
                table.delete(f"source = '{filename}'")
            except Exception as e:
                print(f"Prior chunk cleanup info: {e}")
            table.add(data)
        else:
            db.create_table(TABLE_NAME, data=data)
            
        return len(data)
    except Exception as e:
        print(f"Error adding chunks to LanceDB vault: {e}")
        return 0

def query_vault(query_text: str, n_results: int = 3) -> List[Dict[str, Any]]:
    """Retrieve top relevant chunks from LanceDB for a given query."""
    table = get_vault_table()
    if table is None or get_row_count_safe(table) == 0 or embed_model is None:
        return []
    
    try:
        # Embed the query
        query_vec = list(embed_model.embed([query_text]))[0]
        
        actual_k = min(n_results, get_row_count_safe(table))
        results = table.search(list(query_vec)).limit(actual_k).to_list()
        
        extracted_chunks = []
        for r in results:
            extracted_chunks.append({
                "text": r.get("text", ""),
                "source": r.get("source", "Unknown PDF")
            })
        return extracted_chunks
    except Exception as e:
        print(f"Error querying LanceDB vault: {e}")
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
