# High School Rebellion Chat

A minimal realtime chat app with semantic search.

Tech
- Backend: FastAPI + Socket.IO, SQLAlchemy
- DB: Postgres + pgvector (SQLite fallback)
- Embeddings: sentence-transformers (all-MiniLM-L6-v2)
- Frontend: Vanilla JS/HTML/CSS

Run locally (Docker)
- Prereqs: Docker, Docker Compose
- Env: see .env (DATABASE_URL, SECRET_KEY)
- Start: docker-compose up --build
- App: http://localhost:8000
- DB: Postgres with pgvector (CREATE EXTENSION is in init.sql)
- Notes: embeddings are generated on message send; semantic search requires Postgres for vector index, but falls back to Python scoring on SQLite.

Run locally (without Docker)
- pip install -r backend/requirements.txt
- cd backend && python main.py
- For Postgres: set DATABASE_URL in .env and ensure CREATE EXTENSION vector; (init.sql)

API
- POST /users -> create user { name, email, password }
- POST /login -> returns { access_token, user }
- POST /messages (Bearer auth) -> { receiver_id, message } (sender from JWT)
- GET /messages?userId=...&limit=... (Bearer auth)
- GET /semantic-search?userId=...&q=...&limit=... (Bearer auth)
- GET /performance -> perf metrics

Files
- Backend: backend/main.py, backend/models.py, backend/semantic_search.py
- Frontend: frontend/index.html, frontend/chat.html
- Vector: pgvector enabled via init.sql, index ensured at app startup

Scaling notes (summary)
- Breaking point (e2-standard-2: 2 vCPU, 8GB):
  - Assume ~1 msg/sec/user, ~2–5ms DB insert, ~5–10ms emit, ~10–20ms embedding (MiniLM CPU).
  - Bottlenecks: CPU (embeddings), DB writes, websocket fanout.
  - ~50–100 msgs/sec sustainable on CPU before embedding becomes dominant; move embeddings async to scale.
- Monitoring
  - Implemented: /performance reports avg/max processing time, msgs/sec, CPU/mem.
  - Add: DB latency, queue depth (if using workers), Socket.IO connection count.
- Mitigations
  - Offload embeddings to background worker (Celery/RQ) or embedding API; cache recent text->vector.
  - Add Postgres indexes: ivfflat on messages.embedding (done). Partition messages by user pair for large datasets.
  - Horizontal scale: sticky WS via ingress, shared DB/Redis. Use HNSW for better recall/latency if supported.
  - Pagination for chat history; backpressure for high send rates.

Deployment
- Render/Fly:
  - Deploy backend from backend/ as a web service -> start: python main.py
  - Provision Postgres, set DATABASE_URL and SECRET_KEY.
  - Ensure pgvector: run CREATE EXTENSION IF NOT EXISTS vector; once.
  - Static files served at /static; / and /chat serve frontend pages.

Validation
- Create users via UI (/)
- Login, open /chat in two browsers, send messages
- Use search bar with queries like "homework", "number", etc.