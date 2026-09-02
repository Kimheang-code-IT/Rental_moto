# HollyWing Motor — Production checklist

Use this before going live. Development defaults are **not** safe for production.

## 1. Clear development data

From the repository root, with the stack running:

```powershell
# Wipe business data; keep only admin, roles, document sequences
docker compose exec api python scripts/reset_db.py

# Optional: wipe Docker volumes completely (database + MinIO + Redis + RabbitMQ)
# docker compose down -v
# docker compose up -d --build
```

After reset, only the SuperAdmin from `SEED_ADMIN_*` remains.

## 2. Secrets and environment

1. Copy `.env.production.example` to `.env` on the production host.
2. Replace every `CHANGE_ME_*` value.
3. Set a strong `SEED_ADMIN_PASSWORD` **before** the first API start (or reset again after changing it).
4. Set `CORS_ORIGINS` to your real HTTPS origin(s), for example `https://app.your-domain.com`.
5. Set `CORS_ALLOW_PRIVATE_NETWORKS=false`.
6. Set `ENVIRONMENT=production`.
7. Set `NUXT_PUBLIC_SITE_URL` to the public HTTPS site URL.
8. Rotate Telegram bot token in BotFather if it was ever shared in chat, screenshots, or git history.

Generate secrets:

```powershell
# JWT / Telegram client secret examples
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }) -as [byte[]])
```

Or:

```bash
openssl rand -base64 48
```

## 3. Start production stack

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

This keeps DB / Redis / RabbitMQ / MinIO off the public host ports and runs with `ENVIRONMENT=production`.

## 4. Post-deploy checks

- [ ] Open the site over HTTPS and sign in as SuperAdmin
- [ ] Change the admin password immediately after first login if seed password was temporary
- [ ] Create real staff users and roles (do not keep demo passwords)
- [ ] Configure System Settings → Localization, Telegram destinations, company info
- [ ] Create motorcycles and customers
- [ ] Create one test rental and confirm Telegram invoice + MinIO archive
- [ ] Confirm `/docs` is not exposed publicly if you terminate TLS at a reverse proxy that should block it
- [ ] Back up PostgreSQL and MinIO regularly

## 5. What stays after a clean reset

| Kept | Removed |
|------|---------|
| SuperAdmin role + admin user | Rentals, payments, charges, expenses |
| Rental Staff / Report Viewer roles (empty) | Customers, motorcycles |
| Document sequences | Audit logs, export jobs, outbox |
| App info / MinIO provider settings | Uploaded invoice PDFs in MinIO (clear separately if needed) |

## 6. Local cleanup helpers

```powershell
.\scripts\prepare-production.ps1
```

That script resets the database, clears MinIO objects, and removes local caches.
