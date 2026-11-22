# Jeden kontener: FastAPI serwuje API (/api/…) i zbudowany frontend (/). Render, Railway, Fly.io, Hugging Face.
# Budowa:  docker build -t zatrzymaj-wode .     Uruchomienie:  docker run -p 10000:10000 zatrzymaj-wode

# ── 1. frontend (Vite → statyczne pliki) ──
FROM node:22.11.0-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── 2. backend (Python + uv) ──
FROM python:3.12.7-slim
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv
RUN pip install --no-cache-dir uv==0.13.9
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
COPY data/knowledge /app/data/knowledge
COPY data/imgw /app/data/imgw
COPY --from=web /web/dist /app/frontend/dist
# rozszerzenie DuckDB do czytania krajowego pliku działek (obrys) – pobrane przy budowie, nie przy pierwszym obrysie
RUN /app/.venv/bin/python -c "import duckdb; duckdb.connect().execute('INSTALL httpfs')"
ENV WODA_CACHE_DIR=/var/cache/woda PORT=10000
RUN mkdir -p /var/cache/woda
EXPOSE 10000
CMD ["sh", "-c", "/app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips='*'"]
