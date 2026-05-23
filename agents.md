# Google Drive Book Scanner — Agent Integration Guide

This document describes the **books-scanner** project for integration into a larger **Dashboard / Agent System**. It covers architecture, APIs, data contracts, and practical integration patterns.

---

## Project Overview

**books-scanner** (also branded as *Google Drive Scanner Control Panel* / *Book Scanner Control Panel*) is a full-stack web application that:

1. **Traverses a Google Drive folder tree** (or a flat folder of PDFs) using a Google Service Account.
2. **Downloads each PDF**, extracts metadata (page count, file size), and generates a **thumbnail** from page 2 (or page 1 if only one page).
3. **Uploads thumbnails to Cloudinary** and appends structured book records to a JSON catalog file.
4. **Exposes a REST API + React UI** to start/stop jobs, stream logs, poll status, download results, and view scan history.

**Problem it solves:** Bulk cataloging of educational PDF books stored in Google Drive, with resumable incremental scans and a operator-friendly control panel—without persisting API secrets on the server filesystem (credentials are supplied per job via the API/UI).

**Typical output:** A JSON array of book objects (e.g. `MyFolder.json` or `books.json`) suitable for import into a books database or downstream agent pipeline.

---

## Tech Stack

### Backend (Python)

| Technology | Version / Notes |
|------------|-----------------|
| Python | **3.9** (Dockerfile); compatible with 3.9+ |
| FastAPI | Unpinned in `requirements.txt` |
| Uvicorn | ASGI server |
| python-multipart | Form/file support (FastAPI) |
| google-api-python-client | Google Drive API v3 |
| google-auth-httplib2, google-auth-oauthlib | Google auth |
| cloudinary | Thumbnail uploads |
| PyMuPDF (`fitz`) | PDF parsing & rasterization |
| requests | HTTP (dependency chain) |

**Entry point:** `uvicorn backend.main:app --host 0.0.0.0 --port 8000`

### Frontend (Node)

| Technology | Version (`frontend/package.json`) |
|------------|----------------------------------|
| React | ^18.2.0 |
| react-dom | ^18.2.0 |
| Vite | ^5.0.8 |
| Tailwind CSS | ^3.4.0 |
| lucide-react | ^0.300.0 |
| @vitejs/plugin-react | ^4.2.1 |

**Dev entry:** `npm run dev` → `http://localhost:5173` (proxies `/api` → `http://localhost:8000`)

### Deployment

- **Docker:** Multi-stage build (Node 18 → Python 3.9-slim), single port **8000** (API + static frontend).
- **Local helper:** `run_local.ps1` (Windows) starts backend and frontend in separate terminals.

### External services (no database)

- **Google Drive API** (read-only, service account)
- **Cloudinary** (image CDN for thumbnails)

There is **no SQL/NoSQL database**. Persistence is file-based: JSON output files and `scan_history.json`.

---

## Project Structure

```
books-scanner/
├── agents.md                 # This file — integration reference
├── README.md                 # User-facing setup & architecture summary
├── requirements.txt          # Python dependencies (unpinned)
├── Dockerfile                # Production build: frontend → backend/static
├── run_local.ps1             # Windows dev: pip + npm + dual servers
│
├── backend/
│   ├── main.py               # FastAPI app, CORS, /api router, static mount
│   ├── api.py                # REST routes (start/stop/status/logs/download/history)
│   ├── job_manager.py        # Singleton job lifecycle, threading, counters, logs
│   ├── scanner.py            # Core Drive traversal, PDF processing, Cloudinary upload
│   ├── history.py            # Persists completed job summaries to scan_history.json
│   └── static/               # (generated) Vite production build — not in git by default
│
└── frontend/
    ├── package.json
    ├── vite.config.js        # outDir: ../backend/static; dev proxy /api → :8000
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.jsx          # React bootstrap
        ├── App.jsx           # Config vs Dashboard routing, API polling
        ├── index.css         # Tailwind imports
        └── components/
            ├── ConfigForm.jsx    # Credentials + metadata form
            ├── Dashboard.jsx     # Stats, stop/download, log panel
            ├── LogViewer.jsx     # SSE log stream consumer
            └── HistoryModal.jsx  # Past jobs table + download links
```

