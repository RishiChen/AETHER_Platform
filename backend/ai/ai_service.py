"""
AETHER AI / ML Service Adapter
-------------------------------
Connects FastAPI to backend_model (RemoteCLIP + FAISS vector search).
"""

import sys
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_MODEL_DIR = ROOT_DIR / "backend_model"
if str(BACKEND_MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_MODEL_DIR))

logger = logging.getLogger("aether.ai_service")

class AIService:
    """
    Adapter interfacing with backend_model.AI.semantic_search.search.SemanticSearch
    """
    def __init__(self):
        self.semantic_search = None
        self.is_available = False
        self.status_message = "INITIALIZING"

        self._try_load_model()

    def _try_load_model(self):
        try:
            from AI.semantic_search.search import SemanticSearch
            self.semantic_search = SemanticSearch()
            self.is_available = True
            self.status_message = "OPERATIONAL"
            logger.info("[AETHER AI Service] RemoteCLIP & FAISS vector index loaded successfully.")
        except Exception as e:
            self.is_available = False
            self.status_message = f"UNAVAILABLE_ERROR: {str(e)}"
            logger.warning(f"[AETHER AI Service] RemoteCLIP model initialization deferred: {e}")

    def search_by_text(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Executes semantic text vector search using RemoteCLIP + FAISS.
        """
        if self.is_available and self.semantic_search:
            try:
                return self.semantic_search.search(query, top_k)
            except Exception as e:
                logger.error(f"[AETHER AI Service] Text vector search failed: {e}")
        return []

    def search_similar_image(self, image_input: Any, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Executes image-to-image similarity vector search using RemoteCLIP + FAISS.
        """
        if self.is_available and self.semantic_search:
            try:
                return self.semantic_search.search_by_image(image_input, top_k)
            except Exception as e:
                logger.error(f"[AETHER AI Service] Image vector search failed: {e}")
        return []

    def add_uploaded_image(self, image_path: Path, image_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Extracts image embedding via RemoteCLIP, appends vector to FAISS, and saves metadata.
        """
        if self.is_available and self.semantic_search:
            try:
                if image_id is None:
                    existing_ids = [int(k) for k in self.semantic_search.metadata.keys() if k.isdigit()]
                    image_id = max(existing_ids, default=0) + 1
                return self.semantic_search.add_image(image_path, image_id)
            except Exception as e:
                logger.error(f"[AETHER AI Service] Image indexing failed: {e}")
        return {"error": "AI service unavailable"}

# Singleton instance
ai_service_instance = AIService()

def get_ai_service() -> AIService:
    return ai_service_instance
