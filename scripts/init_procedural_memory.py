#!/usr/bin/env python3
"""
Initialize Procedural Memory in Qdrant

This script:
1. Creates the procedural_memory collection in Qdrant
2. Loads seed Procedural Memory entries
3. Validates the setup

Procedural Memory stores versioned instruction sets that tell agents how to perform tasks.
Each entry includes structured metadata and natural language prose content.
"""

import json
import requests
from typing import List, Dict, Any
from datetime import datetime

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "procedural_memory"

def create_collection():
    """Create the procedural_memory collection with appropriate settings"""
    print(f"Creating collection '{COLLECTION_NAME}'...")

    # Collection configuration
    # Using 768-dimensional vectors (matches nomic-embed-text-v1.5 on G14)
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
    else:
        print(f"✗ Failed to create collection: {response.text}")
        return False

    return True


def load_seed_entries(seed_file: str):
    """Load seed Procedural Memory entries from JSON file"""
    print(f"\nLoading seed entries from {seed_file}...")

    with open(seed_file, 'r') as f:
        entries = json.load(f)

    print(f"Found {len(entries)} seed entries")

    # For bootstrap, we'll use simple embeddings from the instruction content
    # In production, these will be embedded via the G14 embedding service
    # For now, we'll insert with placeholder vectors and update them later

    points = []
    for i, entry in enumerate(entries):
        point = {
            "id": i + 1,
            "vector": [0.0] * 768,  # Placeholder - will be embedded properly later
            "payload": {
                "id": entry["id"],
                "version": entry["version"],
                "domain": entry["domain"],
                "content": entry["content"],
                "authorship": entry["authorship"],
                "performance_metrics": entry.get("performance_metrics", {}),
                "last_validated": entry.get("last_validated", datetime.now().isoformat()),
                "metadata": entry.get("metadata", {})
            }
        }
        points.append(point)

    # Batch insert
    response = requests.put(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points",
        json={"points": points}
    )

    if response.status_code == 200:
        print(f"✓ Loaded {len(points)} entries into Qdrant")
        return True
    else:
        print(f"✗ Failed to load entries: {response.text}")
        return False


def verify_setup():
    """Verify the collection and entries"""
    print("\nVerifying setup...")

    # Check collection exists
    response = requests.get(f"{QDRANT_URL}/collections/{COLLECTION_NAME}")
    if response.status_code != 200:
        print("✗ Collection not found")
        return False

    info = response.json()["result"]
    print(f"✓ Collection exists with {info['points_count']} points")

    # List some entries
    response = requests.post(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
        json={"limit": 3, "with_payload": True, "with_vector": False}
    )

    if response.status_code == 200:
        points = response.json()["result"]["points"]
        print(f"\nSample entries:")
        for point in points:
            payload = point["payload"]
            print(f"  - {payload['id']} ({payload['domain']}): {payload['authorship']}")

    return True


def main():
    print("=== Procedural Memory Initialization ===\n")

    # Create collection
    if not create_collection():
        return

    # Load seed entries
    seed_file = "/home/dave/babs/seeds/procedural_memory_seeds.json"
    if not load_seed_entries(seed_file):
        return

    # Verify
    if verify_setup():
        print("\n✓ Procedural Memory initialization complete!")
        print("\nNext steps:")
        print("  1. Wire up G14 embedding service to generate real vectors")
        print("  2. Add retrieval pipeline to Supervisor service")
        print("  3. Implement learning mechanism for new procedures")
    else:
        print("\n✗ Verification failed")


if __name__ == "__main__":
    main()
