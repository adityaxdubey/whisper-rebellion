FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code to root level (this is the fix!)
COPY backend/ .
COPY frontend/ ./frontend/

# Create a non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

EXPOSE 8000

# Run from the correct location
CMD ["python", "main.py"]
