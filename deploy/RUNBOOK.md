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

## Update

Take a backup first. The migration runs again on every start.

```
cd /root/Indesk
```

```
deploy/backup.sh
```

```
git pull
```

```
docker compose -f compose.prod.yaml build
```

**Warning: `build` alone restarts nothing.** The old containers keep running the old code until you run the next command. Do not skip it.

```
docker compose -f compose.prod.yaml up -d
```

```
curl -s https://indesk.76-13-198-17.sslip.io/api/health
```

## Rollback

Go back to the previous commit and rebuild. Migrations do not roll back by themselves: if the new version changed the database schema, restore the backup from before the update instead (see step 13).

```
git log --oneline -5
```

```
git checkout <previous commit>
```

```
docker compose -f compose.prod.yaml build
```

Remember: `build` alone restarts nothing.

```
docker compose -f compose.prod.yaml up -d
```

When the rollback is over (or after you fix the problem and want to update again), go back to the branch. Without this the server stays on a detached commit and the next `git pull` fails:

```
git checkout main
```

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

## Switch to indesk.uz

Two rules, because the server's nginx file for Indesk has been changed by certbot (it added the 443 part and the redirect):
- Do NOT copy `deploy/nginx/indesk.conf` over `/etc/nginx/conf.d/indesk.conf`. That erases the certbot lines and HTTPS stops working.
- Do NOT edit `deploy/nginx/indesk.conf` inside the repo folder on the server. It makes `git pull` fail on the next update.

The simple, safe path: edit `server_name` in the installed file `/etc/nginx/conf.d/indesk.conf` directly, in both server blocks, and let certbot extend the existing certificate with `--expand`. The repo file stays untouched.

1. In the domain's DNS, add an A record `indesk.uz` pointing to `76.13.198.17`. Wait until it resolves.

```
dig +short indesk.uz
```

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

```
systemctl reload nginx
```

5. Get one certificate that covers both names. Name both hosts, and keep `--expand`:

```
certbot --nginx -d indesk.76-13-198-17.sslip.io -d indesk.uz --expand
```

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

If something goes wrong, restore the backup from step 2 (use its real folder name), then test and reload:

```
cp -a /root/nginx-backup-<date>/. /etc/nginx/
```

```
nginx -t
```

```
systemctl reload nginx
```
