# Indesk deploy runbook (VPS)

Owner steps. Server: Hostinger VPS, host nginx owns ports 80 and 443, Ticketzy runs on the same machine and must keep working.
Repo folder on the server: `/root/Indesk`. Every command is one line in its own block. Run them in order.

Rules for this server:
- Never touch `/etc/nginx/conf.d/ticketzy.conf` or any other non-Indesk nginx file.
- Reload nginx, never restart or stop it.
- Never run `docker system prune`. It deletes Ticketzy's images too.
- Never run `docker compose down` without `-f compose.prod.yaml`.
- Never run `certbot renew --force-renewal`. Always name the host: `certbot --nginx -d <host>`.

## 1. Check the server before you start

Look at which Docker networks exist. The Indesk subnet in `.env` (`EDGE_SUBNET`) must not overlap any of them.

```
docker network inspect $(docker network ls -q) | grep Subnet
```

Check that port 4100 is free. No output means it is free.

```
ss -ltnp | grep ':4100'
```

Note how much memory Ticketzy uses now.

```
free -m
```

```
docker stats --no-stream
```

## 2. Clone

```
git clone <your repo url> /root/Indesk
```

```
cd /root/Indesk
```

## 3. Create .env

```
cp deploy/env.prod.example .env
```

```
chmod 600 .env
```

Generate the three database passwords, one at a time, and paste each into `.env`.

```
openssl rand -hex 24
```

```
openssl rand -hex 24
```

```
openssl rand -hex 24
```

Generate the auth secret and paste it into `.env`.

```
openssl rand -hex 32
```

Open `.env` and fill in: the three `POSTGRES_*` passwords, `AUTH_SECRET`, `GEMINI_API_KEY` (the paid key, with a monthly limit set in Google AI Studio), and check `EDGE_SUBNET` against step 1.

```
nano .env
```

Check the file parses (it prints nothing on success and never prints the values).

```
docker compose -f compose.prod.yaml config -q
```

## 4. Build

The build is heavy. Do it when Ticketzy is quiet. One image at a time keeps memory down.

```
export COMPOSE_PARALLEL_LIMIT=1
```

```
docker compose -f compose.prod.yaml build
```

## 5. Start the database and run the migrations

```
docker compose -f compose.prod.yaml up -d db redis
```

```
docker compose -f compose.prod.yaml run --rm migrate
```

## 6. Start everything

```
docker compose -f compose.prod.yaml up -d
```

```
docker compose -f compose.prod.yaml ps
```

Every service should be `running` or `healthy` (migrate shows as exited 0).

```
curl -s http://127.0.0.1:4100/api/health
```

Expected: `{"status":"ok"}`.

## 7. Back up nginx and fingerprint Ticketzy

```
cp -a /etc/nginx /root/nginx-backup-$(date +%Y%m%d-%H%M)
```

```
md5sum /etc/nginx/conf.d/ticketzy.conf
```

Write the checksum down. It must be identical in step 11.

## 8. Install the Indesk nginx file

```
cp deploy/nginx/indesk.conf /etc/nginx/conf.d/indesk.conf
```

```
nginx -t
```

If `nginx -t` fails, remove the new file and stop: `rm /etc/nginx/conf.d/indesk.conf`.

```
systemctl reload nginx
```

## 9. Check Ticketzy still answers

```
curl -sI https://ticketzy.uz
```

Do the same for every other site's URL on this server (for example its API host, like `https://api.ticketzy.uz`), one command per site:

```
curl -sI https://<other site's URL>
```

Each must answer as it did before step 8.

## 10. HTTPS

```
certbot --nginx -d indesk.76-13-198-17.sslip.io
```

## 11. Check Ticketzy was not changed

```
md5sum /etc/nginx/conf.d/ticketzy.conf
```

If the checksum differs from step 7, stop and restore the nginx backup from step 7 (use its real folder name):

```
cp -a /root/nginx-backup-<date>/. /etc/nginx/
```

