# AETHER - Earth Observation Temporal Engine & Semantic Retrieval System
**SIH 2026 Problem Statement 26227 Prototype**

AETHER is a fully offline-capable platform for semantic satellite imagery retrieval, multi-temporal change detection, false-alarm screening, and human-in-the-loop analyst verification.

---

## Architecture Overview

```
Frontend (HTML/CSS/JS + Leaflet Map)
       │
       │ HTTP / REST / Multipart Uploads
       ▼
FastAPI Backend (localhost:8000)
       ├── SQLite Database (AETHER/aether.db)
       ├── Local Satellite Imagery (AETHER/data/)
       ├── AI Service Adapter (AETHER/embed_and_search.py)
       ├── Archive Ingestion Pipeline
       └── Intelligence Dossier Exporter
```

---

## Quick Start Guide

### 1. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 2. Initialize Database & Seed Baseline Archive
```bash
python Database/database.py
```

### 3. Start the FastAPI Server
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Open Application in Browser
Navigate to:
```
http://localhost:8000/
```

---

## Core API Endpoints

- **Health & Statistics**:
  - `GET /api/health` - Health check & offline status.
  - `GET /api/stats` - Archive statistics & review progress.

- **Semantic & Visual Image Search**:
  - `GET /api/candidates?query=river&cloudMax=30` - Text query search with cloud/source filters.
  - `POST /api/search/image` - Multipart image upload for visual similarity search.

- **Location Inspection & Change Analysis**:
  - `GET /api/location/{id}` - Location metadata, coordinates, and temporal sequence.
  - `GET /api/change-analysis/{id}` - Before/after images, detected changes, false-alarm checklist, provenance.
  - `POST /api/changes/analyze` - Trigger change detection between baseline/target imagery.

- **Analyst Review & Dossier Export**:
  - `POST /api/review` - Persist analyst decision (`confirmed`, `rejected`, `flagged`).
  - `GET /api/export-dossier/{id}` - Download GeoJSON/JSON Intelligence Dossier.

- **Archive Ingestion & Image Serving**:
  - `POST /api/ingest` - Ingest satellite image or `.zip` archive into local data store & SQLite index.
  - `GET /imagery/{filename}` - Safe image file serving with path traversal protection.

---

## Directory Structure

```
Semantic Retrieval Project/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── schemas.py
│   ├── dependencies.py
│   ├── routers/
│   ├── services/
│   └── ai/
├── AETHER/
│   ├── aether.db
│   ├── database.py
│   ├── embed_and_search.py
│   ├── data/
│   ├── models/
│   └── legacy/
├── frontend/
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── imagery/
├── requirements.txt
└── README.md
```
