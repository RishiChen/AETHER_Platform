import json
from pathlib import Path

import numpy as np
from PIL import Image

from .model import RemoteCLIPModel
from .index import ImageIndex


FEATURE_TAG_MAP = {
    "river": ["River Corridor", "Water Meander", "Bridge Pier", "Erosion Bank"],
    "highway": ["Linear Infrastructure", "Expressway", "Asphalt Pavement", "Transport Corridor"],
    "water": ["Reservoir", "Hydrographic Extent", "MNDWI Shift", "Shoreline"],
    "industry": ["Industrial Yard", "Storage Tanks", "Logistics Terminal", "Rooftops"],
    "cleared": ["Land Clearing", "Deforestation", "Bare Soil", "Settlement Fringe"],
    "delhi": ["Urban Agglomeration", "Settlement Footprint", "Built-up Zone"],
    "jammu": ["Jammu & Kashmir", "Mountain Settlement", "Built-up Zone", "High Altitude Terrain"],
    "kashmir": ["Jammu & Kashmir", "Kashmir Valley", "Mountain Settlement", "Terrain"],
    "kargil": ["Jammu & Kashmir", "Kargil Sector", "Mountain Settlement", "Terrain"],
    "s2": ["Sentinel-2 Optical BOA", "Multi-spectral Scene", "Land Cover"],
}

INTENT_SYNONYMS = {
    "river": {"river", "stream", "canal", "bridge", "waterway", "corridor", "meander"},
    "highway": {"highway", "road", "expressway", "linear", "corridor", "asphalt", "transport"},
    "water": {"water", "reservoir", "lake", "shoreline", "pond", "hydro", "extent"},
    "industry": {"industry", "industrial", "port", "warehouse", "terminal", "tank", "yard", "logistics"},
    "cleared": {"cleared", "clearing", "deforestation", "bare", "soil", "settlement", "fringe"},
    "urban": {"urban", "city", "building", "built", "structure", "construction"},
    "kashmir": {"jammu", "kashmir", "kargil", "ladakh", "srinagar", "mountain", "valley"},
}


def tags_for_filename(filename):
    tags = []
    lower_name = filename.lower()
    for key, values in FEATURE_TAG_MAP.items():
        if key in lower_name:
            tags.extend(values)
    return tags or ["Satellite Scene", "Earth Observation", "Local Imagery Archive"]


