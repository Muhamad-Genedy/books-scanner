# Stage 1: Build Frontend
# Stage 1: Build Frontend
FROM node:18-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Setup Backend & Serve
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies if any (e.g. for PyMuPDF sometimes needed, but slim usually ok)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Backend Code
COPY backend/ ./backend/

# Copy Frontend Build to Backend Static Folder
# backend/main.py expects static files in 'backend/static'
# Vite outputs to ../backend/static from /app/frontend, effectively /app/backend/static
COPY --from=frontend-build /app/backend/static ./backend/static

# Expose port
EXPOSE 8000

# Run Application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
