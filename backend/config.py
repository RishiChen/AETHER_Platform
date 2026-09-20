"""
AETHER Backend Configuration
"""

import os
from pathlib import Path

# Base Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
DATABASE_DIR = ROOT_DIR / "Database"
DB_PATH = DATABASE_DIR / "aether.db"
AETHER_DIR = ROOT_DIR / "AETHER"
DATA_DIR = AETHER_DIR / "data"
BEFORE_DATA_DIR = DATA_DIR / "before"
AFTER_DATA_DIR = DATA_DIR / "after"
UPLOADS_DATA_DIR = DATA_DIR / "uploads"
MODELS_DIR = AETHER_DIR / "models"
FRONTEND_DIR = ROOT_DIR / "Frontend"

# Ensure essential directories exist
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DATA_DIR.mkdir(parents=True, exist_ok=True)
BEFORE_DATA_DIR.mkdir(parents=True, exist_ok=True)
AFTER_DATA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Allowed file extensions
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
ALLOWED_ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz"}

# Application settings
APP_NAME = "AETHER - Earth Observation Temporal Engine"
APP_VERSION = "2.0.0-SIH2026"
HOST = "0.0.0.0"
PORT = 8000
