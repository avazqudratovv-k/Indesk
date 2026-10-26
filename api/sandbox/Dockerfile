# The sandbox image: pandas and numpy plus a tiny stdlib server. No secrets, no database client,
# no HTTP framework. It runs as a non-root user; compose adds the other limits (see compose.yaml).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN useradd --system --uid 10002 --no-create-home --shell /usr/sbin/nologin sandbox

COPY requirements.txt /tmp/requirements.txt
RUN pip install --only-binary=:all: -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Owned by root and read-only to the sandbox user: model code cannot change the server or the runner.
COPY indesk_sandbox /srv/indesk_sandbox
WORKDIR /srv
USER sandbox

CMD ["python", "-m", "indesk_sandbox.server"]
