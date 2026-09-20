"""
AETHER Imagery Service
----------------------
Handles safe file retrieval and path traversal prevention for satellite images.
"""

import os
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse
from backend.config import DATA_DIR, FRONTEND_DIR

def resolve_safe_image_path(requested_path_str: str) -> Path:
    """
    Validates and resolves requested file path, ensuring it resides safely
    within allowed data or frontend image directories (preventing path traversal).
    """
    # Clean leading slashes
    clean_path = requested_path_str.lstrip("/\\")

    # Possible base directories where imagery may reside
    allowed_bases = [
        DATA_DIR.resolve(),
        (DATA_DIR / "before").resolve(),
        (DATA_DIR / "after").resolve(),
        (DATA_DIR / "uploads").resolve(),
        (FRONTEND_DIR / "imagery").resolve(),
    ]

    candidate_paths = [
        (FRONTEND_DIR / clean_path).resolve(),
        (DATA_DIR / clean_path).resolve(),
        (FRONTEND_DIR / "imagery" / Path(clean_path).name).resolve(),
        (DATA_DIR / "before" / Path(clean_path).name).resolve(),
        (DATA_DIR / "after" / Path(clean_path).name).resolve(),
        (DATA_DIR / "uploads" / Path(clean_path).name).resolve(),
    ]

    for cand in candidate_paths:
        if cand.exists() and cand.is_file():
            # Verify path traversal security check
            for base in allowed_bases:
                try:
                    cand.relative_to(base)
                    return cand
                except ValueError:
                    continue

    raise HTTPException(status_code=404, detail=f"Image file not found or access denied: {requested_path_str}")


def serve_image_file(requested_path_str: str) -> FileResponse:
    target_path = resolve_safe_image_path(requested_path_str)
    
    # Determine content type
    ext = target_path.suffix.lower()
    media_type = "image/jpeg"
    if ext in (".png",):
        media_type = "image/png"
    elif ext in (".svg",):
        media_type = "image/svg+xml"
    elif ext in (".tif", ".tiff"):
        media_type = "image/tiff"

    return FileResponse(path=str(target_path), media_type=media_type)
