"""
AETHER - database.py
---------------------
Scans data/before, data/after, and data/uploads folders for satellite images,
extracts basic metadata, and stores it in a local SQLite database (aether.db).
Manages scenes, changes, locations metadata, and persistent analyst reviews.
Designed to run fully offline (no cloud/API calls).

Run this from inside the AETHER/ root folder:
    python database.py

Re-running it is safe: already-indexed files are skipped
(incremental ingestion), so new images added later get picked up
without rebuilding everything.
"""

import os
import re
import json
import sqlite3
import hashlib
from datetime import datetime, timezone

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[warn] Pillow not installed. Run: pip install pillow")
    print("       Continuing without image width/height metadata.\n")

# ---------- Config ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(ROOT_DIR, "AETHER", "data")
DB_PATH = os.path.join(BASE_DIR, "aether.db")
VALID_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tif", ".tiff")
PERIOD_FOLDERS = ["before", "after", "uploads"]

# ---------- Database setup ----------
def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scenes (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL UNIQUE,
            location TEXT,
            latitude REAL,
            longitude REAL,
            capture_date TEXT,
            period TEXT CHECK(period IN ('before', 'after', 'uploads')),
            sensor TEXT DEFAULT 'unknown',
            width INTEGER,
            height INTEGER,
            quality TEXT DEFAULT 'unknown'
                CHECK(quality IN ('good', 'fair', 'poor', 'unknown')),
            embedding BLOB,
            indexed_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS changes (
            id TEXT PRIMARY KEY,
            before_scene_id TEXT NOT NULL,
            after_scene_id TEXT NOT NULL,
            location TEXT,
            change_type TEXT,
            description TEXT,
            confidence REAL,
            affected_area TEXT,
            region_bbox TEXT,

            cloud_ok INTEGER DEFAULT 1,
            haze_ok INTEGER DEFAULT 1,
            alignment_ok INTEGER DEFAULT 1,
            season_ok INTEGER DEFAULT 1,
            sensor_ok INTEGER DEFAULT 1,
            false_alarm_risk TEXT DEFAULT 'unknown'
                CHECK(false_alarm_risk IN ('low', 'medium', 'high', 'unknown')),

            processing_history TEXT,
            source TEXT DEFAULT 'manual',
            analyst_status TEXT DEFAULT 'pending'
                CHECK(analyst_status IN ('pending', 'confirmed', 'rejected', 'flagged')),
            created_at TEXT NOT NULL,
            FOREIGN KEY (before_scene_id) REFERENCES scenes(id),
            FOREIGN KEY (after_scene_id) REFERENCES scenes(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            region TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            dms TEXT,
            mgrs TEXT,
            utm TEXT,
            bounds_json TEXT,
            source TEXT,
            sensor TEXT,
            resolution TEXT,
            sun_zenith TEXT,
            cloud_cover TEXT,
            match_score INTEGER DEFAULT 80,
            tags_json TEXT,
            semantic_rationale TEXT,
            thumbnails_json TEXT,
            temporal_sequence_json TEXT,
            change_analysis_json TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS analyst_reviews (
            id TEXT PRIMARY KEY,
            location_id TEXT NOT NULL UNIQUE,
            decision TEXT NOT NULL CHECK(decision IN ('confirmed', 'rejected', 'flagged', 'pending')),
            analyst_id TEXT NOT NULL,
            notes TEXT,
            audit_id TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    _migrate_schema(conn)


def _migrate_schema(conn):
    """
    Adds any columns that were introduced after a table already existed.
    """
    expected = {
        "scenes": {
            "quality": "TEXT DEFAULT 'unknown'",
            "latitude": "REAL",
            "longitude": "REAL",
        },
        "changes": {
            "affected_area": "TEXT",
            "region_bbox": "TEXT",
            "cloud_ok": "INTEGER DEFAULT 1",
            "haze_ok": "INTEGER DEFAULT 1",
            "alignment_ok": "INTEGER DEFAULT 1",
            "season_ok": "INTEGER DEFAULT 1",
            "sensor_ok": "INTEGER DEFAULT 1",
            "false_alarm_risk": "TEXT DEFAULT 'unknown'",
            "processing_history": "TEXT",
        },
    }
    cur = conn.cursor()
    for table, columns in expected.items():
        cur.execute(f"PRAGMA table_info({table})")
        existing_cols = {row[1] for row in cur.fetchall()}
        for col_name, col_def in columns.items():
            if col_name not in existing_cols:
                print(f"[migrate] adding column '{col_name}' to '{table}'")
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
    conn.commit()


def make_scene_id(filepath):
    """Stable unique id derived from the file path."""
    return hashlib.sha1(filepath.encode("utf-8")).hexdigest()[:16]


DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")
SENSOR_PATTERN = re.compile(r"(Sentinel-\d[A-Za-z]*|Landsat-\d*)", re.IGNORECASE)
LEVEL_PATTERN = re.compile(r"(L1C|L2A)", re.IGNORECASE)


def parse_scene_info(filename):
    """
    Parses location, date, and sensor from filename.
    """
    name = os.path.splitext(filename)[0]

    loc_match = re.match(r"^([a-zA-Z\-]+)_", name)
    date_match = DATE_PATTERN.search(name)
    sensor_match = SENSOR_PATTERN.search(name)
    level_match = LEVEL_PATTERN.search(name)

    location = loc_match.group(1) if loc_match else None
    date_str = date_match.group(1) if date_match else None

    sensor = None
    if sensor_match:
        sensor = sensor_match.group(1)
        if level_match:
            sensor += f" ({level_match.group(1).upper()})"

    return location, date_str, sensor


def get_image_dimensions(filepath):
    if not PIL_AVAILABLE:
        return None, None
    try:
        with Image.open(filepath) as img:
            return img.width, img.height
    except Exception as e:
        print(f"[warn] Could not read dimensions for {filepath}: {e}")
        return None, None


def infer_coords_from_filename(filename: str, location: str = "") -> tuple:
    name = (filename + " " + (location or "")).lower()
    if "jammu" in name:
        return 32.7266, 74.8570
    elif "kashmir" in name or "srinagar" in name:
        return 34.0837, 74.7973
    elif "kargil" in name:
        return 34.5539, 76.1349
    elif "river" in name or "delhi" in name or "yamuna" in name:
        return 28.5450, 77.3100
    elif "highway" in name or "gurugram" in name:
        return 28.4850, 77.0250
    elif "water" in name or "osman" in name or "hyderabad" in name:
        return 17.3780, 78.3000
    elif "industry" in name or "gujarat" in name or "kutch" in name:
        return 22.7600, 69.7200
    elif "cleared" in name or "haryana" in name:
        return 28.3150, 77.0450
    return 34.5539, 76.1349


def scan_and_index(conn, data_folder=DATA_DIR):
    cur = conn.cursor()
    added, skipped = 0, 0

    for period in PERIOD_FOLDERS:
        folder = os.path.join(data_folder, period)
        if not os.path.isdir(folder):
            continue

        for filename in sorted(os.listdir(folder)):
            if not filename.lower().endswith(VALID_EXTENSIONS):
                continue

            filepath = os.path.join(folder, filename)
            scene_id = make_scene_id(filepath)

            location, date_str, sensor = parse_scene_info(filename)
            lat, lon = infer_coords_from_filename(filename, location)
            width, height = get_image_dimensions(filepath)

            cur.execute("SELECT 1 FROM scenes WHERE id = ?", (scene_id,))
            if cur.fetchone():
                cur.execute("UPDATE scenes SET latitude = ?, longitude = ? WHERE id = ?", (lat, lon, scene_id))
                skipped += 1
                continue

            cur.execute("""
                INSERT INTO scenes
                (id, filename, filepath, location, latitude, longitude, capture_date, period,
                 sensor, width, height, embedding, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scene_id,
                filename,
                filepath,
                location,
                lat,
                lon,
                date_str,
                period if period in ("before", "after") else "before",
                sensor or "Sentinel-2",
                width,
                height,
                None,
                datetime.now(timezone.utc).isoformat()
            ))
            added += 1
            print(f"[indexed] {period}/{filename} (location={location}, lat={lat}, lon={lon})")

    # Update any legacy scenes missing coordinates
    cur.execute("SELECT id, filename, location FROM scenes WHERE latitude IS NULL OR longitude IS NULL OR latitude = 0.0")
    for row in cur.fetchall():
        sid, fn, loc = row
        l_lat, l_lon = infer_coords_from_filename(fn, loc)
        cur.execute("UPDATE scenes SET latitude = ?, longitude = ? WHERE id = ?", (l_lat, l_lon, sid))

    conn.commit()
    print(f"Index complete: {added} new scene(s) added, {skipped} skipped.")


def get_scene_id(conn, location, date_str, period):
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM scenes
        WHERE location = ? AND capture_date = ? AND period = ?
    """, (location, date_str, period))
    row = cur.fetchone()
    return row[0] if row else None


def add_change(conn, location, before_date, after_date, change_type,
                description, confidence=None, source="manual",
                affected_area=None, region_bbox=None,
                cloud_ok=1, haze_ok=1, alignment_ok=1,
                season_ok=1, sensor_ok=1, false_alarm_risk="unknown",
                processing_history=None):
    before_id = get_scene_id(conn, location, before_date, "before")
    after_id = get_scene_id(conn, location, after_date, "after")

    if not before_id or not after_id:
        print(f"[warn] Scene(s) missing for location='{location}' before={before_date} after={after_date}.")

    change_id = hashlib.sha1(
        f"{location}-{before_date}-{after_date}-{change_type}".encode("utf-8")
    ).hexdigest()[:16]

    conn.execute("""
        INSERT OR REPLACE INTO changes
        (id, before_scene_id, after_scene_id, location, change_type,
         description, confidence, affected_area, region_bbox,
         cloud_ok, haze_ok, alignment_ok, season_ok, sensor_ok,
         false_alarm_risk, processing_history, source, analyst_status,
         created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (
        change_id, before_id or "legacy_before", after_id or "legacy_after",
        location, change_type, description, confidence, affected_area, region_bbox,
        cloud_ok, haze_ok, alignment_ok, season_ok, sensor_ok,
        false_alarm_risk, processing_history, source,
        datetime.now(timezone.utc).isoformat()
    ))
    conn.commit()
    return change_id


def set_analyst_status(conn, change_id, status):
    if status not in ("confirmed", "rejected", "flagged", "pending"):
        print(f"[error] Invalid status '{status}'.")
        return
    conn.execute(
        "UPDATE changes SET analyst_status = ? WHERE id = ?",
        (status, change_id)
    )
    conn.commit()


def save_analyst_review(conn, location_id, decision, analyst_id, notes, audit_id=None):
    if decision not in ("confirmed", "rejected", "flagged", "pending"):
        raise ValueError(f"Invalid review decision: {decision}")
    
    if not audit_id:
        audit_id = f"REV-{int(datetime.now(timezone.utc).timestamp())}"

    review_id = hashlib.sha1(f"{location_id}-{decision}".encode("utf-8")).hexdigest()[:16]
    now_iso = datetime.now(timezone.utc).isoformat()

    conn.execute("""
        INSERT OR REPLACE INTO analyst_reviews
        (id, location_id, decision, analyst_id, notes, audit_id, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (review_id, location_id, decision, analyst_id, notes, audit_id, now_iso))

    # Also update changes table status if present
    conn.execute(
        "UPDATE changes SET analyst_status = ? WHERE location = ?",
        (decision, location_id)
    )
    conn.commit()
    return {
        "id": review_id,
        "locationId": location_id,
        "decision": decision,
        "analystId": analyst_id,
        "notes": notes,
        "auditId": audit_id,
        "timestamp": now_iso
    }


def get_analyst_review(conn, location_id):
    cur = conn.cursor()
    cur.execute("SELECT * FROM analyst_reviews WHERE location_id = ?", (location_id,))
    row = cur.fetchone()
    if not row:
        return None
    cols = [d[0] for d in cur.description]
    res = dict(zip(cols, row))
    return {
        "decision": res["decision"],
        "analystId": res["analyst_id"],
        "notes": res["notes"],
        "auditId": res["audit_id"],
        "timestamp": res["timestamp"]
    }


def save_location_record(conn, loc_dict):
    loc_id = loc_dict["id"]
    coords = loc_dict.get("coordinates", {})

    conn.execute("""
        INSERT OR REPLACE INTO locations
        (id, title, region, latitude, longitude, dms, mgrs, utm,
         bounds_json, source, sensor, resolution, sun_zenith, cloud_cover,
         match_score, tags_json, semantic_rationale, thumbnails_json,
         temporal_sequence_json, change_analysis_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        loc_id,
        loc_dict.get("title", loc_id),
        loc_dict.get("region", "Unknown Region"),
        coords.get("lat"),
        coords.get("lon"),
        coords.get("dms"),
        coords.get("mgrs"),
        coords.get("utm"),
        json.dumps(loc_dict.get("bounds", [])),
        loc_dict.get("source", "Copernicus Sentinel-2"),
        loc_dict.get("sensor", "MSI (Level-2A BOA)"),
        loc_dict.get("resolution", "10m / pixel"),
        loc_dict.get("sunZenith", "30.0°"),
        loc_dict.get("cloudCover", "0.5%"),
        loc_dict.get("matchScore", 85),
        json.dumps(loc_dict.get("tags", [])),
        loc_dict.get("semanticRationale", ""),
        json.dumps(loc_dict.get("thumbnails", {})),
        json.dumps(loc_dict.get("temporalSequence", [])),
        json.dumps(loc_dict.get("changeAnalysis", {})),
        datetime.now(timezone.utc).isoformat()
    ))
    conn.commit()


def _row_to_dict(cur, row):
    if row is None:
        return None
    columns = [d[0] for d in cur.description]
    return dict(zip(columns, row))


def get_scene(conn, scene_id):
    cur = conn.cursor()
    cur.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,))
    return _row_to_dict(cur, cur.fetchone())


def get_change(conn, change_id):
    cur = conn.cursor()
    cur.execute("SELECT * FROM changes WHERE id = ?", (change_id,))
    return _row_to_dict(cur, cur.fetchone())


def list_locations(conn):
    cur = conn.cursor()
    cur.execute("SELECT id FROM locations ORDER BY title")
    locs = [row[0] for row in cur.fetchall()]
    if not locs:
        cur.execute("SELECT DISTINCT location FROM scenes WHERE location IS NOT NULL ORDER BY location")
        locs = [row[0] for row in cur.fetchall()]
    return locs


def get_location_details(conn, location):
    cur = conn.cursor()
    cur.execute("SELECT * FROM locations WHERE id = ?", (location,))
    row = cur.fetchone()

    review = get_analyst_review(conn, location)

    if row:
        raw = _row_to_dict(cur, row)
        return {
            "id": raw["id"],
            "title": raw["title"],
            "region": raw["region"],
            "coordinates": {
                "lat": raw["latitude"],
                "lon": raw["longitude"],
                "dms": raw["dms"],
                "mgrs": raw["mgrs"],
                "utm": raw["utm"]
            },
            "bounds": json.loads(raw["bounds_json"] or "[]"),
            "source": raw["source"],
            "sensor": raw["sensor"],
            "resolution": raw["resolution"],
            "sunZenith": raw["sun_zenith"],
            "cloudCover": raw["cloud_cover"],
            "matchScore": raw["match_score"],
            "tags": json.loads(raw["tags_json"] or "[]"),
            "semanticRationale": raw["semantic_rationale"],
            "thumbnails": json.loads(raw["thumbnails_json"] or "{}"),
            "temporalSequence": json.loads(raw["temporal_sequence_json"] or "[]"),
            "changeAnalysis": json.loads(raw["change_analysis_json"] or "{}"),
            "reviewStatus": review
        }

    # Fallback to scenes / changes tables if not in locations table
    cur.execute("SELECT * FROM scenes WHERE location = ? ORDER BY period, capture_date", (location,))
    scenes = [_row_to_dict(cur, r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM changes WHERE location = ? ORDER BY created_at", (location,))
    changes = [_row_to_dict(cur, r) for r in cur.fetchall()]

    return {
        "location": location,
        "scenes": scenes,
        "changes": changes,
        "reviewStatus": review
    }


def update_scene(conn, scene_id, **fields):
    if not fields:
        return False
    if not get_scene(conn, scene_id):
        return False

    set_clause = ", ".join(f"{col} = ?" for col in fields)
    values = list(fields.values()) + [scene_id]
    conn.execute(f"UPDATE scenes SET {set_clause} WHERE id = ?", values)
    conn.commit()
    return True


def update_change(conn, change_id, **fields):
    if not fields:
        return False
    if not get_change(conn, change_id):
        return False

    set_clause = ", ".join(f"{col} = ?" for col in fields)
    values = list(fields.values()) + [change_id]
    conn.execute(f"UPDATE changes SET {set_clause} WHERE id = ?", values)
    conn.commit()
    return True


def delete_change(conn, change_id):
    if not get_change(conn, change_id):
        return False
    conn.execute("DELETE FROM changes WHERE id = ?", (change_id,))
    conn.commit()
    return True


def delete_scene(conn, scene_id, cascade=True):
    if not get_scene(conn, scene_id):
        return False

    cur = conn.cursor()
    cur.execute("SELECT id FROM changes WHERE before_scene_id = ? OR after_scene_id = ?", (scene_id, scene_id))
    dependent = [row[0] for row in cur.fetchall()]

    if dependent and not cascade:
        return False

    if dependent:
        cur.execute("DELETE FROM changes WHERE before_scene_id = ? OR after_scene_id = ?", (scene_id, scene_id))

    cur.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))
    conn.commit()
    return True


def seed_default_dataset(conn):
    """
    Seeds initial candidate locations and scenes into SQLite if not already present.
    """
    init_db(conn)
    cur = conn.cursor()

    locations_data = [
        {
            "id": "loc-river",
            "title": "Yamuna River Corridor - Sector 4B",
            "region": "Delhi-NCR River Basin, India",
            "coordinates": {
                "lat": 28.5450,
                "lon": 77.3100,
                "dms": "28°32'42\" N, 77°18'36\" E",
                "mgrs": "43RGR303576",
                "utm": "Zone 43R 725680m E 3159980m N"
            },
            "bounds": [[28.5275, 77.2925], [28.5625, 77.3275]],
            "source": "Copernicus Sentinel-2",
            "sensor": "MSI (Level-2A BOA)",
            "resolution": "10m / pixel",
            "sunZenith": "32.1°",
            "cloudCover": "0.3%",
            "matchScore": 94,
            "tags": ["River Corridor", "Structural Emergence", "Concrete Pier", "Anthropogenic Built-up"],
            "semanticRationale": "High density of newly emergent rectilinear spectral signatures adjacent to river meander. Significant delta in Normalized Difference Built-up Index (NDBI).",
            "thumbnails": {
                "2020": "/imagery/loc-river-2020.jpg",
                "2022": "/imagery/loc-river-2022.jpg",
                "2024": "/imagery/loc-river-2024.jpg"
            },
            "temporalSequence": [
                { "year": "2020", "date": "14 March 2020", "granule": "S2A_MSIL2A_20200314T054651_N0214_R119_T43RGR", "thumb": "/imagery/loc-river-2020.jpg", "quality": "Cloud Free (0.1%)", "status": "Baseline" },
                { "year": "2022", "date": "18 May 2022", "granule": "S2B_MSIL2A_20220518T054649_N0400_R119_T43RGR", "thumb": "/imagery/loc-river-2022.jpg", "quality": "Cloud Free (0.2%)", "status": "Intermediate" },
                { "year": "2024", "date": "22 August 2024", "granule": "S2B_MSIL2A_20240822T054649_N0500_R119_T43RGR", "thumb": "/imagery/loc-river-2024.jpg", "quality": "Cloud Free (0.3%)", "status": "Current" }
            ],
            "changeAnalysis": {
                "beforeYear": "2020",
                "beforeDate": "14 March 2020",
                "beforeImage": "/imagery/loc-river-2020.jpg",
                "afterYear": "2024",
                "afterDate": "22 August 2024",
                "afterImage": "/imagery/loc-river-2024.jpg",
                "maskImage": "/imagery/loc-river-mask.svg",
                "confidenceScore": 94,
                "changeType": "Structural Footprint & Construction",
                "affectedArea": "~14,250 m²",
                "summary": "A new structural footprint appears in the selected area between the two acquisition dates. Rectilinear roof signatures and bridge pier concrete foundations confirmed.",
                "detectedChanges": [
                    { "label": "Construction", "confidence": 94, "category": "Anthropogenic / Structural", "severity": "high", "description": "Newly erected multi-story structural foundations and hardstand." },
                    { "label": "Road Development", "confidence": 82, "category": "Linear Infrastructure", "severity": "medium", "description": "Asphalt access spur connecting east embankment to central pier." },
                    { "label": "Vegetation Variation", "confidence": 58, "category": "Environmental / Phenological", "severity": "low", "description": "Seasonal scrub grass density variation along river levee." }
                ],
                "falseAlarmAnalysis": {
                    "checks": [
                        { "label": "Image alignment verified", "detail": "Sub-pixel phase correlation error: 0.14 px (<0.20 px tolerance)", "passed": True },
                        { "label": "Cloud & shadow contamination low", "detail": "Sen2Cor SCL cloud probability: 0.3%, shadow mask clear", "passed": True },
                        { "label": "Radiometric calibration confirmed", "detail": "Bottom-Of-Atmosphere (BOA) surface reflectance normalized", "passed": True },
                        { "label": "Multi-temporal persistence", "detail": "Change persists across 3 consecutive dry-season sensor passes", "passed": True },
                        { "label": "Solar geometry divergence checked", "detail": "Sun zenith angle delta: 4.2°, shadow vector distortion eliminated", "passed": True }
                    ],
                    "riskLevel": "Low",
                    "riskScore": "0.06 / 1.00",
                    "verdict": "Genuine Anthropogenic Structural Change"
                },
                "provenance": {
                    "beforeGranule": "S2A_MSIL2A_20200314T054651_N0214_R119_T43RGR",
                    "afterGranule": "S2B_MSIL2A_20240822T054649_N0500_R119_T43RGR",
                    "sensor": "Copernicus Sentinel-2 MSI (Level-2A BOA)",
                    "spatialResolution": "10m GSD (B2, B3, B4, B8)",
                    "registrationMethod": "AETHER Phase-Correlation Sub-Pixel Orthorectification",
                    "vectorModel": "AETHER-GeoEmbed-v2 (ViT-H/14-EO Multi-Spectral)",
                    "sha256Digest": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "archiveNode": "Local Offline Node - Zone North Alpha"
                }
            }
        },
        {
            "id": "loc-highway",
            "title": "South-West Corridor - Arterial Expressway",
            "region": "Gurugram-Dwarka Link, India",
            "coordinates": {
                "lat": 28.4850,
                "lon": 77.0250,
                "dms": "28°29'06\" N, 77°01'30\" E",
                "mgrs": "43RGR023512",
                "utm": "Zone 43R 698240m E 3152890m N"
            },
            "bounds": [[28.4675, 77.0075], [28.5025, 77.0425]],
            "source": "Copernicus Sentinel-2",
            "sensor": "MSI (Level-2A BOA)",
            "resolution": "10m / pixel",
            "sunZenith": "34.8°",
            "cloudCover": "0.5%",
            "matchScore": 89,
            "tags": ["Linear Infrastructure", "Expressway Corridor", "Earthworks", "Pavement"],
            "semanticRationale": "Linear continuous spectral signature through open terrain with high contrast asphalt/concrete reflectance characteristics.",
            "thumbnails": {
                "2020": "/imagery/loc-highway-2020.jpg",
                "2022": "/imagery/loc-highway-2022.jpg",
                "2024": "/imagery/loc-highway-2024.jpg"
            },
            "temporalSequence": [
                { "year": "2020", "date": "21 February 2020", "granule": "S2A_MSIL2A_20200221T054651_N0214_R119_T43RGR", "thumb": "/imagery/loc-highway-2020.jpg", "quality": "Cloud Free (0.2%)", "status": "Baseline" },
                { "year": "2022", "date": "04 April 2022", "granule": "S2B_MSIL2A_20220404T054649_N0400_R119_T43RGR", "thumb": "/imagery/loc-highway-2022.jpg", "quality": "Cloud Free (0.4%)", "status": "Earthworks" },
                { "year": "2024", "date": "12 June 2024", "granule": "S2B_MSIL2A_20240612T054649_N0500_R119_T43RGR", "thumb": "/imagery/loc-highway-2024.jpg", "quality": "Cloud Free (0.5%)", "status": "Paved Corridor" }
            ],
            "changeAnalysis": {
                "beforeYear": "2020",
                "beforeDate": "21 February 2020",
                "beforeImage": "/imagery/loc-highway-2020.jpg",
                "afterYear": "2024",
                "afterDate": "12 June 2024",
                "afterImage": "/imagery/loc-highway-2024.jpg",
                "maskImage": "/imagery/loc-highway-mask.svg",
                "confidenceScore": 88,
                "changeType": "Linear Transportation Corridor",
                "affectedArea": "~48,600 m²",
                "summary": "New multi-lane paved transportation corridor cutting across previously open semi-arid terrain.",
                "detectedChanges": [
                    { "label": "Road Development", "confidence": 91, "category": "Linear Infrastructure", "severity": "high", "description": "Dual-carriageway paved arterial with grade-separated interchange." },
                    { "label": "Ground Clearing", "confidence": 84, "category": "Land Cover Transformation", "severity": "medium", "description": "Right-of-way earthworks and embankment stabilization." },
                    { "label": "Vegetation Variation", "confidence": 45, "category": "Environmental", "severity": "low", "description": "Roadside ditch grass growth." }
                ],
                "falseAlarmAnalysis": {
                    "checks": [
                        { "label": "Image alignment verified", "detail": "Co-registration RMS error: 0.16 px", "passed": True },
                        { "label": "Cloud & shadow contamination low", "detail": "Cloud probability: 0.5%", "passed": True },
                        { "label": "Radiometric calibration confirmed", "detail": "BOA Surface reflectance calibrated", "passed": True },
                        { "label": "Linear structural continuity verified", "detail": "Hough transform confirms high directional coherence", "passed": True }
                    ],
                    "riskLevel": "Low",
                    "riskScore": "0.09 / 1.00",
                    "verdict": "Confirmed Linear Arterial Expansion"
                },
                "provenance": {
                    "beforeGranule": "S2A_MSIL2A_20200221T054651_N0214_R119_T43RGR",
                    "afterGranule": "S2B_MSIL2A_20240612T054649_N0500_R119_T43RGR",
                    "sensor": "Copernicus Sentinel-2 MSI",
                    "spatialResolution": "10m GSD",
                    "registrationMethod": "AETHER Phase-Correlation Sub-Pixel Orthorectification",
                    "vectorModel": "AETHER-GeoEmbed-v2",
                    "sha256Digest": "f87a32b109dc44a983fe21cb0a43e765109b832104fa231bc78912304910fabc",
                    "archiveNode": "Local Offline Node - Zone North Alpha"
                }
            }
        },
        {
            "id": "loc-water",
            "title": "Osman Sagar Catchment & Reservoir",
            "region": "Musi Basin, Telangana, India",
            "coordinates": {
                "lat": 17.3780,
                "lon": 78.3000,
                "dms": "17°22'40\" N, 78°18'00\" E",
                "mgrs": "44QMD412218",
                "utm": "Zone 44Q 214150m E 1923410m N"
            },
            "bounds": [[17.3590, 78.2810], [17.3970, 78.3190]],
            "source": "Copernicus Sentinel-2",
            "sensor": "MSI (Level-2A BOA)",
            "resolution": "10m / pixel",
            "sunZenith": "28.4°",
            "cloudCover": "0.2%",
            "matchScore": 86,
            "tags": ["Water Extent", "MNDWI Index", "Reservoir Shoreline", "Hydrographic Shift"],
            "semanticRationale": "Pronounced shift in Modified Normalized Difference Water Index (MNDWI) showing seasonal and multi-year shoreline contour dynamics.",
            "thumbnails": {
                "2020": "/imagery/loc-water-2020.jpg",
                "2022": "/imagery/loc-water-2022.jpg",
                "2024": "/imagery/loc-water-2024.jpg"
            },
            "temporalSequence": [
                { "year": "2020", "date": "08 January 2020", "granule": "S2A_MSIL2A_20200108T051831_N0213_R091_T44QMD", "thumb": "/imagery/loc-water-2020.jpg", "quality": "Cloud Free (0.1%)", "status": "High Water Level" },
                { "year": "2022", "date": "14 March 2022", "granule": "S2B_MSIL2A_20220314T051829_N0400_R091_T44QMD", "thumb": "/imagery/loc-water-2022.jpg", "quality": "Cloud Free (0.1%)", "status": "Intermediate" },
                { "year": "2024", "date": "29 May 2024", "granule": "S2B_MSIL2A_20240529T051829_N0500_R091_T44QMD", "thumb": "/imagery/loc-water-2024.jpg", "quality": "Cloud Free (0.2%)", "status": "Receded Shoreline" }
            ],
            "changeAnalysis": {
                "beforeYear": "2020",
                "beforeDate": "08 January 2020",
                "beforeImage": "/imagery/loc-water-2020.jpg",
                "afterYear": "2024",
                "afterDate": "29 May 2024",
                "afterImage": "/imagery/loc-water-2024.jpg",
                "maskImage": "/imagery/loc-water-mask.svg",
                "confidenceScore": 84,
                "changeType": "Hydrological Surface Extent",
                "affectedArea": "~126,000 m²",
                "summary": "Significant surface water extent shrinkage along shallow reservoir embayment with emergent exposed silt bed.",
                "detectedChanges": [
                    { "label": "Waterbody Contraction", "confidence": 88, "category": "Hydrographic", "severity": "high", "description": "Recession of open water surface area exposing shoreline sediment." },
                    { "label": "Sediment / Silt Deposition", "confidence": 79, "category": "Geomorphological", "severity": "medium", "description": "Emergence of low-albedo dried lakebed deposits." }
                ],
                "falseAlarmAnalysis": {
                    "checks": [
                        { "label": "Image alignment verified", "detail": "Sub-pixel co-registration RMS: 0.12 px", "passed": True },
                        { "label": "Cloud & shadow contamination low", "detail": "Cloud probability: 0.2%", "passed": True },
                        { "label": "SWIR water absorption confirmed", "detail": "Band 11 (1610nm) confirms strong water-land boundary separation", "passed": True }
                    ],
                    "riskLevel": "Low",
                    "riskScore": "0.11 / 1.00",
                    "verdict": "Confirmed Hydrographic Variation"
                },
                "provenance": {
                    "beforeGranule": "S2A_MSIL2A_20200108T051831_N0213_R091_T44QMD",
                    "afterGranule": "S2B_MSIL2A_20240529T051829_N0500_R091_T44QMD",
                    "sensor": "Copernicus Sentinel-2 MSI",
                    "spatialResolution": "10m / 20m SWIR",
                    "registrationMethod": "AETHER Phase-Correlation Sub-Pixel Orthorectification",
                    "vectorModel": "AETHER-GeoEmbed-v2",
                    "sha256Digest": "a12b34c56d78e90f1234567890abcdef1234567890abcdef1234567890abcdef",
                    "archiveNode": "Local Offline Node - Zone South Beta"
                }
            }
        },
        {
            "id": "loc-industry",
            "title": "Port Maritime & Industrial Logistics Yard",
            "region": "Gulf of Kutch, Gujarat, India",
            "coordinates": {
                "lat": 22.7600,
                "lon": 69.7200,
                "dms": "22°45'36\" N, 69°43'12\" E",
                "mgrs": "42QVL732168",
                "utm": "Zone 42Q 573890m E 2516420m N"
            },
            "bounds": [[22.7425, 69.7025], [22.7775, 69.7375]],
            "source": "Copernicus Sentinel-2",
            "sensor": "MSI (Level-2A BOA)",
            "resolution": "10m / pixel",
            "sunZenith": "31.6°",
            "cloudCover": "0.4%",
            "matchScore": 82,
            "tags": ["Industrial Logistics", "Terminal Yard", "Storage Tanks", "Harbor Infrastructure"],
            "semanticRationale": "High geometric regularity in spectral reflectance indicative of industrial warehouse rooftops, storage tanks, and container storage pavements.",
            "thumbnails": {
                "2020": "/imagery/loc-industry-2020.jpg",
                "2022": "/imagery/loc-industry-2022.jpg",
                "2024": "/imagery/loc-industry-2024.jpg"
            },
            "temporalSequence": [
                { "year": "2020", "date": "19 January 2020", "granule": "S2A_MSIL2A_20200119T055101_N0214_R033_T42QVL", "thumb": "/imagery/loc-industry-2020.jpg", "quality": "Cloud Free (0.3%)", "status": "Open Ground" },
                { "year": "2022", "date": "25 April 2022", "granule": "S2B_MSIL2A_20220425T055059_N0400_R033_T42QVL", "thumb": "/imagery/loc-industry-2022.jpg", "quality": "Cloud Free (0.2%)", "status": "Construction" },
                { "year": "2024", "date": "08 July 2024", "granule": "S2B_MSIL2A_20240708T055059_N0500_R033_T42QVL", "thumb": "/imagery/loc-industry-2024.jpg", "quality": "Cloud Free (0.4%)", "status": "Operational Yards" }
            ],
            "changeAnalysis": {
                "beforeYear": "2020",
                "beforeDate": "19 January 2020",
                "beforeImage": "/imagery/loc-industry-2020.jpg",
                "afterYear": "2024",
                "afterDate": "08 July 2024",
                "afterImage": "/imagery/loc-industry-2024.jpg",
                "maskImage": "/imagery/loc-industry-mask.svg",
                "confidenceScore": 87,
                "changeType": "Heavy Industrial Facilities",
                "affectedArea": "~31,400 m²",
                "summary": "Erection of new industrial handling warehouses and bulk liquid storage tank cluster.",
                "detectedChanges": [
                    { "label": "Industrial Sheds", "confidence": 89, "category": "Anthropogenic", "severity": "high", "description": "High-reflectance metal roof sheeting installed over logistics bay." },
                    { "label": "Storage Tank Battery", "confidence": 85, "category": "Specialized Infrastructure", "severity": "high", "description": "Two circular bulk liquid containment vessels installed." }
                ],
                "falseAlarmAnalysis": {
                    "checks": [
                        { "label": "Image alignment verified", "detail": "Co-registration RMS: 0.15 px", "passed": True },
                        { "label": "Cloud & shadow contamination low", "detail": "Cloud probability: 0.4%", "passed": True },
                        { "label": "Specular reflectance verified", "detail": "Polarized SAR cross-check confirms high double-bounce signature", "passed": True }
                    ],
                    "riskLevel": "Low",
                    "riskScore": "0.07 / 1.00",
                    "verdict": "Confirmed Industrial Expansion"
                },
                "provenance": {
                    "beforeGranule": "S2A_MSIL2A_20200119T055101_N0214_R033_T42QVL",
                    "afterGranule": "S2B_MSIL2A_20240708T055059_N0500_R033_T42QVL",
                    "sensor": "Copernicus Sentinel-2 MSI",
                    "spatialResolution": "10m GSD",
                    "registrationMethod": "AETHER Phase-Correlation Sub-Pixel Orthorectification",
                    "vectorModel": "AETHER-GeoEmbed-v2",
                    "sha256Digest": "3344556677889900aabbccddeeff0011223344556677889900aabbccddeeff00",
                    "archiveNode": "Local Offline Node - Zone West Gamma"
                }
            }
        },
        {
            "id": "loc-cleared",
            "title": "Southern Buffer Fringe - Land Clearing",
            "region": "Aravalli Range Buffer, Haryana, India",
            "coordinates": {
                "lat": 28.3150,
                "lon": 77.0450,
                "dms": "28°18'54\" N, 77°02'42\" E",
                "mgrs": "43RGR041324",
                "utm": "Zone 43R 700120m E 3133980m N"
            },
            "bounds": [[28.2975, 77.0275], [28.3325, 77.0625]],
            "source": "Copernicus Sentinel-2",
            "sensor": "MSI (Level-2A BOA)",
            "resolution": "10m / pixel",
            "sunZenith": "33.2°",
            "cloudCover": "0.3%",
            "matchScore": 78,
            "tags": ["Land Clearing", "NDVI Drop", "Open Land", "Settlement Fringe"],
            "semanticRationale": "Sharp drop in Normalized Difference Vegetation Index (NDVI) alongside exposed bare soil reflectance adjoining village settlement perimeter.",
            "thumbnails": {
                "2020": "/imagery/loc-cleared-2020.jpg",
                "2022": "/imagery/loc-cleared-2022.jpg",
                "2024": "/imagery/loc-cleared-2024.jpg"
            },
            "temporalSequence": [
                { "year": "2020", "date": "11 February 2020", "granule": "S2A_MSIL2A_20200211T054651_N0214_R119_T43RGR", "thumb": "/imagery/loc-cleared-2020.jpg", "quality": "Cloud Free (0.1%)", "status": "Dense Canopy" },
                { "year": "2022", "date": "20 March 2022", "granule": "S2B_MSIL2A_20220320T054649_N0400_R119_T43RGR", "thumb": "/imagery/loc-cleared-2022.jpg", "quality": "Cloud Free (0.2%)", "status": "Partial Clearing" },
                { "year": "2024", "date": "19 April 2024", "granule": "S2B_MSIL2A_20240419T054649_N0500_R119_T43RGR", "thumb": "/imagery/loc-cleared-2024.jpg", "quality": "Cloud Free (0.3%)", "status": "Graded Ground" }
            ],
            "changeAnalysis": {
                "beforeYear": "2020",
                "beforeDate": "11 February 2020",
                "beforeImage": "/imagery/loc-cleared-2020.jpg",
                "afterYear": "2024",
                "afterDate": "19 April 2024",
                "afterImage": "/imagery/loc-cleared-2024.jpg",
                "maskImage": "/imagery/loc-cleared-mask.svg",
                "confidenceScore": 79,
                "changeType": "Land Cover Alteration",
                "affectedArea": "~22,800 m²",
                "summary": "Vegetation canopy cleared and graded for proposed peripheral development.",
                "detectedChanges": [
                    { "label": "Canopy Removal", "confidence": 84, "category": "Vegetation Transformation", "severity": "medium", "description": "Removal of mature scrub woodland canopy." },
                    { "label": "Exposed Soil Substrate", "confidence": 76, "category": "Surface Geology", "severity": "medium", "description": "Exposed bare soil with altered surface roughness." }
                ],
                "falseAlarmAnalysis": {
                    "checks": [
                        { "label": "Image alignment verified", "detail": "Sub-pixel co-registration RMS: 0.17 px", "passed": True },
                        { "label": "Cloud & shadow contamination low", "detail": "Cloud probability: 0.3%", "passed": True },
                        { "label": "Phenology baseline checked", "detail": "Baseline cross-comparison with identical seasonal dry month", "passed": True }
                    ],
                    "riskLevel": "Low",
                    "riskScore": "0.14 / 1.00",
                    "verdict": "Confirmed Vegetative Clearing"
                },
                "provenance": {
                    "beforeGranule": "S2A_MSIL2A_20200211T054651_N0214_R119_T43RGR",
                    "afterGranule": "S2B_MSIL2A_20240419T054649_N0500_R119_T43RGR",
                    "sensor": "Copernicus Sentinel-2 MSI",
                    "spatialResolution": "10m GSD",
                    "registrationMethod": "AETHER Phase-Correlation Sub-Pixel Orthorectification",
                    "vectorModel": "AETHER-GeoEmbed-v2",
                    "sha256Digest": "445566778899aabbccddeeff00112233445566778899aabbccddeeff00112233",
                    "archiveNode": "Local Offline Node - Zone North Alpha"
                }
            }
        },
        {
            "id": "loc-kargil",
            "title": "Jammu & Kashmir / Kargil Sector",
            "region": "Jammu & Kashmir, India",
            "coordinates": {
                "lat": 34.5539,
                "lon": 76.1349,
                "dms": "34°33'14\" N, 76°08'05\" E",
                "mgrs": "43WES451234",
                "utm": "Zone 43N 604120m E 3824500m N"
            },
            "bounds": [[34.5350, 76.1150], [34.5720, 76.1550]],
            "source": "Copernicus Sentinel-2",
            "sensor": "MSI (Level-2A BOA)",
            "resolution": "10m / pixel",
            "sunZenith": "38.5°",
            "cloudCover": "0.1%",
            "matchScore": 96,
            "tags": ["Jammu & Kashmir", "Mountain Settlement", "Settlement Expansion", "High Altitude Terrain", "Kashmir Corridor"],
            "semanticRationale": "Multi-temporal satellite observation of high-altitude mountain settlement in Jammu & Kashmir showing residential expansion and infrastructure build-up.",
            "thumbnails": {
                "2020": "/imagery/loc-kargil-2020.jpg",
                "2022": "/imagery/loc-kargil-2022.jpg",
                "2024": "/imagery/loc-kargil-2024.jpg"
            },
            "temporalSequence": [
                { "year": "2020", "date": "30 June 2020", "granule": "S2A_MSIL2A_20200630T054651_N0214_R119_T43WES", "thumb": "/imagery/loc-kargil-2020.jpg", "quality": "Cloud Free (0.1%)", "status": "Baseline" },
                { "year": "2022", "date": "30 June 2022", "granule": "S2B_MSIL2A_20220630T054649_N0400_R119_T43WES", "thumb": "/imagery/loc-kargil-2022.jpg", "quality": "Cloud Free (0.1%)", "status": "Intermediate" },
                { "year": "2024", "date": "30 June 2024", "granule": "S2B_MSIL2A_20240630T054649_N0500_R119_T43WES", "thumb": "/imagery/loc-kargil-2024.jpg", "quality": "Cloud Free (0.1%)", "status": "Expanded Built-up" }
            ],
            "changeAnalysis": {
                "beforeYear": "2020",
                "beforeDate": "30 June 2020",
                "beforeImage": "/imagery/loc-kargil-2020.jpg",
                "afterYear": "2024",
                "afterDate": "30 June 2024",
                "afterImage": "/imagery/loc-kargil-2024.jpg",
                "maskImage": "/imagery/loc-kargil-mask.svg",
                "confidenceScore": 96,
                "changeType": "Mountain Settlement & Built-up Expansion",
                "affectedArea": "~38,500 m²",
                "summary": "Residential and built-up area density in Jammu & Kashmir / Kargil sector shows significant structural expansion between acquisition dates.",
                "detectedChanges": [
                    { "label": "Settlement Density", "confidence": 96, "category": "Anthropogenic / Built-up", "severity": "high", "description": "Residential structures and built-up layout expanded across river valley floor." },
                    { "label": "Road Connections", "confidence": 88, "category": "Linear Infrastructure", "severity": "medium", "description": "New access tracks and paved spurs linking settlement clusters." }
                ],
                "falseAlarmAnalysis": {
                    "checks": [
                        { "label": "Image alignment verified", "detail": "Sub-pixel co-registration error: 0.11 px", "passed": True },
                        { "label": "Snow & cloud contamination low", "detail": "Sen2Cor SCL cloud/snow probability: 0.1%", "passed": True },
                        { "label": "Topographic shadow normalized", "detail": "DEM-assisted solar illumination correction applied", "passed": True }
                    ],
                    "riskLevel": "Low",
                    "riskScore": "0.04 / 1.00",
                    "verdict": "Confirmed Jammu & Kashmir Structural Expansion"
                },
                "provenance": {
                    "beforeGranule": "S2A_MSIL2A_20200630T054651_N0214_R119_T43WES",
                    "afterGranule": "S2B_MSIL2A_20240630T054649_N0500_R119_T43WES",
                    "sensor": "Copernicus Sentinel-2 MSI",
                    "spatialResolution": "10m GSD",
                    "registrationMethod": "AETHER Phase-Correlation Sub-Pixel Orthorectification",
                    "vectorModel": "AETHER-GeoEmbed-v2",
                    "sha256Digest": "5566778899aabbccddeeff00112233445566778899aabbccddeeff0011223344",
                    "archiveNode": "Local Offline Node - Zone North Alpha"
                }
            }
        },
        {
            "id": "loc-jammu",
            "title": "Jammu City & Tawi River Basin",
            "region": "Jammu Region, Jammu & Kashmir, India",
            "coordinates": {
                "lat": 32.7266,
                "lon": 74.8570,
                "dms": "32°43'36\" N, 74°51'25\" E",
                "mgrs": "43WEU412389",
                "utm": "Zone 43N 486500m E 3621100m N"
            },
            "bounds": [[32.7000, 74.8300], [32.7500, 74.8800]],
            "source": "Copernicus Sentinel-2",
            "sensor": "MSI (Level-2A BOA)",
            "resolution": "10m / pixel",
            "sunZenith": "35.2°",
            "cloudCover": "0.1%",
            "matchScore": 95,
            "tags": ["Jammu", "Tawi River", "Built-up Zone", "Urban Fringe", "Jammu & Kashmir"],
            "semanticRationale": "Multi-temporal satellite monitoring of urban development and bridge infrastructure along Tawi River in Jammu City.",
            "thumbnails": {
                "2020": "/imagery/loc-kargil-2020.jpg",
                "2022": "/imagery/loc-kargil-2022.jpg",
                "2024": "/imagery/loc-kargil-2024.jpg"
            },
            "temporalSequence": [
                { "year": "2020", "date": "15 May 2020", "granule": "S2A_MSIL2A_20200515_T43WEU", "thumb": "/imagery/loc-kargil-2020.jpg", "quality": "Cloud Free (0.1%)", "status": "Baseline" },
                { "year": "2024", "date": "15 May 2024", "granule": "S2B_MSIL2A_20240515_T43WEU", "thumb": "/imagery/loc-kargil-2024.jpg", "quality": "Cloud Free (0.1%)", "status": "Built-up Expansion" }
            ],
            "changeAnalysis": {
                "beforeYear": "2020",
                "beforeDate": "15 May 2020",
                "beforeImage": "/imagery/loc-kargil-2020.jpg",
                "afterYear": "2024",
                "afterDate": "15 May 2024",
                "afterImage": "/imagery/loc-kargil-2024.jpg",
                "maskImage": "/imagery/loc-kargil-mask.svg",
                "confidenceScore": 95,
                "changeType": "Urban Fringe & Structural Built-up",
                "affectedArea": "~24,000 m²",
                "summary": "New structural building footprint and road expansion detected in Jammu City perimeter.",
                "detectedChanges": [
                    { "label": "Building Footprints", "confidence": 95, "category": "Urban Expansion", "severity": "high", "description": "Rectilinear roof signatures added in suburban outskirts." }
                ],
                "falseAlarmAnalysis": {
                    "checks": [
                        { "label": "Image alignment verified", "detail": "RMS co-registration error: 0.12 px", "passed": True }
                    ],
                    "riskLevel": "Low",
                    "riskScore": "0.05 / 1.00",
                    "verdict": "Confirmed Jammu Built-up Change"
                },
                "provenance": {
                    "beforeGranule": "S2A_MSIL2A_20200515_T43WEU",
                    "afterGranule": "S2B_MSIL2A_20240515_T43WEU",
                    "sensor": "Copernicus Sentinel-2 MSI",
                    "spatialResolution": "10m GSD",
                    "registrationMethod": "AETHER Phase-Correlation Orthorectification",
                    "vectorModel": "AETHER-GeoEmbed-v2",
                    "sha256Digest": "66778899aabbccddeeff00112233445566778899aabbccddeeff001122334455",
                    "archiveNode": "Local Offline Node - Zone Jammu Alpha"
                }
            }
        },
        {
            "id": "loc-kashmir",
            "title": "Srinagar & Kashmir Valley Sector",
            "region": "Kashmir Valley, Jammu & Kashmir, India",
            "coordinates": {
                "lat": 34.0837,
                "lon": 74.7973,
                "dms": "34°05'01\" N, 74°47'50\" E",
                "mgrs": "43WET891234",
                "utm": "Zone 43N 481200m E 3771500m N"
            },
            "bounds": [[34.0500, 74.7600], [34.1100, 74.8300]],
            "source": "Copernicus Sentinel-2",
            "sensor": "MSI (Level-2A BOA)",
            "resolution": "10m / pixel",
            "sunZenith": "36.8°",
            "cloudCover": "0.1%",
            "matchScore": 96,
            "tags": ["Kashmir Valley", "Srinagar", "Dal Lake Basin", "Agricultural Land", "Jammu & Kashmir"],
            "semanticRationale": "Multi-temporal Sentinel-2 imagery observing land use transformation and residential expansion in Kashmir Valley.",
            "thumbnails": {
                "2020": "/imagery/loc-kargil-2020.jpg",
                "2022": "/imagery/loc-kargil-2022.jpg",
                "2024": "/imagery/loc-kargil-2024.jpg"
            },
            "temporalSequence": [
                { "year": "2020", "date": "20 June 2020", "granule": "S2A_MSIL2A_20200620_T43WET", "thumb": "/imagery/loc-kargil-2020.jpg", "quality": "Cloud Free (0.1%)", "status": "Baseline" },
                { "year": "2024", "date": "20 June 2024", "granule": "S2B_MSIL2A_20240620_T43WET", "thumb": "/imagery/loc-kargil-2024.jpg", "quality": "Cloud Free (0.1%)", "status": "Valley Growth" }
            ],
            "changeAnalysis": {
                "beforeYear": "2020",
                "beforeDate": "20 June 2020",
                "beforeImage": "/imagery/loc-kargil-2020.jpg",
                "afterYear": "2024",
                "afterDate": "20 June 2024",
                "afterImage": "/imagery/loc-kargil-2024.jpg",
                "maskImage": "/imagery/loc-kargil-mask.svg",
                "confidenceScore": 96,
                "changeType": "Valley Settlement Expansion",
                "affectedArea": "~31,000 m²",
                "summary": "Expansion of residential structures and perimeter arterial roads in Kashmir Valley.",
                "detectedChanges": [
                    { "label": "Valley Built-up", "confidence": 96, "category": "Settlement Expansion", "severity": "high", "description": "Structural footprints expanded near highway corridor." }
                ],
                "falseAlarmAnalysis": {
                    "checks": [
                        { "label": "Image alignment verified", "detail": "Sub-pixel RMS error: 0.10 px", "passed": True }
                    ],
                    "riskLevel": "Low",
                    "riskScore": "0.04 / 1.00",
                    "verdict": "Confirmed Kashmir Valley Settlement Change"
                },
                "provenance": {
                    "beforeGranule": "S2A_MSIL2A_20200620_T43WET",
                    "afterGranule": "S2B_MSIL2A_20240620_T43WET",
                    "sensor": "Copernicus Sentinel-2 MSI",
                    "spatialResolution": "10m GSD",
                    "registrationMethod": "AETHER Sub-Pixel Orthorectification",
                    "vectorModel": "AETHER-GeoEmbed-v2",
                    "sha256Digest": "778899aabbccddeeff00112233445566778899aabbccddeeff00112233445566",
                    "archiveNode": "Local Offline Node - Zone Kashmir Alpha"
                }
            }
        }
    ]

    for loc in locations_data:
        save_location_record(conn, loc)

    # Seed Kargil manual change
    add_change(
        conn,
        location="kargil",
        before_date="2024-06-30",
        after_date="2026-06-30",
        change_type="settlement expansion",
        description="Residential/built-up area appears denser and more spread out in 2026 compared to 2024.",
        confidence=0.85,
        affected_area="approx. 0.8 sq km",
        false_alarm_risk="low",
        cloud_ok=1, haze_ok=1, alignment_ok=1, season_ok=1, sensor_ok=1,
        processing_history="Manually reviewed by analyst; ground-truth baseline logged.",
        source="manual"
    )

    # Scan and index data/ directory
    scan_and_index(conn)
    print("Database seeding completed successfully.")


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    seed_default_dataset(conn)
    conn.close()
    print(f"aether.db saved at: {DB_PATH}")
