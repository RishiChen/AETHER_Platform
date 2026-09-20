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
            capture_date TEXT,
            period TEXT CHECK(period IN ('before', 'after')),
            sensor TEXT DEFAULT 'unknown',
            width INTEGER,
            height INTEGER,
            embedding BLOB,
            indexed_at TEXT NOT NULL
        )
    """)

    # Stores change analysis between a before/after scene pair.
    # One row = one detected (or manually noted) change event.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS changes (
            id TEXT PRIMARY KEY,
            before_scene_id TEXT NOT NULL,
            after_scene_id TEXT NOT NULL,
            location TEXT,
            change_type TEXT,
            description TEXT,
            confidence REAL,
            source TEXT DEFAULT 'manual',
            analyst_status TEXT DEFAULT 'pending'
                CHECK(analyst_status IN ('pending', 'confirmed', 'rejected')),
            created_at TEXT NOT NULL,
            FOREIGN KEY (before_scene_id) REFERENCES scenes(id),
            FOREIGN KEY (after_scene_id) REFERENCES scenes(id)
        )
    """)
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
                description, confidence=None, source="manual"):
    """
    Log a change record between a before/after scene pair for the given
    location. Looks up the two scene ids automatically from their
    location + date, so you don't need to know the scene hash ids.

    change_type examples: 'construction', 'clearance',
                           'water-extent variation', 'road development',
                           'settlement expansion'
    source: 'manual' (analyst-entered, e.g. ground truth / test case)
            or 'model' (produced by the change-detection pipeline)
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
         description, confidence, source, analyst_status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (
        change_id, before_id, after_id, location, change_type,
        description, confidence, source,
        datetime.now(timezone.utc).isoformat()
    ))
    conn.commit()
    print(f"[change logged] {location}: {before_date} -> {after_date}  "
          f"({change_type}) - {description}")
    return change_id


def show_changes(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT location, change_type, description, analyst_status, source
        FROM changes ORDER BY created_at
    """)
    rows = cur.fetchall()
    if not rows:
        return
    print("\n--- Logged changes ---")
    for location, change_type, description, status, source in rows:
        print(f"[{status}] ({source}) {location} - {change_type}: {description}")


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
    add_change(
        conn,
        location="kargil",
        before_date="2024-06-30",
        after_date="2026-06-30",
        change_type="settlement expansion",
        description="Residential/built-up area appears denser and more "
                     "spread out in 2026 compared to 2024.",
        source="manual"
    )

    show_summary(conn)
    show_changes(conn)
    conn.close()
    print(f"\naether.db saved at: {DB_PATH}")
