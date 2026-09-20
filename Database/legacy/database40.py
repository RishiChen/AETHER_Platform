"""
AETHER - database.py
---------------------
Scans data/before and data/after folders for satellite images,
extracts basic metadata, and stores it in a local SQLite database
(aether.db). Designed to run fully offline (no cloud/API calls).

Run this from inside the AETHER/ root folder:
    python database.py

Re-running it is safe: already-indexed files are skipped
(incremental ingestion), so new images added later get picked up
without rebuilding everything.
"""

import os
import re
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
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(BASE_DIR, "aether.db")
VALID_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tif", ".tiff")
PERIOD_FOLDERS = ["before", "after"]

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
            period TEXT CHECK(period IN ('before', 'after')),
            sensor TEXT DEFAULT 'unknown',
            width INTEGER,
            height INTEGER,
            quality TEXT DEFAULT 'unknown'
                CHECK(quality IN ('good', 'fair', 'poor', 'unknown')),
            embedding BLOB,
            indexed_at TEXT NOT NULL
        )
    """)

    # Stores change analysis between a before/after scene pair.
    # One row = one detected (or manually noted) change event.
    # Fields map directly onto the Change Analysis page (Page 3) in the
    # frontend spec: change type/confidence -> Change Detection (D),
    # region -> Change Overlay (E), cloud/haze/alignment/season/sensor +
    # false_alarm_risk -> False-Alarm Check (F), affected_area ->
    # Change Summary (G), processing_history -> Evidence & Provenance (H),
    # analyst_status -> Analyst Review buttons: Confirm/Reject/Flag (I).
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
    conn.commit()
    _migrate_schema(conn)


def _migrate_schema(conn):
    """
    Adds any columns that were introduced after a table already existed.
    CREATE TABLE IF NOT EXISTS does nothing if the table is already
    present with an older schema, so without this, an existing aether.db
    from before a schema change would error with e.g.
    'table changes has no column named affected_area'. This makes
    re-running database.py on an old aether.db safe (no need to delete
    the .db file when the schema grows).
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
SENSOR_PATTERN = re.compile(r"(Sentinel-\d[A-Za-z]*)", re.IGNORECASE)
LEVEL_PATTERN = re.compile(r"(L1C|L2A)", re.IGNORECASE)


def parse_scene_info(filename):
    """
    Handles two kinds of filenames:

    1. Renamed / hand-named files, e.g.:  kargil_2024-06-30.jpg
       -> location='kargil', date='2024-06-30'

    2. Raw Copernicus Browser export names, e.g.:
       2024-06-30-00_00_2024-06-30-23_59_Sentinel-2_L2A_True_color.jpg
       -> location=None (not present in the filename - rename the file
          to add it, e.g. kargil_2024-06-30.jpg), date='2024-06-30',
          sensor='Sentinel-2 (L2A)'

    Returns (location, date_str, sensor).
    """
    name = os.path.splitext(filename)[0]

    # location prefix only recognized if it's NOT itself a date
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


