FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files but exclude .env
COPY backend/*.py .
COPY backend/schemas.py .
COPY backend/auth.py .
COPY backend/models.py .
COPY backend/database.py .
COPY backend/semantic_search.py .
COPY backend/main.py .

COPY frontend/ ./frontend/

EXPOSE 8000
CMD ["uvicorn", "main:socket_app", "--host", "0.0.0.0", "--port", "8000"]
