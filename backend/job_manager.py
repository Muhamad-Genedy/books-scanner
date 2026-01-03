import threading
import time
from collections import deque
from enum import Enum
from . import scanner

class JobStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    STOPPED = "STOPPED"

class JobManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JobManager, cls).__new__(cls)
            cls._instance.reset()
        return cls._instance

    def reset(self):
        self.status = JobStatus.IDLE
        self.counters = {
            "processed": 0,
            "skipped": 0,
            "errors": 0,
            "total_scanned_so_far": 0
        }
        self.logs = deque(maxlen=1000) # Keep last 1000 logs
        self.current_file = ""
        self.start_time = None
        self.end_time = None
        self.stop_event = threading.Event()
        self.thread = None
        self.active_config = None

    def add_log(self, message):
        self.logs.append(message)

    def update_progress(self, processed=0, skipped=0, errors=0):
        self.counters["processed"] += processed
        self.counters["skipped"] += skipped
        self.counters["errors"] += errors
        self.counters["total_scanned_so_far"] += (processed + skipped + errors)

    def start_job(self, config):
        if self.status == JobStatus.RUNNING:
            return False, "Job is already running"

        self.reset()
        self.status = JobStatus.RUNNING
        self.start_time = time.time()
        self.active_config = config
        self.stop_event.clear()

        def run():
            try:
                scanner.start_scan_job(
                    config,
                    self.add_log,
                    self.update_progress,
                    self.stop_event
                )
                if self.stop_event.is_set():
                    self.status = JobStatus.STOPPED
                    self.add_log("[SYSTEM] Job stopped by user.")
                else:
                    self.status = JobStatus.COMPLETED
                    self.add_log("[SYSTEM] Job completed successfully.")
            except Exception as e:
                self.status = JobStatus.ERROR
                self.add_log(f"[SYSTEM] Job failed: {e}")
            finally:
                self.end_time = time.time()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        return True, "Job started"

    def stop_job(self):
        if self.status == JobStatus.RUNNING:
            self.stop_event.set()
            return True, "Stopping job..."
        return False, "No job running"

    def get_status(self):
        elapsed = 0
        if self.start_time:
            end = self.end_time if self.end_time else time.time()
            elapsed = int(end - self.start_time)

        return {
            "status": self.status,
            "counters": self.counters,
            "elapsed_seconds": elapsed,
            "current_logs": list(self.logs)[-50:] # Return last 50 for polling, or separate API for full stream
        }

job_manager = JobManager()
