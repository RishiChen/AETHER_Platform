"""
Health & System Statistics Router
"""

import sys
from fastapi import APIRouter, Depends
import sqlite3

from backend.dependencies import get_db
from backend.ai.ai_service import AIService, get_ai_service
from backend.schemas import HealthResponse, StatsResponse
from backend.config import AETHER_DIR, DATABASE_DIR

if str(DATABASE_DIR) not in sys.path:
    sys.path.insert(0, str(DATABASE_DIR))
if str(AETHER_DIR) not in sys.path:
    sys.path.insert(0, str(AETHER_DIR))

import database

router = APIRouter(prefix="/api", tags=["Health & System"])

@router.get("/health", response_model=HealthResponse)
def get_health_status(
    db: sqlite3.Connection = Depends(get_db),
    ai_service: AIService = Depends(get_ai_service)
):
    return HealthResponse(
        status="ok",
        offlineMode=True,
        systemStatus="ONLINE · LOCAL ARCHIVE READY",
        databaseConnected=True,
        aiModelStatus=ai_service.status_message
    )

@router.get("/stats", response_model=StatsResponse)
def get_system_stats(db: sqlite3.Connection = Depends(get_db)):
    locs = database.list_locations(db)
    reviews_count = 0
    for loc_id in locs:
        if database.get_analyst_review(db, loc_id):
            reviews_count += 1

    return StatsResponse(
        offlineMode=True,
        systemStatus="ONLINE · LOCAL ARCHIVE READY",
        archiveSize="1.4 TB (Indexed)",
        indexedTiles=142850,
        activeSensors=[
            "Copernicus Sentinel-2 MSI",
            "Copernicus Sentinel-1 SAR",
            "USGS Landsat Collection 2"
        ],
        pendingReviews=max(0, len(locs) - reviews_count),
        completedReviews=reviews_count
    )
