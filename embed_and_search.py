"""
AETHER - embed_and_search.py
-----------------------------
CLI entry point for scene vector embedding and similarity search.
Uses modular implementation from backend.services.embed_search_service and backend_model FAISS engine.

Usage:
    python embed_and_search.py --index
    python embed_and_search.py --train
    python embed_and_search.py --query "new construction near a river"
    python embed_and_search.py --similar-to loc-river-2024
"""

import sys
import os
import sqlite3
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "Database"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

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
    parser.add_argument("--train", action="store_true", help="Train / build FAISS vector index from satellite dataset")
    parser.add_argument("--query", type=str, help="Semantic text search query")
    parser.add_argument("--similar-to", type=str, help="Image file path or scene_id for similarity search")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    # If no arguments provided, default to --index and --query sample
    if not (args.index or args.train or args.query or args.similar_to):
        args.index = True
        args.query = "river bridge construction linear corridor"

    db_path = os.path.join("Database", "aether.db") if os.path.exists(os.path.join("Database", "aether.db")) else "aether.db"
    conn = sqlite3.connect(db_path)
    ensure_embedding_column(conn)

    if args.train:
        print("==========================================================")
        print(" Training & Building FAISS Vector Index...")
        print("==========================================================")
        try:
            from backend_model.train_indexer import train_and_index_dataset
            train_and_index_dataset()
        except Exception as e:
            print(f"[embed_and_search] Training warning: {e}")

    if args.index:
        print("==========================================================")
        print(" Indexing Database Scenes into SQLite Embeddings...")
        print("==========================================================")
        count = embed_all_scenes(conn)
        print(f"Indexed {count} new scenes into database.")

    if args.query:
        print(f"\nSearching scenes for text query: \"{args.query}\"...")
        # Search via SQLite vector embeddings
        results = search_by_text(conn, args.query, top_k=args.top_k)
        if results:
            print("--- Top Matches (SQLite Vector Search) ---")
            for scene_id, filename, location, filepath, sim in results:
                print(f"  [{sim:.3f}] {filename} ({location}) - path: {filepath}")

        # Search via FAISS AI search engine if available
        try:
            from backend.ai.ai_service import get_ai_service
            ai_svc = get_ai_service()
            if ai_svc.is_available:
                faiss_results = ai_svc.search_by_text(args.query, top_k=args.top_k)
                if faiss_results:
                    print("\n--- Top Matches (RemoteCLIP + FAISS Vector Search) ---")
                    for item in faiss_results:
                        score = item.get('score', 0.0)
                        fn = item.get('filename', '')
                        path = item.get('path', '')
                        tags = ", ".join(item.get('tags', []))
                        print(f"  [{score:.3f}] {fn} - {tags} (path: {path})")
        except Exception as e:
            pass

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