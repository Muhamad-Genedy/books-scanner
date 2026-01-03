# Google Drive Scanner Control Panel

A full-stack web application to manage and monitor the Google Drive PDF scanning process.

## Features
- **Web-based Configuration**: Easily input Google Credentials and Cloudinary keys.
- **Real-time Monitoring**: Watch the progress bar and live logs as the scanner traverses folders.
- **Incremental Scanning**: Resumes where it left off (persisted in `books.json`).
- **One-click Download**: Download the final JSON dataset directly from the UI.
- **Dockerized**: Ready for deployment on Coolify or any Docker host.

## Architecture
- **Backend**: Python FastAPI with background threads for scanning.
- **Frontend**: React (Vite) + TailwindCSS.
- **Deployment**: Multi-stage Docker build serving both frontend and backend on port 8000.

## 🚀 Quick Start (Docker)

1. **Build the image**:
   ```bash
   docker build -t scanner-panel .
   ```

2. **Run the container**:
   ```bash
   docker run -p 8000:8000 scanner-panel
   ```

3. **Open Browser**:
   Navigate to [http://localhost:8000](http://localhost:8000)

## 🛠️ Local Development

### Backend
1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the server:
   ```bash
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Frontend
1. Navigate to frontend:
   ```bash
   cd frontend
   ```
2. Install packages:
   ```bash
   npm install
   ```
3. Run development server:
   ```bash
   npm run dev
   ```
4. Open [http://localhost:5173](http://localhost:5173). Note that you might need to configure CORS or proxy in `vite.config.js` if running separately, but the backend is configured to allow localhost:5173.

## 🔒 Security Note
Credentials (Service Account JSON and Cloudinary Keys) are **held in memory** only. They are not saved to disk. If you restart the container, you will need to re-enter them to start a new job. This is by design to prevent secrets from persisting on the server filesystem.
