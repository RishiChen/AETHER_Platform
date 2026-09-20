"""
AETHER Search Service
---------------------
Handles semantic text search & image similarity candidate retrieval from SQLite.
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Iterable, List

from backend.config import AETHER_DIR, DATABASE_DIR
from backend.ai.ai_service import AIService

if str(DATABASE_DIR) not in sys.path:
    sys.path.insert(0, str(DATABASE_DIR))
if str(AETHER_DIR) not in sys.path:
    sys.path.insert(0, str(AETHER_DIR))

import database

logger = logging.getLogger("aether.search_service")

LOCATION_KEY_MAP = {
    "river": "loc-river",
    "highway": "loc-highway",
    "water": "loc-water",
    "industry": "loc-industry",
    "cleared": "loc-cleared",
    "jammu": "loc-jammu",
    "kashmir": "loc-kashmir",
    "srinagar": "loc-kashmir",
    "kargil": "loc-kargil",
    "ladakh": "loc-kargil",
}
TEXT_MIN_SCORE = 0.15
IMAGE_MIN_SCORE = 0.18


def normalize_similarity_score(score: float) -> int:
    """Convert cosine similarity to a conservative UI percentage."""
    return int(max(0, min(99, round(((score + 1.0) / 2.0) * 100))))


def location_id_from_text(text: str) -> Optional[str]:
    lower_name = (text or "").lower()
    for key, loc_id in LOCATION_KEY_MAP.items():
        if key in lower_name:
            return loc_id
    return None


def image_url_for_match(match: Dict[str, Any]) -> str:
    path = Path(match.get("path") or "")
    filename = match.get("filename", path.name)
    if path.exists() and "backend_model" in path.parts:
        return f"/model_images/{filename}"
    return f"/imagery/{filename}"


def dynamic_candidate_from_match(match: Dict[str, Any], score: int, rationale: str) -> Dict[str, Any]:
    filename = match.get("filename", "matched-scene.jpg")
    img_url = image_url_for_match(match)
    title_str = match.get("title", "")
    image_id_str = str(match.get("image_id", ""))
    text_to_check = f"{filename} {title_str} {image_id_str}".lower()

    # Determine precise region & coordinates inside India based on keyword clues
    if "jammu" in text_to_check:
        region_str = "Jammu Region, Jammu & Kashmir, India"
        lat, lon = 32.7266, 74.8570
        dms_str = "32°43'36\" N, 74°51'25\" E"
    elif "kashmir" in text_to_check or "srinagar" in text_to_check:
        region_str = "Kashmir Valley, Jammu & Kashmir, India"
        lat, lon = 34.0837, 74.7973
        dms_str = "34°05'01\" N, 74°47'50\" E"
    elif "kargil" in text_to_check or "ladakh" in text_to_check:
        region_str = "Kargil Sector, Jammu & Kashmir, India"
        lat, lon = 34.5539, 76.1349
        dms_str = "34°33'14\" N, 76°08'05\" E"
    elif "delhi" in text_to_check or "yamuna" in text_to_check:
        region_str = "Delhi-NCR Basin, India"
        lat, lon = 28.5450, 77.3100
        dms_str = "28°32'42\" N, 77°18'36\" E"
    elif "gujarat" in text_to_check or "kutch" in text_to_check:
        region_str = "Gulf of Kutch, Gujarat, India"
        lat, lon = 22.7600, 69.7200
        dms_str = "22°45'36\" N, 69°43'12\" E"
    else:
        region_str = "Jammu & Kashmir Sector, India"
        lat, lon = 34.5539, 76.1349
        dms_str = "34°33'14\" N, 76°08'05\" E"

    return {
        "id": f"img-{match.get('image_id', filename)}",
        "title": filename.replace("-", " ").replace("_", " ").title().replace(".Jpg", "").replace(".Jpeg", "").replace(".Png", ""),
        "region": region_str,
        "coordinates": {
            "lat": lat,
            "lon": lon,
            "dms": dms_str,
            "mgrs": "43WES451234",
            "utm": f"Zone 43N {int(lon*10000)}m E {int(lat*100000)}m N",
        },
        "bounds": [[lat - 0.02, lon - 0.02], [lat + 0.02, lon + 0.02]],
        "source": "Local Offline Satellite Archive",
        "sensor": "RemoteCLIP / CNN Visual Embedding",
        "resolution": "10m / pixel",
        "sunZenith": "30.0°",
        "cloudCover": "0.2%",
        "matchScore": score,
        "tags": match.get("tags") or ["FAISS Vector Match", "Offline Image Embedding"],
        "semanticRationale": rationale,
        "thumbnails": {"2020": img_url, "2022": img_url, "2024": img_url},
        "temporalSequence": [{
            "year": "Archive",
            "date": "Indexed scene",
            "thumb": img_url,
            "quality": "Unknown",
            "status": "Matched Scene",
        }],
        "changeAnalysis": None,
        "reviewStatus": None,
    }


def candidates_from_vector_matches(
    db_conn,
    matches: Iterable[Dict[str, Any]],
    query_label: str,
    min_score: float,
    mode: str,
) -> List[Dict[str, Any]]:
    """
    Groups FAISS matches into locations, so repeated year/images for the same
    place appear as one ranked location instead of noisy duplicate cards.
    """
    grouped: Dict[str, Dict[str, Any]] = {}

    for match in matches:
        raw_score = float(match.get("score", 0.0))
        if raw_score < min_score:
            continue

        ui_score = normalize_similarity_score(raw_score)
        filename = match.get("filename", "")
        match_title = match.get("title", "")
        loc_id = location_id_from_text(f"{filename} {match_title}")
        group_id = loc_id or f"img-{match.get('image_id', filename)}"

        existing = grouped.get(group_id)
        if existing and existing["_rawScore"] >= raw_score:
            existing["_matchCount"] += 1
            continue

        if loc_id:
            candidate = database.get_location_details(db_conn, loc_id)
            if not candidate or "id" not in candidate:
                candidate = dynamic_candidate_from_match(match, ui_score, "")
            else:
                candidate = dict(candidate)
        else:
            candidate = dynamic_candidate_from_match(match, ui_score, "")

        candidate["matchScore"] = ui_score
        candidate["semanticRationale"] = (
            f"{mode} vector match ({ui_score}%) for '{query_label}'. "
            f"Nearest indexed scene: {filename}."
        )
        candidate["_rawScore"] = raw_score
        candidate["_matchCount"] = (existing or {}).get("_matchCount", 0) + 1
        grouped[group_id] = candidate

    candidates = list(grouped.values())
    candidates.sort(key=lambda c: (c.get("_matchCount", 1), c.get("_rawScore", 0.0)), reverse=True)
    for candidate in candidates:
        if candidate.get("_matchCount", 1) > 1:
            candidate["semanticRationale"] += f" {candidate['_matchCount']} indexed images from this location supported the match."
        candidate.pop("_rawScore", None)
        candidate.pop("_matchCount", None)
    return candidates


def execute_candidate_search(
    db_conn,
    ai_service: AIService,
    query: Optional[str] = None,
    source: str = "all",
    cloud_max: float = 30.0,
    result_type: str = "all"
) -> Dict[str, Any]:
    """
    Retrieves candidate locations from SQLite database and FAISS vector index,
    calculates match scores based on RemoteCLIP FAISS vector similarity,
    and returns dynamically formatted candidate cards for the UI.
    """
    clean_query = (query or "").strip().lower()

    candidates = []

    # Execute FAISS text vector search if query present. Do not pre-seed the
    # five demo locations; that made weak/no vector results look like matches.
    if clean_query and ai_service.is_available:
        try:
            vector_results = ai_service.search_by_text(clean_query, top_k=10)
            candidates = candidates_from_vector_matches(
                db_conn=db_conn,
                matches=vector_results,
                query_label=query or "",
                min_score=TEXT_MIN_SCORE,
                mode="Text intent",
            )
        except Exception as e:
            logger.warning(f"FAISS search error: {e}")

    # Keyword database matching fallback if query provided but candidates empty or specific location requested
    if clean_query:
        existing_ids = {c["id"] for c in candidates if "id" in c}
        for loc_id in database.list_locations(db_conn):
            if loc_id in existing_ids:
                continue
            loc = database.get_location_details(db_conn, loc_id)
            if not loc or not isinstance(loc, dict) or "id" not in loc:
                continue
            searchable_text = f"{loc.get('title', '')} {loc.get('region', '')} {' '.join(loc.get('tags', []))} {loc.get('semanticRationale', '')}".lower()
            if any(term in searchable_text for term in clean_query.split()):
                c = dict(loc)
                c["matchScore"] = 90
                c["semanticRationale"] = f"Text intent match (90% confidence) for '{query}'. Location: {loc.get('title')}."
                c["reviewStatus"] = database.get_analyst_review(db_conn, loc_id)
                candidates.append(c)

    # Empty query is the only case where browsing the local candidate archive
    # should show all seeded demo records.
    if not clean_query:
        for loc_id in database.list_locations(db_conn):
            loc = database.get_location_details(db_conn, loc_id)
            if loc and isinstance(loc, dict) and "id" in loc:
                c = dict(loc)
                c["reviewStatus"] = database.get_analyst_review(db_conn, loc_id)
                candidates.append(c)

    candidates.sort(key=lambda c: c.get("matchScore", 0), reverse=True)

    return {
        "success": True,
        "totalCount": len(candidates),
        "candidates": candidates,
        "aiStatus": ai_service.status_message
    }
