# --- Ollama Configuration ---

# Base URL for the Ollama server
# The client classes will append the correct endpoint (e.g., /api/generate, /api/embeddings)
OLLAMA_API_URL = "http://localhost:11434"

# Model name used for summary generation
SUMMARY_GENERATOR_MODEL = "gemma3:12b"

# Model name used for generating vector embeddings for RAG
EMBEDDING_MODEL = "granite-embedding:278m"

# --- RAG Indexing Configuration ---
RAG_CHUNK_SIZE = 500      # Size of text chunks in characters
RAG_CHUNK_OVERLAP = 100   # Number of characters to overlap between chunks