**Runtime-generated files (working directory = project root or container `/app`):**

| File | Purpose |
|------|---------|
| `{FolderName}.json` | Book catalog (sanitized Drive folder name) |
| `books.json` | Default output when root folder id is `root` |
| `scan_history.json` | Last 100 job summaries (includes config snapshot) |
| `temp_{drive_file_id}.pdf` | Temporary download (deleted after processing) |
| `temp_{drive_file_id}.png` | Temporary thumbnail (deleted after Cloudinary upload) |

---

## Core Modules & Functions

### `backend/main.py`

- Creates `FastAPI` app titled *Google Drive Scanner Control Panel*.
- Mounts API at prefix `/api`.
- Serves `backend/static` at `/` when built; otherwise returns JSON placeholder at `/`.

### `backend/api.py` — REST API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/start` | Start background scan (body: `StartConfig`) |
| `POST` | `/api/stop` | Signal running job to stop |
| `POST` | `/api/reset` | Reset in-memory job manager to `IDLE` |
| `GET` | `/api/status` | Current job status, counters, elapsed time, last logs snippet |
| `GET` | `/api/history` | All entries from `scan_history.json` |
| `GET` | `/api/logs/stream` | **SSE** stream of log lines (`text/event-stream`) |
| `GET` | `/api/download?filename=` | Download JSON result file (basename only; traversal-safe) |

**`StartConfig` (Pydantic):**

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `service_account_json` | `str` | Yes | — | Full JSON string of Google service account key |
| `cloudinary_cloud_name` | `str` | Yes | — |
| `cloudinary_api_key` | `str` | Yes | — |
| `cloudinary_api_secret` | `str` | Yes | — |
| `drive_root_id` | `str?` | No | `null` → uses Drive `'root'` |
| `academic_year_id` | `str?` | No | `'Direct'` |
| `term_id` | `str?` | No | `'Direct'` |
| `subject_id` | `str?` | No | `'Direct'` |
| `book_type_id` | `str?` | No | `'Direct'` |
| `release_year` | `str?` | No | `'Direct'` |

Metadata fields are used in **flat folder mode**; in nested mode, folder names overwrite the hierarchy keys during traversal.

### `backend/job_manager.py`

**Singleton:** `job_manager` (`JobManager` class).

| Method / attribute | Responsibility |
|--------------------|----------------|
| `start_job(config: dict)` | Returns `(success: bool, message: str)`; spawns daemon thread |
| `stop_job()` | Sets `threading.Event` to stop scanner |
| `reset()` | Clears state to `IDLE` |
| `get_status()` | JSON-serializable status dict |
| `JobStatus` enum | `IDLE`, `RUNNING`, `COMPLETED`, `ERROR`, `STOPPED` |

**`get_status()` response shape:**

```json
{
  "status": "RUNNING",
  "counters": {
    "processed": 0,
    "skipped": 0,
    "errors": 0,
    "total_scanned_so_far": 0
  },
  "elapsed_seconds": 42,
  "current_logs": ["..."],
  "output_file": "My Books.json"
}
```

### `backend/scanner.py` — Core scanning engine

**Primary entry for programmatic use:**

```python
start_scan_job(
    config: dict,
    log_callback: Callable[[str], None] | None,
    progress_callback: Callable[..., None] | None,  # kwargs: processed, skipped, errors
    stop_event: threading.Event,
    set_meta_info_callback: Callable[[filename, folder_name], None] | None = None,
) -> None
```

| Function | Inputs | Outputs |
|----------|--------|---------|
| `get_drive_service(service_account_json)` | JSON string | `googleapiclient.discovery.Resource` |
| `download_file(service, file_id, file_name)` | Drive service, ids | Local path `temp_{file_id}.pdf` |
| `process_pdf(pdf_path, file_id, drive_file_name, log_callback)` | Paths, ids | `dict` with `page_count`, `file_size_mb`, `image_url` or `None` |
| `process_level(...)` | Recursive traversal state | Side effects: append JSON, callbacks |
| `load_processed_ids(output_file)` | Path | `set` of `drive_file_id` |
| `append_record(record, output_file)` | Record dict, path | Appends to JSON array on disk |

