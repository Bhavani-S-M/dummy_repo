"""
Script to recreate Qdrant collection with correct dimensions for qwen2-embedding model.

This script will:
1. Delete the existing Qdrant collection (if it exists)
2. Create a new collection with 768 dimensions (for qwen2-embedding)
3. Verify the collection was created successfully

Run this after changing the embedding model from mxbai-embed-large (1024d) to qwen2-embedding (768d).
"""

import sys
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Import config
from app.config.config import QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION, VECTOR_DIM

def recreate_collection():
    """Delete and recreate Qdrant collection with correct dimensions."""

    print(f"🔄 Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}...")
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    # Check if collection exists
    try:
        collections = client.get_collections().collections
        existing_names = [c.name for c in collections]

        if QDRANT_COLLECTION in existing_names:
            print(f"⚠️  Collection '{QDRANT_COLLECTION}' exists. Deleting...")
            client.delete_collection(collection_name=QDRANT_COLLECTION)
            print(f"✅ Deleted old collection '{QDRANT_COLLECTION}'")
        else:
            print(f"ℹ️  Collection '{QDRANT_COLLECTION}' does not exist yet")
    except Exception as e:
        print(f"❌ Error checking collections: {e}")
        sys.exit(1)

    # Create new collection with correct dimensions
    try:
        print(f"🔨 Creating new collection '{QDRANT_COLLECTION}' with {VECTOR_DIM} dimensions...")
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=models.VectorParams(
                size=VECTOR_DIM,
                distance=models.Distance.COSINE,
            ),
        )
        print(f"✅ Created Qdrant collection '{QDRANT_COLLECTION}' ({VECTOR_DIM} dims)")

        # Verify collection
        collection_info = client.get_collection(collection_name=QDRANT_COLLECTION)
        print(f"\n📊 Collection Info:")
        print(f"   Name: {QDRANT_COLLECTION}")
        print(f"   Vector Size: {collection_info.config.params.vectors.size}")
        print(f"   Distance: {collection_info.config.params.vectors.distance}")
        print(f"\n✅ Collection successfully recreated!")

    except Exception as e:
        print(f"❌ Error creating collection: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("Qdrant Collection Recreator")
    print("=" * 60)
    print(f"Model: qwen2-embedding:latest")
    print(f"Vector Dimension: {VECTOR_DIM}")
    print(f"Collection: {QDRANT_COLLECTION}")
    print("=" * 60)

    confirm = input("\n⚠️  This will DELETE all existing vectors! Continue? (yes/no): ")
    if confirm.lower() != "yes":
        print("❌ Cancelled by user")
        sys.exit(0)

    recreate_collection()