```
nginx -t
```

```
systemctl reload nginx
```

Then ask for help before doing anything else.

```
curl -sI https://ticketzy.uz
```

## 12. Smoke checks

```
curl -s https://indesk.76-13-198-17.sslip.io/api/health
```

Then in a browser at https://indesk.76-13-198-17.sslip.io:
1. Sign up with a new account.
2. Check the cookies in the browser tools: both `indesk_access` and `indesk_refresh` are `Secure` and `HttpOnly`.
3. Upload the Seoul demo CSV.
4. Ask one question. The agents must appear one by one while the run goes (live stream), not all at the end.
5. Open the report.

Look at the logs for errors while you do this (see "Logs").

## 13. Backups

```
chmod +x deploy/backup.sh
```

Run one by hand.

```
deploy/backup.sh
```

```
ls -l /root/indesk-backups
```

Test a restore into a scratch database. This does not touch the live database. Use the file name from the listing above.

```
docker compose -f compose.prod.yaml exec -T db createdb -U indesk indesk_restore_check
```

```
docker compose -f compose.prod.yaml exec -T db pg_restore -U indesk -d indesk_restore_check --no-owner < /root/indesk-backups/<file>.dump
```

```
docker compose -f compose.prod.yaml exec -T db psql -U indesk -d indesk_restore_check -c "select count(*) from users"
```

```
docker compose -f compose.prod.yaml exec -T db dropdb -U indesk indesk_restore_check
```

Schedule the daily backup (03:15 server time). Add this line with `crontab -e`:

```
15 3 * * * /root/Indesk/deploy/backup.sh >> /root/indesk-backups/backup.log 2>&1
```

To restore for real after a disaster, stop the services that write to the database:

```
docker compose -f compose.prod.yaml stop api worker scheduler
```

Drop the damaged database and create an empty one, owned by the migrator role:

```
docker compose -f compose.prod.yaml exec -T db dropdb -U indesk indesk
```

```
docker compose -f compose.prod.yaml exec -T db createdb -U indesk -O indesk_migrator indesk
```

Load the dump (use the file name from `ls /root/indesk-backups`). Keep the owners: do not add `--no-owner` here, or later migrations fail:

```
docker compose -f compose.prod.yaml exec -T db pg_restore -U indesk -d indesk < /root/indesk-backups/<file>.dump
```

Start the services again:

```
docker compose -f compose.prod.yaml up -d
```

## Update to P14a (v0.2.0-p14a)

Use this section for the one big update from the live version (`12a069a`, deployed 2026-10-27) to P14a. It replaces the old short "Update" section. P14a adds PDF Ask: a new `parser` service, migration 0005 (`document_pages`, `chunks`, the pgvector extension) and migration 0006 (6-hour sessions).

`C:` = run on the Mac. Everything else runs on the server in `/root/Indesk`. Expected output is under each block. If an output differs, stop and ask before going on.

### A. Before you start (server)

Branch:

```
git branch --show-current
```

Expected: `main`

Commit:

```
git log -1 --oneline
```

Expected: starts with `12a069a` (the P13 Seoul sample commit).

Memory. Write down the "available" column and compare it with the number from step 1. The new `parser` service may use up to 1 GiB while it reads a PDF (its limit in `compose.prod.yaml`), and the build is heavy.

```
free -m
```

Expected: a table. "available" should be well above what the build and the parser need; if it is tight, wait until Ticketzy is quiet.

Disk. Write down the free space on `/`. A build needs room for new images.

```
df -h
```

Expected: `/` is not close to full.

Docker starts after a reboot:

```
systemctl is-enabled docker
```

Expected: `enabled`

Clock (certificates, sessions and daily caps all depend on it):

```
timedatectl
```

Expected: a line `System clock synchronized: yes`.

### B. Rollback point (Mac)

`C:` Tag the live version and push the tag. The rollback section needs this tag.

