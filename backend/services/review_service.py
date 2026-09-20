"""
AETHER Review Service
---------------------
Persists analyst review decisions (Confirmed, Rejected, Flagged) to SQLite.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional

from backend.config import AETHER_DIR, DATABASE_DIR

if str(DATABASE_DIR) not in sys.path:
    sys.path.insert(0, str(DATABASE_DIR))
if str(AETHER_DIR) not in sys.path:
    sys.path.insert(0, str(AETHER_DIR))

import database

def record_review_decision(
    db_conn,
    location_id: str,
    decision: str,
    analyst_id: Optional[str] = "ANALYST_4092_SIGINT",
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Saves an analyst review decision into SQLite aether.db database.
    """
    valid_decisions = ("confirmed", "rejected", "flagged", "pending")
    if decision not in valid_decisions:
        raise ValueError(f"Invalid decision '{decision}'. Allowed: {valid_decisions}")

    if not notes:
        if decision == "confirmed":
            notes = "Verified genuine anthropogenic change. Evidence consistent with satellite baseline."
        elif decision == "rejected":
            notes = "Marked as false positive or natural phenological variation."
        else:
            notes = "Marked for secondary oversight and senior analyst signoff."

    review_record = database.save_analyst_review(
        db_conn,
        location_id=location_id,
        decision=decision,
        analyst_id=analyst_id or "ANALYST_4092_SIGINT",
        notes=notes
    )

    return {
        "success": True,
        "message": f"Review recorded: {decision.upper()}",
        "review": review_record
    }
