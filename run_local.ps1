# Run Local Development Environment

Write-Host "Setting up Local Environment..." -ForegroundColor Cyan

# 1. Setup Backend
Write-Host "Installing Backend Dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# 2. Setup Frontend
Write-Host "Installing Frontend Dependencies..." -ForegroundColor Yellow
cd frontend
npm install
cd ..

# 3. Start Servers
Write-Host "Starting Backend Server (Port 8000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"

Write-Host "Starting Frontend Server..." -ForegroundColor Green
cd frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm run dev"

Write-Host "Both servers are starting in new windows." -ForegroundColor Cyan
Write-Host "Backend: http://localhost:8000/docs"
Write-Host "Frontend: http://localhost:5173"
