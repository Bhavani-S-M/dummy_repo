from __future__ import annotations
import logging
import os
import time
import requests
from functools import lru_cache
from typing import List, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.config.config import (
    OLLAMA_HOST,
    OLLAMA_MODEL,
    OLLAMA_EMBED_MODEL,
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_COLLECTION,
    VECTOR_DIM,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

__all__ = [
    "get_llm_client",
    "get_embed_client",
    "embed_text_ollama",
    "get_qdrant_client",
]

# -------------------------------------------------------------------------
# Ollama Configuration
# -------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_llm_client() -> dict:
    """Return Ollama configuration for text generation."""
    return {"host": OLLAMA_HOST, "model": OLLAMA_MODEL}


@lru_cache(maxsize=1)
def get_embed_client() -> dict:
    """Return Ollama embedding configuration."""
    return {"host": OLLAMA_HOST, "model": OLLAMA_EMBED_MODEL, "vector_dim": VECTOR_DIM}


# -------------------------------------------------------------------------
# Embedding generator
# -------------------------------------------------------------------------
def embed_text_ollama(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings using Ollama embedding model.
    Retries once on transient errors, auto-detects dimension if needed.
    """
    embed_cfg = get_embed_client()
    url = f"{embed_cfg['host'].rstrip('/')}/api/embed"
    model = embed_cfg["model"]
    expected_dim = int(embed_cfg["vector_dim"])

    if not isinstance(texts, list):
        texts = [str(texts)]
    texts = [t.strip() for t in texts if t and t.strip()]
    if not texts:
        logger.warning("⚠️ No valid texts provided for embedding.")
        return []

    payload = {"model": model, "input": texts}

    for attempt in range(2):  # Retry once
        try:
            logger.info(f"🔄 Calling Ollama embedding API: {url} with model={model}, {len(texts)} texts")
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()

            logger.debug(f"📥 Ollama response keys: {list(data.keys())}")

            embeddings = (
                data.get("embedding")
                or data.get("embeddings")
                or data.get("data")
                or []
            )

            # Normalize nested structure
            if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], (int, float)):
                embeddings = [embeddings]
            elif isinstance(embeddings, list) and isinstance(embeddings[0], dict):
                embeddings = [d.get("embedding", []) for d in embeddings if "embedding" in d]

            valid_vectors = [
                v for v in embeddings
                if isinstance(v, list)
                and len(v) > 0
                and all(isinstance(x, (int, float)) for x in v)
            ]

            if not valid_vectors:
                logger.error(f"❌ No valid embedding vectors found. Raw embeddings type: {type(embeddings)}, length: {len(embeddings) if isinstance(embeddings, list) else 'N/A'}")
                raise ValueError("Empty or invalid embedding vectors")

            dim = len(valid_vectors[0])
            if dim != expected_dim:
                logger.warning(
                    f"⚠️ Embedding dimension mismatch — got {dim}, expected {expected_dim}. "
                    f"Update VECTOR_DIM in config if model changed."
                )

            logger.info(f"✅ Generated {len(valid_vectors)} embeddings with dimension {dim}")
            return valid_vectors

        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ Cannot connect to Ollama at {url}. Is Ollama running? Error: {e}")
            if attempt == 0:
                time.sleep(1.5)
                continue
            else:
                logger.error("❌ Ollama embedding failed after retry - Ollama service not available.")
                return []
        except Exception as e:
            logger.error(f"❌ Embedding attempt {attempt+1} failed: {type(e).__name__}: {e}")
            if attempt == 0:
                time.sleep(1.5)
                continue
            else:
                logger.error("❌ Ollama embedding failed after retry.")
                return []


# -------------------------------------------------------------------------
# Qdrant Client
# -------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Initialize or reuse a Qdrant client (auto-creates collection if missing)."""
    try:
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

        collections = client.get_collections().collections
        existing = [c.name for c in collections]

        if QDRANT_COLLECTION not in existing:
            client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=models.VectorParams(
                    size=VECTOR_DIM,
                    distance=models.Distance.COSINE,
                ),
            )
            logger.info(f"✅ Created Qdrant collection '{QDRANT_COLLECTION}' ({VECTOR_DIM} dims)")
        else:
            logger.info(f"ℹ️ Qdrant collection '{QDRANT_COLLECTION}' already exists")

        return client

    except Exception as e:
        logger.exception(f"❌ Failed to initialize Qdrant client: {e}")
        raise
