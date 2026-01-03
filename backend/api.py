from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import os
import time
import asyncio
from typing import Optional
from .job_manager import job_manager, JobStatus
from .scanner import OUTPUT_FILE

router = APIRouter()

class StartConfig(BaseModel):
    service_account_json: str
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str
    drive_root_id: Optional[str] = None
    academic_year_id: Optional[str] = 'Direct'
    term_id: Optional[str] = 'Direct'
    subject_id: Optional[str] = 'Direct'
    release_year: Optional[str] = 'Direct'

@router.post("/start")
async def start_scan(config: StartConfig):
    success, msg = job_manager.start_job(config.dict())
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "started", "message": msg}

@router.post("/stop")
async def stop_scan():
    success, msg = job_manager.stop_job()
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "stopped", "message": msg}

@router.post("/reset")
async def reset_job():
    job_manager.reset()
    return {"status": "reset", "message": "Job state reset successfully"}

@router.get("/status")
async def get_status():
    return job_manager.get_status()

async def log_generator():
    """Generator for Server-Sent Events (SSE) that streams new logs."""
    last_idx = 0
    while True:
        logs = list(job_manager.logs)
        if len(logs) > last_idx:
            new_logs = logs[last_idx:]
            for log in new_logs:
                yield f"data: {log}\n\n"
            last_idx = len(logs)
        
        if job_manager.status not in [JobStatus.RUNNING, JobStatus.IDLE] and last_idx >= len(logs):
            # If job is done and we sent all logs, maybe close? 
            # Or just keep open for a bit?
            # Let's keep it open but poll slower.
            pass

        await asyncio.sleep(0.5)

@router.get("/logs/stream")
async def stream_logs():
    return StreamingResponse(log_generator(), media_type="text/event-stream")

@router.get("/download")
async def download_results():
    if not os.path.exists(OUTPUT_FILE):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(OUTPUT_FILE, media_type='application/json', filename='books.json')
