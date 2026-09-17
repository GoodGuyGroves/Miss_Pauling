# ---------- Stage 1: build the docs site and the runtime site-packages ----------
FROM python:3.13-alpine AS builder

ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build

COPY requirements.txt .
# Runtime dependencies only: everything above the "docs build only" marker in requirements.txt
RUN sed '/# --- docs build only/,$d' requirements.txt > requirements-runtime.txt \
    && pip install --prefix=/runtime -r requirements-runtime.txt
# Full set (including mkdocs) just for building the docs; discarded with this stage
RUN pip install -r requirements.txt
COPY docs docs
RUN cd docs && mkdocs build

# ---------- Stage 2: runtime ----------
FROM python:3.13-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    MISS_PAULING_DB_PATH=/data/sqlite.db

COPY --from=builder /runtime /usr/local

WORKDIR /app
COPY shared shared
COPY website website
COPY fastdl fastdl
COPY admin_roles.py .
COPY --from=builder /build/docs/site docs/site

# Non-root user; /data holds all persistent state (SQLite, maps, mapcycle state). Mount a volume there.
RUN addgroup -S -g 10001 app && adduser -S -D -u 10001 -G app -h /home/app app \
    && mkdir -p /data/maps \
    && chown -R app:app /data
USER app

EXPOSE 8000

# --proxy-headers trusts X-Forwarded-Proto/For from the ingress so generated URLs use https
CMD ["uvicorn", "website.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