def scan_and_index(conn):
    cur = conn.cursor()
    added, skipped = 0, 0

    for period in PERIOD_FOLDERS:
        folder = os.path.join(DATA_DIR, period)
        if not os.path.isdir(folder):
            print(f"[warn] Folder not found: {folder}")
            continue

        for filename in sorted(os.listdir(folder)):
            if not filename.lower().endswith(VALID_EXTENSIONS):
                continue

            filepath = os.path.join(folder, filename)
            scene_id = make_scene_id(filepath)

            # Skip if already indexed
            cur.execute("SELECT 1 FROM scenes WHERE id = ?", (scene_id,))
            if cur.fetchone():
                skipped += 1
                continue

            location, date_str, sensor = parse_scene_info(filename)
            width, height = get_image_dimensions(filepath)

            if location is None:
                print(f"  [warn] No location prefix found in '{filename}'. "
                      f"Rename it like 'kargil_{date_str or 'YYYY-MM-DD'}.jpg' "
                      f"so it's identifiable later.")

            cur.execute("""
                INSERT INTO scenes
                (id, filename, filepath, location, capture_date, period,
                 sensor, width, height, embedding, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scene_id,
                filename,
                filepath,
                location,
                date_str,
                period,
                sensor or "Sentinel-2",  # fallback if not detected in filename
                width,
                height,
                None,
                datetime.now(timezone.utc).isoformat()
            ))
            added += 1
            print(f"[indexed] {period}/{filename}  (location={location}, date={date_str}, sensor={sensor})")

    conn.commit()
    print(f"\nDone. {added} new scene(s) indexed, {skipped} already existed.")


def get_scene_id(conn, location, date_str, period):
    """Find a scene's id by location + date + period (before/after)."""
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
    """
    Log a change record between a before/after scene pair for the given
    location. Looks up the two scene ids automatically from their
    location + date, so you don't need to know the scene hash ids.

    change_type examples: 'construction', 'clearance',
                           'water-extent variation', 'road development',
                           'settlement expansion'
    source: 'manual' (analyst-entered, e.g. ground truth / test case)
            or 'model' (produced by the change-detection pipeline)
    affected_area: free text or a number+unit, e.g. '1.4 sq km'
    region_bbox: overlay region for the Change Overlay UI, e.g. a
                 "x1,y1,x2,y2" pixel box or a GeoJSON string
    cloud_ok/haze_ok/alignment_ok/season_ok/sensor_ok: 1 = no issue
                 detected for that factor, 0 = flagged as a possible
                 confound (these back Page 3's False-Alarm Check list)
    false_alarm_risk: 'low' | 'medium' | 'high' | 'unknown'
    processing_history: free text describing pipeline steps applied
                 (for the Evidence & Provenance panel)
    """
    before_id = get_scene_id(conn, location, before_date, "before")
    after_id = get_scene_id(conn, location, after_date, "after")

    if not before_id or not after_id:
        print(f"[error] Could not find scene(s) for location='{location}' "
              f"before={before_date} after={after_date}. "
              f"Make sure database.py has already indexed these images.")
        return None

    change_id = hashlib.sha1(
        f"{before_id}-{after_id}-{change_type}".encode("utf-8")
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
        change_id, before_id, after_id, location, change_type,
        description, confidence, affected_area, region_bbox,
        cloud_ok, haze_ok, alignment_ok, season_ok, sensor_ok,
        false_alarm_risk, processing_history, source,
        datetime.now(timezone.utc).isoformat()
    ))
    conn.commit()
    print(f"[change logged] {location}: {before_date} -> {after_date}  "
          f"({change_type}) - {description}")
    return change_id


def set_analyst_status(conn, change_id, status):
    """
    Backs the Confirm / Reject / Flag for Review buttons on Page 3.
    status: 'confirmed' | 'rejected' | 'flagged'
    """
    if status not in ("confirmed", "rejected", "flagged", "pending"):
        print(f"[error] Invalid status '{status}'.")
        return
    conn.execute(
        "UPDATE changes SET analyst_status = ? WHERE id = ?",
        (status, change_id)
    )
    conn.commit()
    print(f"[analyst review] change {change_id} -> {status}")


def set_scene_quality(conn, location, date_str, period, quality):
    """quality: 'good' | 'fair' | 'poor' | 'unknown' — shown in Location Details."""
    scene_id = get_scene_id(conn, location, date_str, period)
    if not scene_id:
        print(f"[error] Scene not found for {location} {date_str} {period}")
        return
    conn.execute("UPDATE scenes SET quality = ? WHERE id = ?", (quality, scene_id))
    conn.commit()


def set_scene_coordinates(conn, location, date_str, period, latitude, longitude):
    """
    Set lat/lon for a scene — backs the Map marker (Page 2E) and the
    'Coordinates' line in Location Details / Selected Location panels
    (Page 2G, Page 3A). Usually the same for a location's before/after
    pair, so call it once per scene (or once per location if you loop
    over both periods).
    """
    scene_id = get_scene_id(conn, location, date_str, period)
    if not scene_id:
        print(f"[error] Scene not found for {location} {date_str} {period}")
        return
    conn.execute(
        "UPDATE scenes SET latitude = ?, longitude = ? WHERE id = ?",
        (latitude, longitude, scene_id)
    )
    conn.commit()
    print(f"[coordinates set] {location} {date_str} {period} -> ({latitude}, {longitude})")


