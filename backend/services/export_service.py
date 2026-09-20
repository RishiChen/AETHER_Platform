"""
AETHER Export Dossier Service
------------------------------
Generates standardized GeoJSON Intelligence Dossier reports.
"""

import sys
from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from backend.config import AETHER_DIR, DATABASE_DIR

if str(DATABASE_DIR) not in sys.path:
    sys.path.insert(0, str(DATABASE_DIR))
if str(AETHER_DIR) not in sys.path:
    sys.path.insert(0, str(AETHER_DIR))

import database

def generate_dossier_response(db_conn, location_id: str) -> JSONResponse:
    loc = database.get_location_details(db_conn, location_id)
    if not loc or "title" not in loc:
        raise HTTPException(status_code=404, detail=f"Location '{location_id}' not found.")

    review = loc.get("reviewStatus") or {"status": "PENDING_ANALYST_REVIEW"}
    coords = loc.get("coordinates", {})
    bounds = loc.get("bounds", [])
    ca = loc.get("changeAnalysis", {})

    polygon_coords = []
    if len(bounds) >= 2:
        polygon_coords = [[
            [bounds[0][1], bounds[0][0]],
            [bounds[1][1], bounds[0][0]],
            [bounds[1][1], bounds[1][0]],
            [bounds[0][1], bounds[1][0]],
            [bounds[0][1], bounds[0][0]]
        ]]

    temp_seq = loc.get("temporalSequence", [])
    b_year = ca.get("beforeYear", "2020")
    a_year = ca.get("afterYear", "2024")
    b_item = next((item for item in temp_seq if item.get("year") == b_year), temp_seq[0] if temp_seq else {})
    a_item = next((item for item in temp_seq if item.get("year") == a_year), temp_seq[-1] if temp_seq else {})

    from backend.services.provenance_service import build_dynamic_provenance
    prov_data = build_dynamic_provenance(
        location_id=loc.get("id", location_id),
        location_title=loc.get("title", location_id),
        coordinates=coords,
        before_item=b_item,
        after_item=a_item,
        sensor_name=loc.get("sensor", "Copernicus Sentinel-2 MSI (Level-2A BOA)")
    )

    dossier = {
        "type": "FeatureCollection",
        "aetherMetadata": {
            "platform": "AETHER - Adaptive Earth-observation Temporal Hyper-semantic Engine for Retrieval",
            "problemStatement": "SIH 2026 PS 26227",
            "exportTimestamp": datetime.now(timezone.utc).isoformat(),
            "classification": "OFFLINE ANALYST EVALUATION REPORT",
            "standardsCompliance": [
                "W3C PROV-DM (Data Model)",
                "W3C PROV-O (Ontology RDF JSON-LD)",
                "ISO 19115 (Geographic Information - Metadata - Lineage)"
            ]
        },
        "locationIntelligence": {
            "id": loc.get("id", location_id),
            "title": loc.get("title"),
            "region": loc.get("region"),
            "coordinates": coords,
            "sensor": loc.get("sensor"),
            "provenance": prov_data,
            "falseAlarmMetrics": ca.get("falseAlarmAnalysis", {}),
            "analystReview": review
        },
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": polygon_coords
                },
                "properties": {
                    "name": loc.get("title"),
                    "detectedChangeType": ca.get("changeType", "N/A"),
                    "confidence": ca.get("confidenceScore", 0),
                    "affectedArea": ca.get("affectedArea", "N/A")
                }
            }
        ]
    }

    filename = f"AETHER_Dossier_{location_id}_{int(datetime.now(timezone.utc).timestamp())}.json"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }

    return JSONResponse(content=dossier, headers=headers)
