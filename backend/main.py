from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from .api import router as api_router

app = FastAPI(title="Google Drive Scanner Control Panel")

# CORS Configuration
origins = [
    "http://localhost:5173", # Vite dev server
    "http://localhost:8000",
    "*" # For local dev ease
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Router
app.include_router(api_router, prefix="/api")

# Serve Frontend Static Files (Production Mode)
# We expect the frontend build to be in 'backend/static' (or just 'static' relative to here)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
else:
    # Just a placeholder route if frontend isn't built yet
    @app.get("/")
    def read_root():
        return {"message": "Backend is running. Frontend not found in static/."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
