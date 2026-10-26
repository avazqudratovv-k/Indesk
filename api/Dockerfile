FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# /data/uploads is owned by the app user here, so a new named volume mounted on it inherits that owner.
RUN useradd --system --uid 10001 --create-home app \
    && mkdir /app /data /data/uploads \
    && chown app:app /app /data /data/uploads \
    && chmod 700 /data/uploads
WORKDIR /app

# Production image (compose.prod.yaml, target: prod): runtime packages only, no test or lint tools.
FROM base AS prod
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY --chown=app:app . .
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Dev image: includes test and lint tools. It is the LAST stage, so a plain `build: ./api` (compose.yaml) gets it.
FROM base AS dev
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

COPY --chown=app:app . .
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
