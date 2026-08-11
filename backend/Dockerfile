FROM python:3.12-slim

# Build context must be repo root: docker build -f backend/Dockerfile .
# This layout mirrors the local repo structure so brain/ is reachable from
# backend/routes via the same relative path used in development.
WORKDIR /app/looper

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY requirements-brain.txt requirements-brain.txt
RUN pip install --no-cache-dir -r requirements-brain.txt

COPY backend/ backend/
COPY brain/ brain/
COPY tools/ tools/

RUN mkdir -p /app/data
ENV LOOPER_DB_URL=sqlite:////app/data/looper.db

EXPOSE 8000

# slim image has no curl — use python for the healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).status==200 else 1)"

WORKDIR /app/looper/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
