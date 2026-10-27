#!/bin/bash
# Runs once, when the db volume is first created (docker-entrypoint-initdb.d), as the superuser.
# Creates the two roles of DECISIONS #118: a migrator that owns the schema and an app role that can
# only read and write rows. Passwords come from the container environment, never from this file.
set -euo pipefail

: "${POSTGRES_MIGRATOR_PASSWORD:?POSTGRES_MIGRATOR_PASSWORD is not set}"
: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD is not set}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v dbname="$POSTGRES_DB" \
  -v migrator_password="$POSTGRES_MIGRATOR_PASSWORD" \
  -v app_password="$POSTGRES_APP_PASSWORD" <<'SQL'
CREATE ROLE indesk_migrator LOGIN PASSWORD :'migrator_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE indesk_app LOGIN PASSWORD :'app_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

-- pgvector (P14): only a superuser may create it, so it is made here, once, on a fresh volume. Migration
-- 0005 then finds it. An existing volume needs the same statement by hand (see the migration).
CREATE EXTENSION IF NOT EXISTS vector;

-- The migrator owns the database, so it also owns the public schema and every table it creates.
ALTER DATABASE :"dbname" OWNER TO indesk_migrator;
REVOKE ALL ON DATABASE :"dbname" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"dbname" TO indesk_migrator, indesk_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
-- Table grants for the app role are issued by migration 0004, so they follow the schema.
SQL