**Drive folder hierarchy (nested mode):**

| Level | Folder role | Context key set |
|-------|-------------|-----------------|
| 0 | Academic Year | `academic_year_id` |
| 1 | Term | `term_id` |
| 2 | Subject | `subject_id` |
| 3 | Book Type | `book_type_id` |
| 4 | Release Year | `release_year` |
| 5 | PDF files | Processed as books |

**Flat folder mode:** If level 0 has no subfolders but contains PDFs, all PDFs are processed with metadata from `config` (`academic_year_id`, etc.).

**Book record schema (each array element):**

```json
{
  "name": "Book Title.pdf",
  "drive_file_id": "1abc...",
  "academic_year_id": "2024-2025",
  "term_id": "First Term",
  "subject_id": "Arabic",
  "book_type_id": "Student Book",
  "release_year": "2025",
  "page_count": 120,
  "file_size_mb": 15,
  "image_url": "https://res.cloudinary.com/.../pdf_thumbnails/..."
}
```

**Incremental scan:** `load_processed_ids` skips files whose `drive_file_id` already exists in the output JSON.

### `backend/history.py`

**Singleton:** `history_manager`.

| Method | Description |
|--------|-------------|
| `add_entry(entry)` | Prepends entry with ISO `timestamp`, saves to `scan_history.json` (max 100) |
| `get_all()` | Returns full history list |

History entries include `config` (with secrets), `stats`, `status`, `output_file`, `folder_name`, `elapsed_seconds`.

### Frontend modules (UI integration reference)

| Component | Role |
|-----------|------|
| `App.jsx` | Polls `/api/status` every 2s; routes CONFIG ↔ DASHBOARD |
| `ConfigForm.jsx` | Collects credentials; persists to **browser localStorage** |
| `Dashboard.jsx` | Stats, stop, download, history modal |
| `LogViewer.jsx` | `EventSource('/api/logs/stream')` |
| `HistoryModal.jsx` | `GET /api/history` |

---

## Data Flow

```
┌─────────────────┐     POST /api/start      ┌──────────────────┐
│  Dashboard /    │ ───────────────────────► │   job_manager    │
│  External Agent │     (StartConfig)        │  (background     │
└────────┬────────┘                          │   thread)        │
         │                                   └────────┬─────────┘
         │ GET /api/status, SSE /api/logs/stream       │
         │                                            ▼
         │                                   ┌──────────────────┐
         │                                   │  scanner.py      │
         │                                   │  start_scan_job  │
         │                                   └────────┬─────────┘
         │                                            │
         │                    ┌───────────────────────┼───────────────────────┐
         │                    ▼                       ▼                       ▼
         │           ┌────────────────┐    ┌─────────────────┐    ┌──────────────────┐
         │           │ Google Drive   │    │ PyMuPDF         │    │ Cloudinary       │
         │           │ API (list/get) │    │ (page 2 thumb)  │    │ pdf_thumbnails/  │
         │           └────────┬───────┘    └────────┬────────┘    └────────┬─────────┘
         │                    │                       │                       │
         │                    └───────────────────────┴───────────────────────┘
         │                                            │
         │                                            ▼
         │                                   ┌──────────────────┐
         │                                   │ {folder}.json    │
         │                                   │ (book catalog)   │
         │                                   └────────┬─────────┘
         │                                            │
         │ GET /api/download                          ▼
         └──────────────────────────────────  scan_history.json
```

**Per-file pipeline:**

1. List folders/PDFs under `drive_root_id` (recursive or flat).
2. Skip if `drive_file_id` in existing output JSON.
3. Download PDF → `temp_{id}.pdf`.
4. Extract `page_count`, `file_size_mb`; render page 2 (or 1) → PNG.
5. Upload PNG to Cloudinary (`folder="pdf_thumbnails"`, `public_id=file_id`).
6. Append record to output JSON; update progress counters; emit log lines.
7. Delete temp PDF/PNG.

