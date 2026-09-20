"""
Location Inspection Router
"""

import sys
import sqlite3
from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_db
from backend.schemas import LocationResponse
from backend.config import AETHER_DIR, DATABASE_DIR

if str(DATABASE_DIR) not in sys.path:
    sys.path.insert(0, str(DATABASE_DIR))
if str(AETHER_DIR) not in sys.path:
    sys.path.insert(0, str(AETHER_DIR))

import database

router = APIRouter(prefix="/api", tags=["Locations"])

@router.get("/location/{location_id}", response_model=LocationResponse)
def get_location_by_id(location_id: str, db: sqlite3.Connection = Depends(get_db)):
    loc = database.get_location_details(db, location_id)
    if not loc or "title" not in loc:
        raise HTTPException(status_code=404, detail=f"Location '{location_id}' not found.")
    return {"success": True, "location": loc}
