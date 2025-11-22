import os
from dotenv import load_dotenv

load_dotenv()

# Project root (1 level above /app)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Database (sync + async)
DATABASE_URL = os.getenv("DATABASE_URL","sqlite+aiosqlite:///./test.db")

FRONTEND_URL = os.getenv("FRONTEND_URL")

# Auth / JWT
SECRET_KEY = os.getenv("SECRET_KEY","super-secret-key-change-this")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES","1440"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT","https://your-azure-openai-endpoint/")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY","your-azure-openai-key")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv( "AZURE_OPENAI_EMBEDDING_DEPLOYMENT","text-embedding-ada-002")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_VERSION","2023-05-15")


# Azure AI Search
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT","https://your-azure-search-endpoint/")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY","your-azure-search-key")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX","your-azure-search-index")

# Azure Storage
AZURE_STORAGE_ACCOUNT = os.getenv("AZURE_STORAGE_ACCOUNT","your-azure-storage-account")
AZURE_STORAGE_KEY = os.getenv("AZURE_STORAGE_KEY","your-azure-storage-key")
AZURE_STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER","your-azure-storage-container")


# Email (SMTP)
SMTP_HOST = os.getenv("SMTP_HOST","your-smtp-host")
SMTP_PORT = int(os.getenv("SMTP_PORT","587"))
SMTP_USER = os.getenv("SMTP_USER","your-smtp-user")
SMTP_PASS = os.getenv("SMTP_PASS","your-smtp-pass")

# ---------- LLM / OLLAMA ----------
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:latest")
# qwen3-embedding produces 4096-dimensional vectors
VECTOR_DIM = int(os.getenv("VECTOR_DIM", "4096"))

# ---------- VECTOR DATABASE / QDRANT ----------
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "knowledge_chunks")  # For KB documents only
CASE_STUDY_COLLECTION = os.getenv("CASE_STUDY_COLLECTION", "case_studies")  # For case studies only