```
git tag v0.1.0-live 12a069a && git push origin v0.1.0-live
```

Expected: `* [new tag]         v0.1.0-live -> v0.1.0-live`

### C. Order of work

1. CI is green on the pull request.
2. Merge `developer` into `main`.
3. Tag the merge commit `v0.2.0-p14a` and push the tag (on the Mac, with `main` checked out and pulled):

```
git tag v0.2.0-p14a && git push origin v0.2.0-p14a
```

Expected: `* [new tag]         v0.2.0-p14a -> v0.2.0-p14a`

Only then go on to D.

### D. Update the server

1. Back up the database.

```
deploy/backup.sh
```

Expected: `backup written: /root/indesk-backups/indesk-<date>.dump`

2. Copy the dump to the Mac once. `C:` Use the file name from the line above.

```
scp root@76.13.198.17:/root/indesk-backups/indesk-<date>.dump ~/Downloads/
```

Expected: the file is copied; a size of more than 0 bytes.

3. Check that the vector extension is available in the running database.

```
docker compose -f compose.prod.yaml exec -T db psql -U indesk -d indesk -c "select name, default_version from pg_available_extensions where name = 'vector'"
```

Expected: one row, `vector | <version>`. No row means the database image has no pgvector: stop.

4. Check that the database is at migration 0004.

```
docker compose -f compose.prod.yaml exec -T db psql -U indesk -d indesk -c "select version_num from alembic_version"
```

Expected: `0004`

5. Create the extension as the `indesk` superuser. Migration 0005 runs as the migrator role, which may not create it (the `db-init` script only runs on a fresh volume).

```
docker compose -f compose.prod.yaml exec -T db psql -U indesk -d indesk -c "CREATE EXTENSION IF NOT EXISTS vector"
```

Expected: `CREATE EXTENSION` (or a NOTICE that it already exists).

6. Pull the code. You are on `main`, so this brings the merge commit.

```
git pull
```

Expected: a list of changed files, no conflict. If it says a local file would be overwritten, stop (see the nginx rule in the domain section: never edit repo files on the server).

7. Build one image at a time to save memory.

```
export COMPOSE_PARALLEL_LIMIT=1
```

```
docker compose -f compose.prod.yaml build
```

Expected: ends without error. **Warning: `build` alone restarts nothing.** The old containers keep running the old code until the next command.

8. Start the new version. The `migrate` service runs first, then the api starts.

```
docker compose -f compose.prod.yaml up -d
```

Expected: containers are created or recreated, including the new `parser`.

9. Remove the old, unused image layers. This removes dangling images only (it is not `docker system prune`, and it does not touch images that a container uses).

```
docker image prune -f
```

Expected: `Total reclaimed space: ...`

### E. After the migration

```
docker compose -f compose.prod.yaml exec -T db psql -U indesk -d indesk -c "select version_num from alembic_version"
```

Expected: `0006`. If it still says `0004` or `0005`, read the `migrate` log and do not run the smoke test:

```
docker compose -f compose.prod.yaml logs migrate
```

### F. Expected side effect

Migration 0006 sets the start of each session to the original login time. Anyone who logged in more than 6 hours ago must log in again. This is expected, not a fault.

## Role-split checks

These show that the app runs as the limited role and that migration 0005 gave it the right grants. Run them after "Update to P14a" step E. **Only the owner's own run of these commands marks the control "verified". Until then it stays "not verified".**

Which database users are connected:

```
docker compose -f compose.prod.yaml exec -T db psql -U indesk -d indesk -c "select usename, count(*) from pg_stat_activity where datname = 'indesk' group by usename order by usename"
```

Expected: `indesk_app` with a few connections (api, worker, scheduler). `indesk` may show one row for this command itself. `indesk_migrator` should not stay connected after `migrate` exited. The api, worker and scheduler must never appear as `indesk`.

`indesk_app` cannot create tables:

```
docker compose -f compose.prod.yaml exec -T db psql -U indesk_app -d indesk -c "CREATE TABLE should_fail (i int)"
```