---

## Integration Guide (for Dashboard / Agent merging)

### Integration strategies

| Strategy | When to use |
|----------|-------------|
| **HTTP client** | Remote or microservice: call `/api/*` from your Dashboard backend or agent orchestrator. |
| **Python import** | Same process / monorepo: import `scanner.start_scan_job` or wrap `job_manager`. |
| **Embed UI** | Serve or iframe the built React app from `backend/static`, or reimplement forms against the API. |
| **Fork catalog only** | Run scans separately; ingest `{folder}.json` via `/api/download` or shared volume. |

### What to import (Python)

```python
# Option A: Full job orchestration (status, logs, threading included)
from backend.job_manager import job_manager, JobStatus

# Option B: Low-level scanner only (you provide callbacks + stop_event)
from backend.scanner import start_scan_job
import threading

# Option C: History
from backend.history import history_manager
```

**Note:** Run with project root on `PYTHONPATH` (e.g. `cd books-scanner` before `uvicorn` or imports).

### Important types and contracts

**Job status enum:** `JobStatus` — string values `IDLE`, `RUNNING`, `COMPLETED`, `ERROR`, `STOPPED`.

**Config dict** (same keys as `StartConfig`):

```python
config = {
    "service_account_json": open("service-account.json").read(),
    "cloudinary_cloud_name": "...",
    "cloudinary_api_key": "...",
    "cloudinary_api_secret": "...",
    "drive_root_id": "FOLDER_ID_OR_NULL",
    "academic_year_id": "Direct",
    "term_id": "Direct",
    "subject_id": "Direct",
    "book_type_id": "Direct",
    "release_year": "Direct",
}
```

**Progress callback signature:**

```python
def progress_callback(*, processed=0, skipped=0, errors=0):
    ...
```

**Log callback:** Receives strings like `[HH:MM:SS] [INFO] message`.

### Dependencies to install

**Backend:**

```bash
pip install -r requirements.txt
```

**Frontend (only if building UI):**

```bash
cd frontend && npm install && npm run build
```

**System (Dockerfile):** `build-essential` for PyMuPDF wheels on slim images.

**Google setup:**

1. Create a service account with Drive API enabled.
2. Share target Drive folder(s) with the service account email (read access).
3. Pass the full JSON key in `service_account_json`.

**Cloudinary setup:** Account with upload preset not required; uses signed server-side upload API.

### HTTP usage example (external Dashboard)

```python
import requests

BASE = "http://localhost:8000/api"

# Start scan
r = requests.post(f"{BASE}/start", json={
    "service_account_json": service_account_json_string,
    "cloudinary_cloud_name": "my_cloud",
    "cloudinary_api_key": "key",
    "cloudinary_api_secret": "secret",
    "drive_root_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz",
})
r.raise_for_status()

# Poll status
status = requests.get(f"{BASE}/status").json()
# status["status"], status["counters"], status["output_file"]

# Stop
requests.post(f"{BASE}/stop")

# Download catalog
filename = status.get("output_file") or "books.json"
catalog = requests.get(f"{BASE}/download", params={"filename": filename})
books = catalog.json()
```

**SSE logs (JavaScript / agent watcher):**

```javascript
const es = new EventSource("http://localhost:8000/api/logs/stream");
es.onmessage = (e) => console.log(e.data);
```

### Python embedding example (in-process agent)

```python
import threading
from collections import deque
from backend.scanner import start_scan_job

logs = deque(maxlen=1000)
stop = threading.Event()

def log_cb(msg):
    logs.append(msg)

def progress_cb(*, processed=0, skipped=0, errors=0):
    # Update your agent state / metrics
    pass

def on_meta(filename, folder_name):
    print(f"Writing to {filename} for folder {folder_name}")

thread = threading.Thread(
    target=start_scan_job,
    args=(config, log_cb, progress_cb, stop, on_meta),
    daemon=True,
)
thread.start()

# Later: stop.set()
```

