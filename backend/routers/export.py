"""
Export Dossier Router
"""

import sqlite3
from fastapi import APIRouter, Depends

from backend.dependencies import get_db
from backend.services.export_service import generate_dossier_response

router = APIRouter(prefix="/api", tags=["Export"])

@router.get("/export-dossier/{location_id}")
def export_intelligence_dossier(location_id: str, db: sqlite3.Connection = Depends(get_db)):
    return generate_dossier_response(db, location_id)
