"""
AETHER - embed_and_search.py
-----------------------------
CLI entry point for scene vector embedding and similarity search.
Uses modular implementation from backend.services.embed_search_service.

Usage:
    python embed_and_search.py --index
    python embed_and_search.py --query "new construction near a river"
    python embed_and_search.py --similar-to loc-river-2024
"""

import sys
import os
import sqlite3
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.services.embed_search_service import (
    embed_all_scenes,
    search_by_text,
    find_similar_scenes,
    ensure_embedding_column,
    get_image_embedding
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AETHER Scene Vector Embedding & Search")
    parser.add_argument("--index", action="store_true", help="Embed all un-embedded scenes in database")
    parser.add_argument("--query", type=str, help="Semantic text search query")
    parser.add_argument("--similar-to", type=str, help="Image file path or scene_id for similarity search")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    db_path = os.path.join(BASE_DIR, "Database", "aether.db") if os.path.exists(os.path.join(BASE_DIR, "Database", "aether.db")) else os.path.join(BASE_DIR, "aether.db")
    conn = sqlite3.connect(db_path)
    ensure_embedding_column(conn)

    if args.index:
        count = embed_all_scenes(conn)
        print(f"Indexed {count} new scenes into database.")

    if args.query:
        print(f"\nSearching scenes for text query: \"{args.query}\"...")
        results = search_by_text(conn, args.query, top_k=args.top_k)
        for scene_id, filename, location, filepath, sim in results:
            print(f"  [{sim:.3f}] {filename} ({location}) - path: {filepath}")

    if args.similar_to:
        print(f"\nSearching scenes similar to: \"{args.similar_to}\"...")
        target_path = args.similar_to
        if not os.path.exists(target_path):
            cur = conn.cursor()
            row = cur.execute("SELECT filepath FROM scenes WHERE id = ? OR filename LIKE ?", (args.similar_to, f"%{args.similar_to}%")).fetchone()
            if row:
                target_path = row[0]

        if os.path.exists(target_path):
            results = find_similar_scenes(conn, target_path, top_k=args.top_k)
            for scene_id, filename, location, filepath, sim in results:
                print(f"  [{sim:.3f}] {filename} ({location}) - path: {filepath}")
        else:
            print(f"Target image or scene_id not found: {args.similar_to}")

    conn.close()