def _row_to_dict(cur, row):
    """Convert a sqlite3 row into a dict using the cursor's column names."""
    if row is None:
        return None
    columns = [d[0] for d in cur.description]
    return dict(zip(columns, row))


# ============================================================
# READ (R) — single-record lookups
# ============================================================

def get_scene(conn, scene_id):
    """Fetch one scene by its id. Returns a dict, or None if not found."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,))
    return _row_to_dict(cur, cur.fetchone())


def get_change(conn, change_id):
    """Fetch one change record by its id. Returns a dict, or None if not found."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM changes WHERE id = ?", (change_id,))
    return _row_to_dict(cur, cur.fetchone())


def list_locations(conn):
    """All distinct locations currently indexed (for populating a dropdown/list page)."""
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT location FROM scenes
        WHERE location IS NOT NULL ORDER BY location
    """)
    return [row[0] for row in cur.fetchall()]


def get_location_details(conn, location):
    """
    Full fetch for one location - this is what the frontend's
    'Fetch' / 'Inspect Location' / 'Analyze Change' button calls.
    Returns a single dict with every scene and every change on record
    for that location, so the UI can render Pages 2-3 from one call:

        {
          "location": "kargil",
          "scenes": [ {...}, {...} ],   # before + after images, metadata
          "changes": [ {...}, {...} ]   # detections, false-alarm checks,
                                         # provenance, analyst status
        }
    """
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM scenes WHERE location = ?
        ORDER BY period, capture_date
    """, (location,))
    scenes = [_row_to_dict(cur, row) for row in cur.fetchall()]

    cur.execute("""
        SELECT * FROM changes WHERE location = ?
        ORDER BY created_at
    """, (location,))
    changes = [_row_to_dict(cur, row) for row in cur.fetchall()]

    return {
        "location": location,
        "scenes": scenes,
        "changes": changes,
    }


# ============================================================
# UPDATE (U) — generic field update (on top of the specific
# set_analyst_status / set_scene_quality helpers above)
# ============================================================

def update_scene(conn, scene_id, **fields):
    """
    Update one or more columns on a scene row, e.g.:
        update_scene(conn, scene_id, sensor="Sentinel-2 (L2A)", quality="good")
    """
    if not fields:
        print("[error] update_scene called with no fields to update.")
        return False
    if not get_scene(conn, scene_id):
        print(f"[error] No scene found with id={scene_id}")
        return False

    set_clause = ", ".join(f"{col} = ?" for col in fields)
    values = list(fields.values()) + [scene_id]
    conn.execute(f"UPDATE scenes SET {set_clause} WHERE id = ?", values)
    conn.commit()
    print(f"[updated] scene {scene_id}: {fields}")
    return True


def update_change(conn, change_id, **fields):
    """
    Update one or more columns on a change row, e.g.:
        update_change(conn, change_id, confidence=0.9, false_alarm_risk="low")
    """
    if not fields:
        print("[error] update_change called with no fields to update.")
        return False
    if not get_change(conn, change_id):
        print(f"[error] No change found with id={change_id}")
        return False

    set_clause = ", ".join(f"{col} = ?" for col in fields)
    values = list(fields.values()) + [change_id]
    conn.execute(f"UPDATE changes SET {set_clause} WHERE id = ?", values)
    conn.commit()
    print(f"[updated] change {change_id}: {fields}")
    return True


# ============================================================
# DELETE (D)
# ============================================================

def delete_change(conn, change_id):
    """Delete a single change record (e.g. analyst rejects/removes a false detection)."""
    if not get_change(conn, change_id):
        print(f"[error] No change found with id={change_id}")
        return False
    conn.execute("DELETE FROM changes WHERE id = ?", (change_id,))
    conn.commit()
    print(f"[deleted] change {change_id}")
    return True


