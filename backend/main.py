"""
AETHER FastAPI Main Application Entry Point
--------------------------------------------
SIH 2026 Problem Statement 26227
"""

import sys
import logging
import sqlite3
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import APP_NAME, APP_VERSION, DB_PATH, FRONTEND_DIR, AETHER_DIR, DATABASE_DIR
from backend.routers import health, search, scenes, locations, changes, review, ingestion, export

if str(DATABASE_DIR) not in sys.path:
    sys.path.insert(0, str(DATABASE_DIR))
if str(AETHER_DIR) not in sys.path:
    sys.path.insert(0, str(AETHER_DIR))

import database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aether.main")

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Semantic Retrieval & Multi-Temporal Change Analysis of Satellite Imagery - Fully Offline Capable Backend System"
)

# CORS configuration for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(health.router)
app.include_router(search.router)
app.include_router(scenes.router)
app.include_router(locations.router)
app.include_router(changes.router)
app.include_router(review.router)
app.include_router(ingestion.router)
app.include_router(export.router)

from backend.ai.ai_service import get_ai_service

@app.on_event("startup")
def startup_event():
    logger.info("=======================================================")
    logger.info(" AETHER Earth Observation Platform Backend Starting")
    logger.info(f" Database Path: {DB_PATH}")
    logger.info(" Mode: OFFLINE LOCAL RETRIEVAL & PROCESSING READY")
    logger.info("=======================================================")

    # Ensure DB tables exist and default candidate dataset is seeded
    conn = sqlite3.connect(str(DB_PATH))
    try:
        database.seed_default_dataset(conn)
    finally:
        conn.close()

    # Trigger RemoteCLIP & FAISS vector index auto-initialization
    try:
        ai_svc = get_ai_service()
        logger.info(f"AI Service Status: {ai_svc.status_message}")
    except Exception as e:
        logger.warning(f"AI Service startup warning: {e}")

# Mount backend_model images directory if present
MODEL_IMAGES_DIR = Path(__file__).resolve().parent.parent / "backend_model" / "AI" / "semantic_search" / "data" / "images"
MODEL_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/model_images", StaticFiles(directory=str(MODEL_IMAGES_DIR)), name="model_images")

# Mount frontend static directory if present
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
    logger.info(f"Frontend static files mounted from {FRONTEND_DIR}")

if __name__ == "__main__":
    import uvicorn
    from backend.config import HOST, PORT
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)

