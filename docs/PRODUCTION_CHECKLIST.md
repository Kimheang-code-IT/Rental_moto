# HollyWing Motor — Production checklist

Use this before going live. Development defaults are **not** safe for production.

## 1. Publish images (CI)

GitHub Actions builds and pushes these images to GHCR on every push to `main`, on `v*` tags, and via workflow dispatch:

| Image | GHCR name |
| --- | --- |
| API + Celery workers + scheduler | `ghcr.io/kimheang-code-it/rental_moto/api` |
| Nginx frontend | `ghcr.io/kimheang-code-it/rental_moto/frontend` |
| Telegram bot | `ghcr.io/kimheang-code-it/rental_moto/telegram-bot` |

Tags published: `latest` (main), `sha-<short>`, and semver when you push a `v*` git tag.

**GitHub setup (once):**

1. Repo **Settings → Actions → General → Workflow permissions** → **Read and write**.
2. After the first successful workflow, open **Packages** and confirm the three images exist.
3. For a private repository, create a GitHub PAT with `read:packages` (and `write:packages` if you also push from a laptop). On the production host: `docker login ghcr.io`.
4. Optional: make each package public if another machine should pull without login.

## 2. Secrets and environment

1. Copy `.env.production.example` to `.env` on the production host.
2. Replace every `CHANGE_ME_*` value. The API **refuses to start** in production if JWT or Telegram client secret are still placeholders.
3. Do not set any `SEED_ADMIN_*` variables; they no longer exist. The first administrator registers through the public `/auth/setup` page (email + password) immediately after the first deploy, while the users table is empty.
4. Set `CORS_ORIGINS` to your real HTTPS origin(s), for example `https://app.your-domain.com`.
5. Set `CORS_ALLOW_PRIVATE_NETWORKS=false` and `DEBUG=false`.
6. Set `ENVIRONMENT=production`.
7. Set `IMAGE_TAG` to `latest` or a specific version/SHA tag from GHCR.
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

## 3. Start production stack (pull, do not build)

The production host only needs this git repo (for compose files) plus Docker. Application images come from GHCR.

```powershell
docker login ghcr.io
.\scripts\deploy-from-registry.ps1
```

Or:

```bash
docker login ghcr.io
chmod +x scripts/deploy-from-registry.sh
./scripts/deploy-from-registry.sh
```

Manual equivalent:

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

This keeps DB / Redis / API off the public host ports, sets `ENVIRONMENT=production`, and **does not rebuild images**. `/docs` and `/openapi.json` are disabled in production.

To pin a version: set `IMAGE_TAG=sha-abc1234` (or `v1.0.0`) in `.env`.

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

That script resets the database, clears local archived files, and removes local caches. It does **not** publish images; use GitHub Actions for that.
