"""
AETHER Local Dataset Trainer & FAISS Vector Indexer
----------------------------------------------------
Scans local satellite imagery, extracts RemoteCLIP / CNN feature vectors,
tags visual feature characteristics, and builds offline FAISS vector index.
"""

import os
import sys
import json
from pathlib import Path
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_MODEL_DIR = ROOT_DIR / "backend_model"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BACKEND_MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_MODEL_DIR))

from AI.semantic_search.search import SemanticSearch

# Default feature tags based on filename pattern
FEATURE_TAG_MAP = {
    "river": ["River Corridor", "Water Meander", "Bridge Pier", "Erosion Bank"],
    "highway": ["Linear Infrastructure", "Expressway", "Asphalt Pavement", "Transport Cut"],
    "water": ["Reservoir", "Hydrographic Extent", "MNDWI Shift", "Shoreline"],
    "industry": ["Industrial Yard", "Storage Tanks", "Logistics Terminal", "Rooftops"],
    "cleared": ["Land Clearing", "Deforestation", "Bare Soil", "Settlement Fringe"],
    "delhi": ["Urban Agglomeration", "Settlement Footprint", "Built-up Zone"],
    "s2": ["Sentinel-2 Optical BOA", "Multi-spectral Scene", "Land Cover"]
}

def train_and_index_dataset(images_dir: Path = None):
    print("==========================================================")
    print(" AETHER Local Satellite Dataset Trainer & FAISS Indexer")
    print("==========================================================")

    search_engine = SemanticSearch()

    search_dirs = []
    if images_dir and images_dir.exists():
        search_dirs.append(images_dir)
    else:
        search_dirs = [
            ROOT_DIR / "Frontend" / "imagery",
            ROOT_DIR / "AETHER" / "data" / "before",
            ROOT_DIR / "AETHER" / "data" / "after",
            ROOT_DIR / "backend_model" / "AI" / "semantic_search" / "data" / "images"
        ]

    image_files = []
    for sdir in search_dirs:
        if sdir.exists():
            image_files.extend([
                f for f in sdir.iterdir()
                if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".tif", ".tiff"] and not f.name.endswith("-mask.svg") and not "mask" in f.name.lower()
            ])

    print(f"Found {len(image_files)} satellite imagery files to train/index.")

    indexed_count = 0
    next_id = max([int(k) for k in search_engine.metadata.keys() if k.isdigit()], default=0) + 1

    for img_path in image_files:
        filename = img_path.name
        # Check if already indexed
        already_indexed = any(
            m.get("filename") == filename or m.get("path") == str(img_path)
            for m in search_engine.metadata.values()
        )
        if already_indexed:
            continue

        print(f"  [Processing] Extracting feature vectors for {filename} (ID: {next_id})...")

        # Derive feature tags
        tags = []
        fn_lower = filename.lower()
        for key, tag_list in FEATURE_TAG_MAP.items():
            if key in fn_lower:
                tags.extend(tag_list)
        if not tags:
            tags = ["Satellite Scene", "Earth Observation", "Local Imagery Archive"]

        # Add image to FAISS
        try:
            res = search_engine.add_image(img_path, next_id)
            # Enrich metadata with tags and location metadata
            search_engine.metadata[str(next_id)]["tags"] = tags
            search_engine.metadata[str(next_id)]["title"] = filename.replace("-", " ").replace("_", " ").title().replace(".Jpg", "")
            search_engine.metadata[str(next_id)]["source"] = "Copernicus Sentinel-2"
            search_engine.metadata[str(next_id)]["sensor"] = "MSI Level-2A BOA"

            next_id += 1
            indexed_count += 1
        except Exception as e:
            print(f"  [Error] Failed to encode/index {filename}: {e}")

    # Persist updated metadata
    with open(search_engine.metadata_path, "w") as f:
        json.dump(search_engine.metadata, f, indent=4)

    total_vectors = search_engine.index.count() if search_engine.index else 0
    print("==========================================================")
    print(f" Dataset Indexing Complete!")
    print(f" Newly Indexed: {indexed_count} images")
    print(f" Total FAISS Vectors: {total_vectors}")
    print(f" Saved FAISS Index: {search_engine.index_path}")
    print(f" Saved Metadata: {search_engine.metadata_path}")
    print("==========================================================")

if __name__ == "__main__":
    train_and_index_dataset()

