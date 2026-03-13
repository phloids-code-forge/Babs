#!/usr/bin/env python3
"""
Re-embed Procedural Memory seeds with real G14 embeddings

This script:
1. Reads all existing Procedural Memory entries from Qdrant
2. Generates real embeddings via G14 embedding service
3. Updates the vectors in Qdrant

Run this after init_procedural_memory.py to replace placeholder zero vectors.
"""

import json
import requests
from typing import List, Dict, Any

QDRANT_URL = "http://localhost:6333"
EMBEDDING_URL = "http://g14:8080/embed"
COLLECTION_NAME = "procedural_memory"


def get_all_points() -> List[Dict[str, Any]]:
    """Retrieve all points from the collection"""
    print(f"Fetching all points from '{COLLECTION_NAME}'...")

    response = requests.post(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
        json={"limit": 100, "with_payload": True, "with_vector": False}
    )

    if response.status_code != 200:
        print(f"✗ Failed to fetch points: {response.text}")
        return []

    points = response.json()["result"]["points"]
    print(f"✓ Found {len(points)} points")
    return points


def get_embedding(text: str) -> List[float]:
    """Get embedding vector from G14 service"""
    response = requests.post(
        EMBEDDING_URL,
        json={"inputs": text},
        headers={"Content-Type": "application/json"}
    )

    if response.status_code != 200:
        raise Exception(f"Embedding request failed: {response.text}")

    # Response is a list of vectors (we send single input, get single vector)
    return response.json()[0]


def update_point_vector(point_id: int, vector: List[float], payload: Dict[str, Any]) -> bool:
    """Update a single point's vector in Qdrant while preserving payload"""
    response = requests.put(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points",
        json={
            "points": [{
                "id": point_id,
                "vector": vector,
                "payload": payload
            }]
        }
    )

    return response.status_code == 200


def main():
    print("=== Re-embedding Procedural Memory Seeds ===\n")

    # Fetch all points
    points = get_all_points()
    if not points:
        print("No points to re-embed")
        return

    print(f"\nRe-embedding {len(points)} entries...")

    success_count = 0
    for point in points:
        point_id = point["id"]
        payload = point["payload"]

        # Use the content field for embedding
        text = payload["content"]
        print(f"\nProcessing: {payload['id']}")
        print(f"  Domain: {payload['domain']}")
        print(f"  Content length: {len(text)} chars")

        try:
            # Get embedding from G14
            vector = get_embedding(text)
            print(f"  ✓ Generated {len(vector)}-dim embedding")

            # Update in Qdrant (preserve payload)
            if update_point_vector(point_id, vector, payload):
                print(f"  ✓ Updated vector in Qdrant")
                success_count += 1
            else:
                print(f"  ✗ Failed to update vector in Qdrant")

        except Exception as e:
            print(f"  ✗ Error: {e}")

    print(f"\n=== Summary ===")
    print(f"Successfully re-embedded: {success_count}/{len(points)} entries")

    if success_count == len(points):
        print("\n✓ All Procedural Memory seeds now have real embeddings!")
        print("\nYou can verify with:")
        print("  curl http://localhost:6333/collections/procedural_memory")
    else:
        print(f"\n⚠ {len(points) - success_count} entries failed to re-embed")


if __name__ == "__main__":
    main()