Expected: `ERROR:  permission denied for schema public`. If a table was created, drop it and report it as a security failure.

`indesk_app` has all four grants on the two new tables (migration 0005):

```
docker compose -f compose.prod.yaml exec -T db psql -U indesk -d indesk -c "select c.relname, q.p, has_table_privilege('indesk_app', c.oid, q.p) as granted from pg_class c cross join (values ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE')) q(p) where c.relname in ('document_pages', 'chunks') and c.relkind = 'r' order by 1, 2"
```

Expected: 8 rows, every `granted` is `t`.

## Production env checklist

Names and the shape they need. Never paste a value into a chat or a ticket. All of these live in `/root/Indesk/.env` (mode 600).

| Name | Required shape | Notes |
|---|---|---|
| `ALLOWED_ORIGINS` | Comma-separated origins, each starting with `https://`, no path, no `localhost` or `127.0.0.1` | The api refuses to start in production otherwise. It is the write-request (CSRF) allow-list. |
| `EDGE_SUBNET` (the api sees it as `TRUSTED_PROXIES`) | One CIDR, for example a `/24`, that overlaps no other Docker network | Must not be empty. See "1. Check the server before you start". |
| Cookies `Secure` + `HttpOnly` | Nothing to set | Compose fixes `APP_ENV=production`, and the code makes the cookies `Secure` and `HttpOnly` from that. The api refuses to start if cookies would not be `Secure`. |
| `COMPOSE_FILE` | `compose.prod.yaml` | Makes a bare `docker compose` load the production file only. The commands here still use `-f compose.prod.yaml` on purpose. |

`SESSION_MAX_SECONDS` is fixed at the 6-hour default (21600). The production compose file does not pass it on, so it cannot be changed from `.env` in production.

The file parses and every required name is set (prints nothing on success):

```
docker compose -f compose.prod.yaml config -q
```

Expected: no output.

Each name reached the container. `grep -c` prints how many lines matched and never the value:

```
docker compose -f compose.prod.yaml exec -T api env | grep -c ALLOWED_ORIGINS
```

Expected: `1`

```
docker compose -f compose.prod.yaml exec -T api env | grep -c TRUSTED_PROXIES
```

Expected: `1`

```
docker compose -f compose.prod.yaml exec -T api env | grep -c '^APP_ENV=production$'
```

Expected: `1`

`COMPOSE_FILE` is set in the shell the commands run from:

```
grep -c '^COMPOSE_FILE=compose.prod.yaml$' .env
```

Expected: `1`

The cookie flags are also checked in the browser in "Update smoke test", step 4.

## Gemini key and budget

Use the paid key (the key lives only in `.env` as `GEMINI_API_KEY`, and only the worker gets it).

1. Budget. In the Google Cloud console, open Billing, then Budgets & alerts, and create a budget for the project of the key with alerts at 50% and 90% sent by email. **A budget only alerts. It does not stop spending.** The hard limits are the app's daily caps (`api/config/limits.toml`: 10 runs and 50 calls per user, 150 runs and 600 calls for the whole site per day) plus a quota you set in Google Cloud for the Gemini API on that project (lower the daily request quota there). Set both.

2. Rotate the key (also do this at once if the key may have leaked). Create the new key first, so there is no gap:
   1. Create a new key for the same project.
   2. Put it in `.env`.
   3. Recreate the worker.
   4. Run the smoke test's Seoul question to see it works.
   5. Delete the old key in Google.

```
nano .env
```

```
docker compose -f compose.prod.yaml up -d worker
```

Expected: `Container indesk-worker-1  Recreated` then `Started`.

The new key reached the worker (count only, no value):

```
docker compose -f compose.prod.yaml exec -T worker env | grep -c GEMINI_API_KEY
```

Expected: `1`

The key never appears in the logs. Every Google key starts with `AIza`:

