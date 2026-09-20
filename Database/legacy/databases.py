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
    show_summary(conn)
    conn.close()
    print(f"\naether.db saved at: {DB_PATH}")
