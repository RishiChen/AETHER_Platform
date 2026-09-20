"""
AETHER Satellite Imagery Batch Change Detection & Mask Pre-processor Script
-----------------------------------------------------------------------------
Scans satellite imagery pairs, runs phase correlation alignment, SSIM + Lab spectral delta
change mask generation, and populates high-contrast RGBA overlay PNGs into Frontend/imagery/masks.

Run:
    python scripts/run_change_detection.py
"""

import sys
import os
import glob
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_DIR = ROOT_DIR / "Database"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

import database as db
from backend.services.detect_change_service import compute_change_mask, detect_and_save

def run_all_change_detections():
    print("=================================================================")
    print(" AETHER Batch Satellite Change Detector & Overlay Pre-processor")
    print("=================================================================")

    db_path = ROOT_DIR / "Database" / "aether.db"
    if not db_path.exists():
        db_path = ROOT_DIR / "aether.db"

    conn = sqlite3.connect(str(db_path))

    imagery_dir = ROOT_DIR / "Frontend" / "imagery"
    masks_dir = imagery_dir / "masks"
    masks_dir.mkdir(parents=True, exist_ok=True)

    locations = ["river", "highway", "water", "industry", "cleared", "kargil"]
    years = ["2020", "2022", "2024"]

    processed = 0

    for loc in locations:
        loc_images = sorted(list(imagery_dir.glob(f"*{loc}*.jpg")) + list(imagery_dir.glob(f"*{loc}*.png")))
        if len(loc_images) < 2:
            continue

        pairs = [
            (2020, 2024),
            (2020, 2022),
            (2022, 2024)
        ]

        for b_yr, a_yr in pairs:
            b_file = imagery_dir / f"loc-{loc}-{b_yr}.jpg"
            a_file = imagery_dir / f"loc-{loc}-{a_yr}.jpg"

            if not b_file.exists():
                b_file = imagery_dir / f"{loc}-{b_yr}.jpg"
            if not a_file.exists():
                a_file = imagery_dir / f"{loc}-{a_yr}.jpg"

            if b_file.exists() and a_file.exists():
                out_mask_loc = masks_dir / f"loc-{loc}_{b_yr}_{a_yr}_mask.png"
                out_mask_plain = masks_dir / f"{loc}_{b_yr}_{a_yr}_mask.png"
                out_mask_default = masks_dir / f"{loc}_change_mask.png"
                out_mask_loc_default = masks_dir / f"loc-{loc}_change_mask.png"

                print(f"  [Processing] {loc} ({b_yr} -> {a_yr})...")

                try:
                    res = compute_change_mask(
                        before_path=str(b_file),
                        after_path=str(a_file),
                        output_mask_path=str(out_mask_loc),
                        change_type="Structural & Land Cover Shift"
                    )
                    import shutil
                    shutil.copyfile(str(out_mask_loc), str(out_mask_plain))
                    shutil.copyfile(str(out_mask_loc), str(out_mask_default))
                    shutil.copyfile(str(out_mask_loc), str(out_mask_loc_default))
                    processed += 1
                    print(f"    -> Score: {res['changeScore']} | Area: {res['affectedArea']} | Blobs: {res['contoursCount']}")
                except Exception as e:
                    print(f"    -> Error: {e}")

    conn.close()
    print("=================================================================")
    print(f" Pre-processed {processed} Change Overlay Masks.")
    print("=================================================================")

if __name__ == "__main__":
    run_all_change_detections()