```
docker compose -f compose.prod.yaml logs worker | grep -c "AIza"
```

Expected: `0`. (`grep -c` also exits with code 1 when the count is 0. That is normal here.) Any number above 0 means the key leaked into a log: rotate it again and tell me.

## Unattended checks

These keep the demo alive while nobody watches.

**Certificate renewal.** Check the timer exists and is waiting. On a certbot installed with apt the timer is `certbot.timer`:

```
systemctl list-timers | grep certbot
```

Expected: one line with a NEXT time in the future. If nothing prints, the certbot may be a snap: try `systemctl list-timers | grep snap.certbot` and ask if both are empty.

A dry run proves renewal would work. It uses the Let's Encrypt test server and changes no certificate. Never use `--force-renewal`:

```
certbot renew --dry-run
```

Expected: `Congratulations, all simulated renewals succeeded`

**Disk:**

```
df -h /
```

Expected: not close to full. Docker's own use:

```
docker system df
```

Expected: a table (this only reads; it is not `prune`).

**Clock:**

```
timedatectl
```

Expected: `System clock synchronized: yes`

**External uptime monitor.** Use a free external service (for example UptimeRobot or Better Stack). Monitor `https://<host>/api/ready`, every 5 minutes, with an email alert to you. `/api/ready` answers `{"status":"ready"}` when the database and Redis answer and `503` when they do not. (`/api/health` only says the api process is up; do not use it for this.) Without an external monitor, a dead server is noticed only when someone tries the demo.

**Background jobs.** The scheduler (`scheduler` service) puts three jobs on the queue and the worker runs them:

| Job | How often | What it does |
|---|---|---|
| `upload-sweep` | every 3600 s | Deletes the stored files of expired uploads. |
| `run-reaper` | every 60 s | Fails runs whose worker died or that are older than the 300 s hard limit. |
| `purge-expired` | every 86400 s | Deletes expired reports, old runs and old `ai_calls`. |

What each job writes to the log (read from the code, `api/app/jobs/` and `api/app/runs/reaper.py`):
- `upload-sweep` logs one line on every pass: `upload sweep: deleted=... in_use=... failed=...`.
- `run-reaper` **does not log on an empty pass.** `reap_stuck_runs` writes `run reaper: failed=<n>` only when it failed at least one run, and one `run <id> reaped reason=...` line per run. Silence means nothing was stuck, not that the job is dead.
- `purge-expired` logs at least one line per daily pass: `purge pass: expired_runs=... old_no_report_runs=... ai_calls=... pdf_failed=...`.

Not verified on the server: the worker and the scheduler set up no logging of their own, so Python's `INFO` lines above may not reach `docker logs` at all. If the greps below find nothing for `upload-sweep`, that does not prove the job did not run: look for RQ's own lines instead (they name the function, for example `run_sweep`), and tell me.

Last sweep lines (the scheduler enqueues; the worker logs):

```
docker compose -f compose.prod.yaml logs --since 2h worker | grep -i "sweep"
```

Last reaper lines (expect nothing on a quiet system):

```
docker compose -f compose.prod.yaml logs --since 24h worker | grep -i "reap"
```

Last purge lines (the daily pass):

```
docker compose -f compose.prod.yaml logs --since 26h worker | grep -i "purge"
```

The scheduler itself is alive:

```
docker compose -f compose.prod.yaml ps scheduler
```

Expected: `healthy`

## Update smoke test

Run after "Update to P14a" step E. Eight steps. Use a **test account**. Step 6 and step 7 each use one real Gemini run, and a new account has 3 free runs, so a test account keeps your own runs. Use only the Seoul demo data and a small test PDF, never a private file.

1. Health and ready.

```
curl -s https://indesk.76-13-198-17.sslip.io/api/health
```

Expected: `{"status":"ok"}`

```
curl -s https://indesk.76-13-198-17.sslip.io/api/ready
```

Expected: `{"status":"ready"}`

2. All services are up.