class SemanticSearch:

    def __init__(self):

        # =================================
        # PATHS
        # =================================

        self.data_dir = (
            Path(__file__).resolve().parent / "data"
        )

        self.image_dir = (
            self.data_dir / "images"
        )

        self.index_path = (
            self.data_dir /
            "faiss.index"
        )

        self.metadata_path = (
            self.data_dir /
            "metadata.json"
        )

        self.signature_path = (
            self.data_dir /
            "model_signature.txt"
        )

        # Create image directory

        self.image_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        # =================================
        # LOAD REMOTECLIP
        # =================================

        self.model = (
            RemoteCLIPModel()
        )

        self.model_signature = getattr(
            self.model,
            "signature",
            "unknown-encoder"
        )

        # =================================
        # LOAD METADATA
        # =================================

        if self.metadata_path.exists():

            with open(
                self.metadata_path,
                "r"
            ) as file:

                self.metadata = (
                    json.load(file)
                )

        else:

            self.metadata = {}

        # =================================
        # LOAD FAISS
        # =================================

        signature_matches = (
            self.signature_path.exists()
            and self.signature_path.read_text().strip() == self.model_signature
        )

        if self.index_path.exists() and signature_matches:

            print(
                "Loading existing FAISS index..."
            )

            # RemoteCLIP ViT-B-32
            # embedding dimension = 512

            self.index = ImageIndex(
                dimension=512
            )

            self.index.load(
                self.index_path
            )

            print(
                "Vectors:",
                self.index.count()
            )

        else:

            self.index = None
            if self.index_path.exists() and not signature_matches:
                print(
                    "FAISS index encoder mismatch; rebuilding local vector index..."
                )
                self.metadata = {}

        # Auto-index base satellite dataset if FAISS vector index is empty
        self.auto_index_dataset()

    # =================================
    # ADD IMAGE
    # =================================

    def add_image(
        self,
        image_path,
        image_id
    ):

        """
        Image
          ↓
        RemoteCLIP
          ↓
        Embedding
          ↓
        FAISS
        """

        image_path = Path(
            image_path
        )

        # Open image

        image = Image.open(
            image_path
        ).convert("RGB")

        # =================================
        # IMAGE → EMBEDDING
        # =================================

        embedding = (
            self.model.encode_image(
                image
            )
        )

        embedding = np.asarray(
            [embedding],
            dtype=np.float32
        )

        # =================================
        # CREATE FAISS IF FIRST IMAGE
        # =================================

        if self.index is None:

            dimension = (
                embedding.shape[1]
            )

            self.index = ImageIndex(
                dimension
            )

        # =================================
        # ADD TO FAISS
        # =================================

        self.index.add_embeddings(
            embedding,
            np.array(
                [image_id],
                dtype=np.int64
            )
        )

        # =================================
        # SAVE FAISS
        # =================================

        self.index.save(
            self.index_path
        )

        # =================================
        # SAVE METADATA
        # =================================

        self.metadata[
            str(image_id)
        ] = {

            "image_id": image_id,

            "filename":
                image_path.name,

            "path":
                str(image_path),

            "tags":
                tags_for_filename(image_path.name)
        }

        with open(
            self.metadata_path,
            "w"
        ) as file:

            json.dump(
                self.metadata,
                file,
                indent=4
            )

        self.signature_path.write_text(
            self.model_signature
        )

        return {

            "image_id":
                image_id,

            "filename":
                image_path.name
        }

    # =================================
    # SEARCH
    # =================================

    def search(
        self,
        query,
        top_k=5
    ):

        """
        Text
          ↓
        RemoteCLIP
          ↓
        Text embedding
          ↓
        FAISS
          ↓
        Image IDs
        """

        # No images

        if self.index is None:

            return []

        # =================================
        # TEXT → EMBEDDING
        # =================================

        text_embedding = (
            self.model.encode_text(
                query
            )
        )

        # =================================
        # FAISS SEARCH
        # =================================

        search_k = top_k
        if self.index is not None and self.index.count() > top_k:
            search_k = self.index.count()

        scores, ids = (
            self.index.search(
                text_embedding,
                search_k
            )
        )

        results = []

        # =================================
        # PROCESS RESULTS
        # =================================

        for score, image_id in zip(
            scores,
            ids
        ):

            image_id = int(
                image_id
            )

            # No result

            if image_id == -1:

                continue

            # Find metadata

            metadata = (
                self.metadata.get(
                    str(image_id)
                )
            )

            if metadata is None:

                continue

            filename = metadata.get("filename", "")
            dynamic_tags = tags_for_filename(filename) + metadata.get("tags", [])
            metadata_text = " ".join([
                filename,
                metadata.get("title", ""),
                " ".join(dynamic_tags),
            ])
            intent_score = self._intent_score(query, metadata_text)
            adjusted_score = (float(score) * 0.65) + (intent_score * 0.35)

            results.append({

                "image_id":
                    image_id,

                "score":
                    float(adjusted_score),

                "vectorScore":
                    float(score),

                "intentScore":
                    float(intent_score),

                "filename":
                    metadata[
                        "filename"
                    ],

                "path":
                    metadata[
                        "path"
                    ],

                "tags":
                    metadata.get("tags", [])
            })

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:top_k]

    # =================================
    # SEARCH BY IMAGE EMBEDDING
    # =================================

    def search_by_image(
        self,
        image_input,
        top_k=5
    ):
        if self.index is None:
            return []

        if isinstance(image_input, (str, Path)):
            image = Image.open(image_input).convert("RGB")
        elif isinstance(image_input, Image.Image):
            image = image_input.convert("RGB")
        else:
            raise ValueError("Unsupported image input type")

        image_embedding = self.model.encode_image(image)

        scores, ids = self.index.search(
            image_embedding,
            top_k
        )

        results = []
        for score, image_id in zip(scores, ids):
            image_id = int(image_id)
            if image_id == -1:
                continue
            metadata = self.metadata.get(str(image_id))
            if metadata is None:
                continue
            results.append({
                "image_id": image_id,
                "score": float(score),
                "filename": metadata["filename"],
                "path": metadata["path"],
                "tags": metadata.get("tags", [])
            })

        return results

    def _intent_score(self, query, metadata_text):
        query = (query or "").lower()
        metadata_text = (metadata_text or "").lower()
        if not query or not metadata_text:
            return 0.0

        score = 0.0
        for concept, words in INTENT_SYNONYMS.items():
            query_hits = {word for word in words if word in query}
            if not query_hits:
                continue
            metadata_hits = {word for word in words if word in metadata_text}
            if concept in metadata_text:
                metadata_hits.add(concept)
            if metadata_hits:
                score += min(1.0, len(query_hits) / 2.0) * min(1.0, len(metadata_hits) / 2.0)

        query_tokens = {token for token in query.replace("-", " ").replace("_", " ").split() if len(token) > 2}
        metadata_tokens = {token for token in metadata_text.replace("-", " ").replace("_", " ").split() if len(token) > 2}
        if query_tokens:
            score += len(query_tokens & metadata_tokens) / len(query_tokens)

        return min(1.0, score)

    # =================================
    # AUTO INDEX BASE DATASET
    # =================================

    def auto_index_dataset(self):
        root_dir = Path(__file__).resolve().parent.parent.parent.parent
        imagery_dirs = [
            root_dir / "Frontend" / "imagery",
            self.image_dir,
        ]

        # List default and user-trained satellite images to seed FAISS vector index
        image_files = []
        for imagery_dir in imagery_dirs:
            if not imagery_dir.exists():
                continue
            image_files.extend([
                f for f in imagery_dir.iterdir()
                if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".tif", ".tiff"]
            ])

        if not image_files:
            return

        indexed_paths = {m["path"] for m in self.metadata.values()}
        next_id = max([int(k) for k in self.metadata.keys()], default=0) + 1

        new_indexed_count = 0
        for img_path in image_files:
            if str(img_path) in indexed_paths or img_path.name in [m.get("filename") for m in self.metadata.values()]:
                continue
            print(f"Auto-indexing dataset image into FAISS: {img_path.name}")
            try:
                self.add_image(img_path, next_id)
                next_id += 1
                new_indexed_count += 1
            except Exception as e:
                print(f"Failed to auto-index {img_path.name}: {e}")

        if new_indexed_count > 0:
            print(f"FAISS index populated with {new_indexed_count} new satellite images.")
