# HollyWing Motor — Production checklist

Use this before going live. Development defaults are **not** safe for production.

## 1. Build images locally

Images are built from source on the host with `docker compose ... up -d --build`.
No GitHub login, GHCR account, or CI is required. The three images are:

| Image | Local name |
| --- | --- |
| API + Celery workers + scheduler | `hollywing-motor/api:${IMAGE_TAG:-local}` |
| Nginx frontend | `hollywing-motor/frontend:${IMAGE_TAG:-local}` |
| Telegram bot | `hollywing-motor/telegram-bot:${IMAGE_TAG:-local}` |

The host only needs Docker plus this git repo. The first build downloads base
images (`python:3.12-slim`, `node:22-alpine`, `nginx:1.27-alpine`, `postgres:16-alpine`,
`redis:7-alpine`) and Python/Node dependencies, so it takes a few minutes.

This stack is tuned for a small host (under 5 users). Container CPU/memory
limits live in `docker-compose.prod.yml` and can be overridden in `.env`
(`DB_MEMORY`, `API_MEMORY`, `WORKER_MEMORY`, and so on).

The `worker-telegram` service only delivers outbound Telegram notifications. Set
`TELEGRAM_WORKER_REPLICAS=0` in `.env` to stop it and save ~100–200 MB. The API,
reports, exports, and the two-way `telegram-bot` keep working; outbound
notifications are queued in Redis instead of delivered, and password-reset codes
expire after ~5 minutes.

## 2. Secrets and environment

1. Copy `.env.production.example` to `.env` on the production host.
2. Replace every `CHANGE_ME_*` value. The API **refuses to start** in production if JWT or Telegram client secret are still placeholders.
3. Do not set any `SEED_ADMIN_*` variables; they no longer exist. The first administrator registers through the public `/auth/setup` page (email + password) immediately after the first deploy, while the users table is empty.
4. Set `CORS_ORIGINS` to your real HTTPS origin(s), for example `https://app.your-domain.com`.
5. Set `CORS_ALLOW_PRIVATE_NETWORKS=false` and `DEBUG=false`.
6. Set `ENVIRONMENT=production`.
7. Optionally set `IMAGE_TAG` to a label such as the current git short SHA (`IMAGE_TAG=sha-abc1234`) so local builds are easy to tell apart; otherwise leave it as `local`.
8. Rotate the Telegram bot token in BotFather if it was ever shared in chat, screenshots, or git history.

Generate secrets:

```powershell
# JWT / Telegram client secret examples
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }) -as [byte[]])
```

Or:

```bash
openssl rand -base64 48
```

## 3. Start production stack (build locally)

The production host only needs this git repo plus Docker. Every image is built
from source on the host; nothing is pulled from a registry.

```powershell
.\scripts\deploy-local.ps1
```

Or:

```bash
chmod +x scripts/deploy-local.sh
./scripts/deploy-local.sh
```

Manual equivalent:

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --remove-orphans
```

This keeps DB / Redis / API off the public host ports, sets `ENVIRONMENT=production`,
builds the images locally, applies the small-host CPU/memory limits, and disables
`/docs` and `/openapi.json` in production.

After changing code, pull and rebuild:

```powershell
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --remove-orphans
```

## 4. Optional: wipe development data

Only if this host previously ran the development stack:

```powershell
# Wipe business data; keep users, roles, document sequences, and settings
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api python scripts/reset_db.py

# Optional: wipe Docker volumes completely (database + local files + Redis + RabbitMQ)
# docker compose -f docker-compose.yml -f docker-compose.prod.yml down -v
# docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

After reset, users, roles, document sequences, and settings remain; you stay signed in. A full `down -v` volume wipe is the only path that returns the app to `/auth/setup`.

## 5. Post-deploy checks

- [ ] Open the site over HTTPS, register the first system owner through `/auth/setup`, and use a strong password
- [ ] Confirm `GET /api/v2/auth/setup-status` returns `needsSetup: false` and `POST /api/v2/auth/setup` returns 409 afterwards
- [ ] Create real staff users and roles
- [ ] Configure System Settings → Localization, Telegram (Bot token, Group ID, Chat User IDs), company info
- [ ] Create motorcycles and customers
- [ ] Create one test rental and confirm Telegram **text** notification (no PDF attachment)
- [ ] Confirm `/docs` returns 404 (Swagger is off in production)
- [ ] Confirm host ports 5432 / 6379 / 5672 / 8000 are not published
- [ ] Back up PostgreSQL and the `appdata` volume (exports) regularly

## 6. What stays after a clean reset

| Kept | Removed |
|------|---------|
| All users and roles | Rentals, payments, charges, expenses |
| Document sequences (including last values) | Customers, motorcycles |
| App settings / storage providers | Audit logs, export jobs, outbox |
| Refresh-token sessions | Export files on disk (clear `/srv/data/exports` separately if needed) |

## 7. Local cleanup helpers

```powershell
.\scripts\prepare-production.ps1
```

That script resets the database, clears local archived files, and removes local caches. It does **not** build or publish images; rebuild locally with `scripts/deploy-local.ps1`.