```
docker compose -f compose.prod.yaml ps
```

Expected: `api`, `worker`, `scheduler`, `sandbox`, `parser`, `web`, `db`, `redis` are `running` or `healthy` (the `parser` must say `healthy`), and `migrate` is `exited (0)`.

3. Migration level.

```
docker compose -f compose.prod.yaml exec -T db psql -U indesk -d indesk -c "select version_num from alembic_version"
```

Expected: `0006`

4. Log in in the browser at https://indesk.76-13-198-17.sslip.io with the test account (sign it up first if it does not exist). In the browser tools check that `indesk_access` and `indesk_refresh` are both `Secure` and `HttpOnly`.

5. Open `/reports/example` (the cached example report). Expected: the report shows, with no model call.

6. Seoul sample, one question (the one real Gemini call of the CSV path). Use the Seoul sample in Ask and ask one question. Expected: the agents appear one by one while the run goes, then a report opens. This uses one of the 3 free runs.

7. One small PDF with one question (the new parser path). Upload one small test PDF, ask one question about it. Expected: the upload is accepted, the run ends with a cited report or a clear "not found in the document" answer, not an error. This uses a second free run.

8. Look for errors and for the key prefix in the logs.

```
docker compose -f compose.prod.yaml logs --since 30m worker | grep -ci "error"
```

Expected: `0`, or a few lines you can explain. Read them:

```
docker compose -f compose.prod.yaml logs --since 30m worker api parser | grep -i "error"
```

The key prefix never appears:

```
docker compose -f compose.prod.yaml logs worker | grep -c "AIza"
```

Expected: `0`

## Rollback by tag

Use this when the update went wrong. Migrations do not roll back by themselves, so a database restore is part of it whenever any migration ran.

1. Stop the services that write to the database.

```
docker compose -f compose.prod.yaml stop api worker scheduler
```

Expected: the three containers stop.

2. **If any migration ran** (the database is at 0005 or 0006), restore the dump made in "Update to P14a" step D1. Follow "To restore for real after a disaster" in step 13: drop the damaged database, create an empty one owned by the migrator role, load the dump without `--no-owner`. The dump is from before the update, so it has no vector extension and no `session_started_at` column. That is fine for the old code, which does not use either. Skip this step only if `alembic_version` is still `0004`.

3. Go back to the tagged code.

```
git checkout v0.1.0-live
```

Expected: a "detached HEAD" message. That is normal here.

4. Rebuild.

```
docker compose -f compose.prod.yaml build
```

Remember: `build` alone restarts nothing.

5. Start the old version. `--remove-orphans` removes the `parser` container, which the old file does not know. It only touches containers of the Indesk project, not Ticketzy.

```
docker compose -f compose.prod.yaml up -d --remove-orphans
```

Expected: containers recreated, `parser` removed.

6. Check it answers.

```
curl -s https://indesk.76-13-198-17.sslip.io/api/health
```

Expected: `{"status":"ok"}`

7. Later, when the problem is fixed and you want to update again, go back to the branch. Without this the next `git pull` fails:

```
git checkout main
```

Expected: `Switched to branch 'main'`

## Logs

```
docker compose -f compose.prod.yaml logs --tail 100 api
```

```
docker compose -f compose.prod.yaml logs --tail 100 worker
```

```
docker compose -f compose.prod.yaml logs --tail 100 web
```

Follow one service live (Ctrl+C to stop):

```
docker compose -f compose.prod.yaml logs -f worker
```

## Stop everything (Indesk only)

```
docker compose -f compose.prod.yaml down
```

This keeps the database and uploads volumes. Do not add `-v`: that deletes them.

## Change a database password later

The passwords in `.env` only set the roles when the database volume is first created. To change one afterwards, change the role and `.env` together.

```
docker compose -f compose.prod.yaml exec db psql -U indesk -d indesk -c "ALTER ROLE indesk_app PASSWORD 'new-password'"
```

Then put the same value in `.env` and recreate the services.

