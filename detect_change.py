"""
AETHER - detect_change.py
---------------------------
CLI entry point for automated multi-temporal satellite change detection.
Uses sub-pixel phase correlation alignment + SSIM + Lab spectral delta pipeline from
backend.services.detect_change_service.

Run:
    python detect_change.py
    python detect_change.py --before Frontend/imagery/loc-river-2020.jpg --after Frontend/imagery/loc-river-2024.jpg --output Frontend/imagery/masks/loc-river_mask.png
    python detect_change.py --all
"""

import sys
import os
import glob
import re
import sqlite3
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "Database"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(DB_DIR) not in sys.path:
    sys.path.insert(0, str(DB_DIR))

import database as db
from backend.services.detect_change_service import (
    compute_change_mask,
    detect_and_save
)

def compute_change(before_path: str, after_path: str, output_mask_path: str, change_type: str = "Structural & Land Cover Shift"):
    """
    Backward-compatible wrapper for compute_change_mask.
    Returns (change_score, output_mask_path, bbox_str).
    """
    annotated_path = output_mask_path.replace(".png", "_annotated.jpg").replace(".jpg", "_annotated.jpg")
    res = compute_change_mask(
        before_path=before_path,
        after_path=after_path,
        output_mask_path=output_mask_path,
        output_annotated_path=annotated_path,
        change_type=change_type
    )
    bbox_str = "; ".join(res["boundingBoxes"]) if res["boundingBoxes"] else None
    return res["changeScore"], output_mask_path, bbox_str


def find_image(folder: str, location: str, preferred_year: str = None) -> str:
    extensions = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]
    files = []
    
    search_dirs = [folder, os.path.join("Frontend", "imagery"), os.path.join("AETHER", "data", "before"), os.path.join("AETHER", "data", "after")]
    for sdir in search_dirs:
        if os.path.exists(sdir):
            for ext in extensions:
                files.extend(glob.glob(os.path.join(sdir, ext)))

    location_files = [f for f in files if location.lower() in os.path.basename(f).lower()]
    
    if preferred_year and location_files:
        year_matched = [f for f in location_files if preferred_year in os.path.basename(f)]
        if year_matched:
            return year_matched[0]

    if not location_files:
        raise FileNotFoundError(f"No image matching '{location}' found.")
    return location_files[0]


def get_date_from_filename(path: str) -> str:
    filename = os.path.basename(path)
    match = re.search(r"(20\d{2})[-_](\d{2})[-_](\d{2})", filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    match = re.search(r"(20\d{2})", filename)
    if match:
        return match.group(1)
    return "unknown"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AETHER Multi-Temporal Satellite Change Detector")
    parser.add_argument("--before", type=str, help="Path to before satellite image")
    parser.add_argument("--after", type=str, help="Path to after satellite image")
    parser.add_argument("--location", type=str, default="river", help="Location ID / keyword")
    parser.add_argument("--output", type=str, help="Path to output RGBA PNG mask")
    parser.add_argument("--change-type", type=str, default="Structural & Land Cover Shift")
    parser.add_argument("--all", action="store_true", help="Batch run change detection across all standard locations")
    args = parser.parse_args()

    db_path = os.path.join("Database", "aether.db") if os.path.exists(os.path.join("Database", "aether.db")) else "aether.db"
    conn = sqlite3.connect(db_path)

    if args.before and args.after:
        out_mask = args.output or os.path.join("Frontend", "imagery", "masks", f"{args.location}_change_mask.png")
        print(f"[AETHER Change Detection] Analyzing single pair: {args.before} vs {args.after}")
        results = compute_change_mask(
            before_path=args.before,
            after_path=args.after,
            output_mask_path=out_mask,
            change_type=args.change_type
        )
        print(f"  Change Score: {results['changeScore']}")
        print(f"  Affected Area: {results['affectedArea']}")
        print(f"  Contours/Blobs: {results['contoursCount']}")
        print(f"  Output Mask: {out_mask}")

    else:
        # Batch Mode over dataset locations
        before_folder = os.path.join("Frontend", "imagery")
        after_folder = os.path.join("Frontend", "imagery")
        locations = ["river", "highway", "water", "industry", "cleared", "kargil"]

        print("==========================================================")
        print(" AETHER Automated Satellite Change Detector (Batch Run)")
        print("==========================================================")

        for loc in locations:
            try:
                b_path = find_image(before_folder, loc, preferred_year="2020")
                a_path = find_image(after_folder, loc, preferred_year="2024")

                if b_path == a_path and len(glob.glob(os.path.join(before_folder, f"*{loc}*"))) > 1:
                    all_loc = glob.glob(os.path.join(before_folder, f"*{loc}*"))
                    all_loc.sort()
                    b_path, a_path = all_loc[0], all_loc[-1]

                b_date = get_date_from_filename(b_path)
                a_date = get_date_from_filename(a_path)
                out_mask = os.path.join("Frontend", "imagery", "masks", f"{loc}_change_mask.png")

                detect_and_save(
                    conn,
                    location=loc,
                    before_date=b_date,
                    after_date=a_date,
                    before_path=b_path,
                    after_path=a_path,
                    output_mask_path=out_mask,
                    change_type=args.change_type
                )
            except Exception as e:
                print(f"[detect_change CLI] Skipping {loc}: {e}")

        conn.commit()
        print("==========================================================")
        print(" Batch Change Detection Completed Successfully.")
        print("==========================================================")

    conn.close()