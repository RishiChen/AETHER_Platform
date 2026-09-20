"""
AETHER Archive Ingestion Service
---------------------------------
Handles single file and ZIP archive uploads, saves to local storage, and indexes into SQLite.
"""

import os
import sys
import zipfile
import logging
from pathlib import Path
from typing import List, Dict, Any

from backend.config import AETHER_DIR, DATABASE_DIR, DATA_DIR, UPLOADS_DATA_DIR, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_ARCHIVE_EXTENSIONS

if str(DATABASE_DIR) not in sys.path:
    sys.path.insert(0, str(DATABASE_DIR))
if str(AETHER_DIR) not in sys.path:
    sys.path.insert(0, str(AETHER_DIR))

import database

logger = logging.getLogger("aether.ingestion_service")

def process_uploaded_archive(db_conn, filename: str, content: bytes) -> Dict[str, Any]:
    """
    Saves file or unzips archive, stores satellite images in data/uploads/, and indexes into aether.db.
    """
    ext = Path(filename).suffix.lower()
    processed_files = []

    if ext in ALLOWED_ARCHIVE_EXTENSIONS:
        # Save temp zip file
        zip_path = UPLOADS_DATA_DIR / filename
        with open(zip_path, "wb") as f:
            f.write(content)

        # Unzip safely
        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                for member in zip_ref.namelist():
                    # Security check: prevent zip slip
                    member_path = Path(member)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        continue
                    if member_path.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS:
                        extracted_path = UPLOADS_DATA_DIR / member_path.name
                        with zip_ref.open(member) as source, open(extracted_path, "wb") as target:
                            target.write(source.read())
                        processed_files.append(str(extracted_path))
        except Exception as e:
            logger.error(f"Error unzipping {filename}: {e}")
    elif ext in ALLOWED_IMAGE_EXTENSIONS:
        img_path = UPLOADS_DATA_DIR / filename
        with open(img_path, "wb") as f:
            f.write(content)
        processed_files.append(str(img_path))
    else:
        raise ValueError(f"Unsupported file format '{ext}'. Allowed: {ALLOWED_IMAGE_EXTENSIONS | ALLOWED_ARCHIVE_EXTENSIONS}")

    # Index new files in database
    database.scan_and_index(db_conn, data_folder=str(DATA_DIR))

    return {
        "success": True,
        "message": f"Successfully ingested {len(processed_files)} file(s) into offline archive.",
        "filesProcessed": len(processed_files),
        "indexedScenes": processed_files
    }
