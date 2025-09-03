FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend and frontend directories
# .dockerignore will prevent .env and other unwanted files from being copied
COPY backend/ .
COPY frontend/ ./frontend/

# Expose port and set the command
EXPOSE 10000
CMD ["sh", "-c", "uvicorn main:socket_app --host 0.0.0.0 --port ${PORT}"]