### Mounting into an existing FastAPI app

```python
from fastapi import FastAPI
from backend.api import router as scanner_router

app = FastAPI()
app.include_router(scanner_router, prefix="/scanner/api", tags=["books-scanner"])
```

Adjust frontend `API_BASE` or proxy paths accordingly.

### OpenAPI

With the server running: `http://localhost:8000/docs` (Swagger UI) for interactive API exploration.

---

## Environment Variables

**This project does not use `.env` files or `os.environ` for configuration.**

All secrets and targets are passed **per request** in the `POST /api/start` body (or programmatic `config` dict). Optional operational env vars are only those used by your host (e.g. `PORT` if you wrap uvicorn yourself)—none are defined by this codebase.

| Variable | Required | Description |
|----------|----------|-------------|
| — | — | No first-class env vars in repo |

**Credential handling:**

| Layer | Behavior |
|-------|----------|
| Backend | Credentials held in memory for active job; written into `scan_history.json` on completion |
| Frontend | Saves credentials to **browser `localStorage`** (keys prefixed `scanner_*`) |

For a centralized Dashboard, prefer passing secrets from your secure vault per job and **avoid** relying on frontend localStorage in production.

---

## Potential Issues & Notes

### Integration conflicts

1. **Single global job:** `JobManager` is a singleton—only one scan runs at a time. Multiple agents must queue externally.
2. **Working directory:** Output JSON and `scan_history.json` are written to the **process CWD**. Docker uses `/app`; align volume mounts for persistence.
3. **Port / path collision:** Default port `8000` and `/api` prefix may clash with an existing Dashboard API—use a reverse proxy or router prefix.
4. **CORS:** `main.py` allows `localhost:5173`, `localhost:8000`, and `"*"`. Tighten for production when merging origins.
5. **Static mount order:** In production, `StaticFiles` is mounted at `/` **after** `/api`; API routes take precedence. Do not mount another catch-all at `/` without ordering care.
6. **No `backend/__init__.py`:** Imports assume running from repo root (`uvicorn backend.main:app`). Package layout may need `__init__.py` if vendored as a library.
7. **Frontend status bug:** `App.jsx` does not map `output_file` from `/api/status` into React state, so the Dashboard download button may not appear until fixed—API still returns `output_file`; agents should read it from status JSON directly.

### Security

- Service account JSON and Cloudinary secrets appear in **`scan_history.json`** after each run—restrict file permissions or strip secrets in a wrapper before integration.
- `/api/download` only allows basenames (no `../` traversal) but any readable `.json` in CWD can be requested—run with minimal filesystem exposure.
- README states backend does not persist secrets to disk; **history file contradicts this** for completed jobs.

### Operational

- **Resumable scans:** Re-running with the same output filename skips known `drive_file_id` values.
- **Thumbnail page:** Uses **page index 1** (second page) when `page_count >= 2`, else page 0—tuned for book covers/interior preview.
- **Drive scope:** `https://www.googleapis.com/auth/drive.readonly` only.
- **Stop is cooperative:** `stop_event` is checked between files/folders; current file may finish.
- **Log buffer:** In-memory deque max **1000** lines; SSE streams from this buffer.
- **requirements.txt unpinned:** Pin versions in production for reproducible agent deployments.

### Google Drive prerequisites

- Folder must be shared with the service account email.
- Wrong folder ID or missing share produces `CRITICAL` log hints in flat/empty folder paths.

---

## Quick reference

| Item | Value |
|------|--------|
| Main API prefix | `/api` |
| Production URL | `http://<host>:8000` |
| Dev frontend | `http://localhost:5173` |
| Core Python module | `backend/scanner.py` → `start_scan_job` |
| Default catalog file | `books.json` (root) or `{sanitized_folder_name}.json` |
| History file | `scan_history.json` |
| Cloudinary folder | `pdf_thumbnails` |
| Drive scope | Read-only |

---

*Generated for agent/dashboard integration. Update this file when API routes or record schemas change.*