```
docker compose -f compose.prod.yaml up -d
```

## Switch to indesk.uz (gated)

**Do this only after "Update smoke test" passed on the current host, all 8 steps.** Do not do it in the same sitting as the update: if both change at once you cannot tell which one broke something.

Two rules, because the server's nginx file for Indesk has been changed by certbot (it added the 443 part and the redirect):
- Do NOT copy `deploy/nginx/indesk.conf` over `/etc/nginx/conf.d/indesk.conf`. That erases the certbot lines and HTTPS stops working.
- Do NOT edit `deploy/nginx/indesk.conf` inside the repo folder on the server. It makes `git pull` fail on the next update.

The simple, safe path: edit `server_name` in the installed file `/etc/nginx/conf.d/indesk.conf` directly, in both server blocks, and let certbot extend the existing certificate with `--expand`. The repo file stays untouched.

1. In the domain's DNS, add an A record `indesk.uz` pointing to `76.13.198.17`. Wait until it resolves.

```
dig +short indesk.uz
```

Expected: `76.13.198.17`

2. Back up nginx and take the checksum of the other site's file (as in step 7).

```
cp -a /etc/nginx /root/nginx-backup-$(date +%Y%m%d-%H%M)
```

```
md5sum /etc/nginx/conf.d/ticketzy.conf
```

3. Open the installed file.

```
nano /etc/nginx/conf.d/indesk.conf
```

There are two `server` blocks (port 443 and the port 80 redirect). In BOTH, change the line so it lists both names, keeping everything else as it is:

`server_name indesk.76-13-198-17.sslip.io indesk.uz;`

4. Test and reload.

```
nginx -t
```

Expected: `syntax is ok` and `test is successful`.

```
systemctl reload nginx
```

5. Get one certificate that covers both names. Name both hosts, and keep `--expand`:

```
certbot --nginx -d indesk.76-13-198-17.sslip.io -d indesk.uz --expand
```

Expected: `Successfully deployed certificate`.

6. Allow both origins in `.env` while people still use the old address: `ALLOWED_ORIGINS=https://indesk.76-13-198-17.sslip.io,https://indesk.uz`

```
nano .env
```

7. Recreate the services so they read the new value. No rebuild is needed: the web image has no host name in it, and the browser always calls its own origin.

```
docker compose -f compose.prod.yaml up -d
```

8. Check `https://indesk.uz`: sign up, upload and run one question. Later, remove the old host from `ALLOWED_ORIGINS` and run the same `up -d` again.
9. Check the Ticketzy checksum again. It must be identical to step 2.

```
md5sum /etc/nginx/conf.d/ticketzy.conf
```

10. Check every other site's URL on this server still answers (as in step 9 above):

```
curl -sI https://ticketzy.uz
```

### Cookies and sessions

The login cookies are host-only: they belong to the exact host that set them. A person who logged in on `indesk.76-13-198-17.sslip.io` stays logged in there and is **not** logged in on `indesk.uz`, and the other way round. Nobody is logged out by the switch. Each host has its own session, which still ends 6 hours after its login.

### Rollback of the domain switch

If `indesk.uz` misbehaves, the old host is untouched and keeps working, so you can stop and go back without a rush.

1. Put `.env` back to the old origin only: `ALLOWED_ORIGINS=https://indesk.76-13-198-17.sslip.io`

```
nano .env
```

```
docker compose -f compose.prod.yaml up -d
```

Expected: the api and worker are recreated.

2. Certificate fallback. Because the certificate was extended with `--expand`, it still covers the old name. The old host keeps working over HTTPS even if `indesk.uz` has a certificate problem. You do not need to touch certbot to go back. Never use `--force-renewal`.

3. If nginx itself is broken, restore the backup from step 2 (use its real folder name), then test and reload:

```
cp -a /root/nginx-backup-<date>/. /etc/nginx/
```

```
nginx -t
```

```
systemctl reload nginx
```
