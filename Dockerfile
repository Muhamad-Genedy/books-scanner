FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies if needed (e.g. for PyMuPDF or general utilities)
# PyMuPDF binary wheels usually work fine, but if you need build tools:
# RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Command to run the script
# NOTE: This script runs once and exits. For a scheduled job, use Coolify's Cron syntax or a loop.
CMD ["python", "app.py"]
