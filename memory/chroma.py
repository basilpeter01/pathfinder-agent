# Backward compatibility forwarding layer:
# Swapped from ChromaDB to LanceDB + FastEmbed for zero-server security and faster embedded ONNX vector search.
from memory.lancedb import (
    add_document_chunks_to_vault,
    query_vault,
    list_vault_documents,
    LANCEDB_DIR as CHROMA_DIR
)
