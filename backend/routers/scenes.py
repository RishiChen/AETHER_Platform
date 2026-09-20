"""
Scene Retrieval & Safe Image Serving Router
"""

import sys
import sqlite3
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.dependencies import get_db
from backend.services.imagery_service import serve_image_file
from backend.config import AETHER_DIR, DATABASE_DIR

if str(DATABASE_DIR) not in sys.path:
    sys.path.insert(0, str(DATABASE_DIR))
if str(AETHER_DIR) not in sys.path:
    sys.path.insert(0, str(AETHER_DIR))

import database

router = APIRouter(prefix="", tags=["Scenes & Image Serving"])

@router.get("/api/scenes/{scene_id}")
def get_scene_by_id(scene_id: str, db: sqlite3.Connection = Depends(get_db)):
    scene = database.get_scene(db, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene '{scene_id}' not found.")
    return {"success": True, "scene": scene}

@router.get("/api/scenes/{scene_id}/image")
def get_scene_image(scene_id: str, db: sqlite3.Connection = Depends(get_db)):
    scene = database.get_scene(db, scene_id)
    if not scene or "filepath" not in scene:
        raise HTTPException(status_code=404, detail=f"Scene '{scene_id}' not found.")
    return serve_image_file(scene["filepath"])

@router.get("/imagery/{image_path:path}")
def get_imagery_by_path(image_path: str):
    """
    Serves imagery files (e.g. /imagery/loc-river-2020.jpg) safely.
    Prevent path traversal traversal.
    """
    return serve_image_file(image_path)
