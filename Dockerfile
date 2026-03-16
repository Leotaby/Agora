# ============================================================
# NEXUS = HumanTwin — Dockerfile
# Multi-stage: backend (Python/FastAPI) + frontend (Node/Vue)
# ============================================================

# --- Backend ---
FROM python:3.11-slim AS backend

WORKDIR /app

# Install uv
RUN pip install uv --no-cache-dir

COPY backend/pyproject.toml backend/requirements.txt ./
RUN uv pip install --system -r requirements.txt

COPY backend/ ./

EXPOSE 5001
CMD ["python", "run.py"]


# --- Frontend ---
FROM node:20-slim AS frontend

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./

EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
