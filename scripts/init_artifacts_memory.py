#!/usr/bin/env python3
"""
Initialize Artifacts Collection in Qdrant
"""
import requests

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "artifacts"

def create_collection():
    print(f"Creating collection '{COLLECTION_NAME}'...")
    config = {
        "vectors": {
            "size": 768,
            "distance": "Cosine"
        }
    }
    response = requests.put(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
        json=config
    )
    if response.status_code == 200:
        print(f"✓ Collection '{COLLECTION_NAME}' created successfully")
    elif response.status_code == 400 and "already exists" in response.text:
        print(f"✓ Collection '{COLLECTION_NAME}' already exists")
    else:
        print(f"✗ Failed to create collection: {response.text}")
        return False
    return True

if __name__ == "__main__":
    create_collection()
