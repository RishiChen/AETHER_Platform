"""
Analyst Review Router
"""

import sqlite3
from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_db
from backend.schemas import ReviewRequest, ReviewResponse
from backend.services.review_service import record_review_decision

router = APIRouter(prefix="/api", tags=["Analyst Review"])

@router.post("/review", response_model=ReviewResponse)
def submit_review(body: ReviewRequest, db: sqlite3.Connection = Depends(get_db)):
    if not body.locationId or not body.decision:
        raise HTTPException(status_code=400, detail="locationId and decision are required.")

    try:
        res = record_review_decision(
            db_conn=db,
            location_id=body.locationId,
            decision=body.decision,
            analyst_id=body.analystId,
            notes=body.notes
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
