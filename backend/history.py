import json
import os
import time
from datetime import datetime
from threading import Lock

HISTORY_FILE = 'scan_history.json'

class HistoryManager:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HistoryManager, cls).__new__(cls)
            cls._instance.history = []
            cls._instance.load()
        return cls._instance

    def load(self):
        if not os.path.exists(HISTORY_FILE):
            self.history = []
            return

        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    self.history = []
                    return
                self.history = json.loads(content)
                # Ensure it's a list
                if not isinstance(self.history, list):
                    self.history = []
        except Exception as e:
            print(f"Error loading history: {e}")
            self.history = []

    def save(self):
        with self._lock:
            try:
                with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                    json.dump(self.history, f, ensure_ascii=False, indent=4)
            except Exception as e:
                print(f"Error saving history: {e}")

    def add_entry(self, entry):
        # Entry structure:
        # {
        #   "id": "uuid",
        #   "timestamp": "ISO string",
        #   "config": {...},
        #   "stats": { processed, skipped, errors, elapsed },
        #   "status": "COMPLETED" | "STOPPED" | "ERROR",
        #   "output_file": "filename.json",
        #   "folder_name": "folder name"
        # }
        entry['timestamp'] = datetime.now().isoformat()
        # Add to beginning of list
        self.history.insert(0, entry)
        # Limit history size (optional, say 100 entries)
        if len(self.history) > 100:
            self.history = self.history[:100]
        self.save()

    def get_all(self):
        return self.history

history_manager = HistoryManager()