def delete_scene(conn, scene_id, cascade=True):
    """
    Delete a scene row. Since 'changes' references scene ids, by default
    (cascade=True) any change rows that used this scene as before/after
    are deleted too, to avoid dangling foreign keys. Pass cascade=False
    to block the delete instead if dependent changes exist.
    """
    if not get_scene(conn, scene_id):
        print(f"[error] No scene found with id={scene_id}")
        return False

    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM changes
        WHERE before_scene_id = ? OR after_scene_id = ?
    """, (scene_id, scene_id))
    dependent = [row[0] for row in cur.fetchall()]

    if dependent and not cascade:
        print(f"[error] scene {scene_id} is used by {len(dependent)} change(s); "
              f"not deleted (pass cascade=True to also delete those changes).")
        return False

    if dependent:
        cur.execute("""
            DELETE FROM changes WHERE before_scene_id = ? OR after_scene_id = ?
        """, (scene_id, scene_id))
        print(f"[deleted] {len(dependent)} dependent change(s): {dependent}")

    cur.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))
    conn.commit()
    print(f"[deleted] scene {scene_id}")
    return True


def print_table(rows):
    """
    Pretty-print a list of dicts (e.g. from get_location_details()['scenes'])
    as an aligned table - handy for quickly eyeballing query results.
    """
    if not rows:
        print("(no rows)")
        return
    cols = list(rows[0].keys())
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    header = " | ".join(c.ljust(widths[c]) for c in cols)
    print(header)
    print("-+-".join("-" * widths[c] for c in cols))
    for r in rows:
        print(" | ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols))


def show_changes(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT location, change_type, description, analyst_status,
               source, false_alarm_risk, affected_area
        FROM changes ORDER BY created_at
    """)
    rows = cur.fetchall()
    if not rows:
        return
    print("\n--- Logged changes ---")
    for location, change_type, description, status, source, risk, area in rows:
        area_str = f", area={area}" if area else ""
        print(f"[{status}] ({source}) {location} - {change_type} "
              f"(false-alarm risk: {risk}{area_str}): {description}")


def show_summary(conn):
    cur = conn.cursor()
    cur.execute("SELECT period, COUNT(*) FROM scenes GROUP BY period")
    print("\n--- Database summary ---")
    for period, count in cur.fetchall():
        print(f"{period}: {count} scene(s)")


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    scan_and_index(conn)

    # ---- Manually logged change (ground-truth / test case) ----
    # This is YOUR observation about the Kargil pair: residential/
    # settlement area has expanded from 2024 to 2026. It gets stored
    # in the `changes` table so it survives, and can later be used to
    # check whether the automated change-detection model agrees.
    # Add more add_change(...) calls below for other locations/pairs.
    change_id = add_change(
        conn,
        location="kargil",
        before_date="2024-06-30",
        after_date="2026-06-30",
        change_type="settlement expansion",
        description="Residential/built-up area appears denser and more "
                     "spread out in 2026 compared to 2024.",
        confidence=0.85,
        affected_area="approx. 0.8 sq km",
        false_alarm_risk="low",
        cloud_ok=1, haze_ok=1, alignment_ok=1, season_ok=1, sensor_ok=1,
        processing_history="Manually reviewed by analyst; no automated "
                            "pipeline run yet.",
        source="manual"
    )

    # Example of the Analyst Review action (Confirm / Reject / Flag
    # buttons on Page 3). Since this is our own ground-truth entry,
    # we confirm it here as a demonstration of the workflow.
    if change_id:
        set_analyst_status(conn, change_id, "confirmed")

    show_summary(conn)
    show_changes(conn)

    # ---- CRUD demo (proves Read / Update / Delete work end-to-end) ----
    # This is what a "fetch details" button on the frontend would call:
    if change_id:
        print("\n--- get_location_details('kargil') ---")
        details = get_location_details(conn, "kargil")
        print(f"location: {details['location']}")
        print(f"{len(details['scenes'])} scene(s), {len(details['changes'])} change(s)")
        print_table(details["scenes"])
        print_table(details["changes"])

    conn.close()
    print(f"\naether.db saved at: {DB_PATH}")
