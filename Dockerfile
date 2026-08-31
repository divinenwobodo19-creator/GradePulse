# ── GradePulse Multi-Stage Dockerfile ──────────────────────────────────────────
# Targets:  backend  |  frontend
# Usage:
#   docker build --target backend -t gradepulse-api .
#   docker build --target frontend -t gradepulse-web ./gradepulse-web

# ══════════════════════════════════════════════════════════════════════════════
# Stage 1: Backend (Python / FastAPI)
# ══════════════════════════════════════════════════════════════════════════════
FROM python:3.12-slim AS backend

RUN addgroup --system gradepulse && adduser --system --ingroup gradepulse gradepulse

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY linucb_brain/ linucb_brain/
COPY ingest.py .
COPY pyproject.toml .

RUN mkdir -p /data && chown -R gradepulse:gradepulse /app /data

USER gradepulse

ENV PYTHONPATH=/app \
    HOST=0.0.0.0 \
    PORT=8000 \
    WEB_CONCURRENCY=2 \
    BRAIN_STATE_PATH=/data/brain_state.json \
    CONFIG_PATH=/data/class_config.json \
    USER_DB_PATH=/data/gradepulse_users.db \
    BACKUP_DIR=/data/backups \
    BACKUP_ENABLED=true \
    LOG_LEVEL=INFO

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "linucb_brain.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

# ══════════════════════════════════════════════════════════════════════════════
# Stage 2: Frontend (Node.js / Next.js)
# ══════════════════════════════════════════════════════════════════════════════
FROM node:20-alpine AS frontend

WORKDIR /app

COPY gradepulse-web/package.json gradepulse-web/package-lock.json* ./
RUN npm install

COPY gradepulse-web/ .

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
