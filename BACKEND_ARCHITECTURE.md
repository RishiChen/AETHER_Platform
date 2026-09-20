# AETHER Backend Architecture Documentation

## 1. System Overview

AETHER provides offline-first, high-performance semantic retrieval and multi-temporal change analysis of satellite imagery. The backend is implemented in **Python FastAPI** and uses **SQLite** (`aether.db`) as its persistent single source of truth.

---

## 2. Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    AETHER Frontend UI                       │
│  (HTML5, CSS3, Vanilla JS, Leaflet Map, Change Viewers)     │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / JSON / Multipart
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                         │
│                    (backend/main.py)                        │
├───────────────┬──────────────┬───────────────┬──────────────┤
│ Health & Stats│ Search Engine│ Change Analysis│Analyst Review│
└───────┬───────┴──────┬───────┴───────┬───────┴──────┬───────┘
        │              │               │              │
        ▼              ▼               ▼              ▼
┌───────────────┐┌──────────────┐┌──────────────┐┌─────────────┐
│    SQLite     ││ AI Service   ││ File Storage ││ Export      │
│  (aether.db)  ││ Adapter      ││ (data/      )││ Service     │
│ - scenes      ││ (RemoteCLIP) ││ - before/    ││ - GeoJSON   │
│ - changes     │└──────────────┘│ - after/     ││ - Intelligence│
│ - locations   │                │ - uploads/   ││   Dossier   │
│ - reviews     │                └──────────────┘└─────────────┘
└───────────────┘
```

---

## 3. Data Flow & Boundary Isolation

### A. Analyst Review Workflow
1. User clicks Confirm/Reject/Flag in UI.
2. Frontend sends `POST /api/review` with `{ locationId, decision, analystId, notes }`.
3. FastAPI executes `record_review_decision()` in `backend/services/review_service.py`.
4. Review is stored in `analyst_reviews` and `changes` tables in `aether.db`.
5. Review state persists across application restarts.

### B. Real Multipart Image Search Workflow
1. User drops/uploads image in Search UI.
2. Frontend posts `FormData` (`image: File`, `cloudMax`) to `POST /api/search/image`.
3. FastAPI saves uploaded image to `data/uploads/` and scans scene metadata.
4. AI service extracts embeddings via `embed_and_search.py` (or uses metadata scoring fallback if weights are missing).
5. Candidates retrieved from SQLite are filtered by cloud cover and ranked by similarity score.
6. JSON response returns candidate cards and map reticle coordinates to the UI.

### C. Archive Ingestion Workflow
1. User or automated batch posts image file or `.zip` archive to `POST /api/ingest`.
2. FastAPI extracts files safely into `data/uploads/`.
3. `scan_and_index()` extracts filename metadata (`location`, `date`, `sensor`, `width`, `height`).
4. SQLite `scenes` table is updated incrementally without duplicating existing file records.

---

## 4. Database Schema (`aether.db`)

### `scenes` Table
- `id` (TEXT PRIMARY KEY) - SHA1 hash of filepath.
- `filename` (TEXT NOT NULL)
- `filepath` (TEXT NOT NULL UNIQUE)
- `location` (TEXT)
- `capture_date` (TEXT)
- `period` (TEXT: 'before', 'after', 'uploads')
- `sensor` (TEXT)
- `width` (INTEGER), `height` (INTEGER)
- `embedding` (BLOB)
- `indexed_at` (TEXT)

### `locations` Table
- `id` (TEXT PRIMARY KEY)
- `title` (TEXT), `region` (TEXT)
- `latitude` (REAL), `longitude` (REAL)
- `dms` (TEXT), `mgrs` (TEXT), `utm` (TEXT)
- `bounds_json` (TEXT)
- `source` (TEXT), `sensor` (TEXT), `resolution` (TEXT)
- `sun_zenith` (TEXT), `cloud_cover` (TEXT)
- `match_score` (INTEGER)
- `tags_json` (TEXT), `semantic_rationale` (TEXT)
- `thumbnails_json` (TEXT), `temporal_sequence_json` (TEXT), `change_analysis_json` (TEXT)

### `analyst_reviews` Table
- `id` (TEXT PRIMARY KEY)
- `location_id` (TEXT NOT NULL UNIQUE)
- `decision` (TEXT: 'confirmed', 'rejected', 'flagged', 'pending')
- `analyst_id` (TEXT NOT NULL)
- `notes` (TEXT)
- `audit_id` (TEXT NOT NULL)
- `timestamp` (TEXT NOT NULL)

---

## 5. Security & Robustness

- **Path Traversal Prevention**: Controlled image serving (`backend/services/imagery_service.py`) checks `os.path.commonpath` to ensure requested file paths remain strictly inside allowed data/frontend directories.
- **SQL Injection Prevention**: All SQLite queries use parameterized tuple arguments.
- **Input Validation**: Request bodies and parameters are validated using Pydantic V2 models.
