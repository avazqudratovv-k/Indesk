#!/bin/bash
# Daily dump of the Indesk database. Run from cron on the host (see deploy/RUNBOOK.md). Keeps 7 days.
# Usage: deploy/backup.sh [repo-dir] [backup-dir]
set -euo pipefail

REPO_DIR="${1:-/root/Indesk}"
BACKUP_DIR="${2:-/root/indesk-backups}"
KEEP_DAYS=7

umask 077
mkdir -p "$BACKUP_DIR"
cd "$REPO_DIR"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TMP="$BACKUP_DIR/.indesk-$STAMP.dump.partial"
OUT="$BACKUP_DIR/indesk-$STAMP.dump"

# Custom format (-Fc) so pg_restore can pick what to restore. Runs as the db superuser inside the container.
docker compose -f compose.prod.yaml exec -T db pg_dump -U indesk -d indesk -Fc >"$TMP"
test -s "$TMP"
mv "$TMP" "$OUT"

find "$BACKUP_DIR" -maxdepth 1 -name 'indesk-*.dump' -mtime +"$KEEP_DAYS" -delete
echo "backup written: $OUT"
