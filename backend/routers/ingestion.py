"""
Archive Ingestion Router
"""

import sqlite3
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException

from backend.dependencies import get_db
from backend.schemas import IngestionResponse
from backend.services.ingestion_service import process_uploaded_archive

router = APIRouter(prefix="/api", tags=["Archive Ingestion"])

@router.post("/ingest", response_model=IngestionResponse)
async def ingest_archive(
    archive: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_db)
):
    content = await archive.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        result = process_uploaded_archive(db, archive.filename, content)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest archive: {str(e)}")
