from __future__ import annotations
import socket
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFoundError
from app.core.redis import cache
from app.models import StorageProvider
from app.repositories.admin import StorageProviderRepository
from app.schemas.settings import ConnectionResult
from app.services.admin_service import SettingService, SETTINGS_CACHE_PREFIX

STORAGE_CACHE_KEY = f"{SETTINGS_CACHE_PREFIX}storage"

MASKED = "***"


def _to_dict(provider: StorageProvider) -> dict:
    return {
        "id": provider.id,
        "name": provider.name,
        "type": provider.type,
        "active": provider.active,
        "isDefault": provider.is_default,
        "maxFileSizeMb": provider.max_file_size_mb,
        "allowedFileTypes": provider.allowed_file_types or [],
        "accessMode": provider.access_mode,
        "uploadPathPattern": provider.upload_path_pattern,
        "connectionStatus": provider.connection_status,
        "lastTestedAt": provider.last_tested_at.isoformat() if provider.last_tested_at else None,
        "lastTestMessage": provider.last_test_message,
        "endpoint": provider.endpoint,
        "region": provider.region,
        "bucket": provider.bucket,
        "accessKey": provider.access_key,
        "secretKey": MASKED if provider.secret_key else "",
        "publicUrl": provider.public_url,
        "pathStyle": provider.path_style,
        "folderId": provider.folder_id,
        "clientId": provider.client_id,
        "clientSecret": MASKED if provider.client_secret else "",
        "credentialStatus": provider.credential_status,
        "syncStatus": provider.sync_status,
        "syncSchedule": provider.sync_schedule,
        "updatedAt": provider.updated_at.isoformat(),
    }


class StorageProviderService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = StorageProviderRepository(session)
        self.session = session

    async def list(self) -> list[dict]:
        cached = await cache.get_json(STORAGE_CACHE_KEY)
        if cached is not None:
            return cached
        providers = [_to_dict(p) for p in await self.repo.list()]
        await cache.set_json(STORAGE_CACHE_KEY, providers, settings.settings_cache_ttl_seconds)
        return providers

    async def _invalidate(self) -> None:
        await cache.delete_keys(STORAGE_CACHE_KEY)

    async def get(self, provider_id: str) -> dict:
        provider = await self.repo.get(provider_id)
        if provider is None:
            raise NotFoundError("Storage provider not found")
        return _to_dict(provider)

    async def create(self, data, user_id: int | None) -> dict:
        provider_id = data.id or f"sp-{uuid.uuid4().hex[:8]}"
        existing = await self.repo.get(provider_id)
        if existing is not None:
            raise NotFoundError("Provider id already exists")
        payload = data.model_dump(by_alias=False)
        payload.pop("id", None)
        if payload.get("secret_key") == MASKED:
            payload["secret_key"] = None
        if payload.get("client_secret") == MASKED:
            payload["client_secret"] = None
        provider = StorageProvider(id=provider_id, **payload, updated_by_user_id=user_id)
        if provider.is_default:
            await self.repo.unset_default(provider_id)
        await self.repo.add(provider)
        await self.session.commit()
        await self._invalidate()
        return _to_dict(provider)

    async def update(self, provider_id: str, data, user_id: int | None) -> dict:
        provider = await self.repo.get(provider_id)
        if provider is None:
            raise NotFoundError("Storage provider not found")
        updates = data.model_dump(exclude_unset=True, by_alias=False)
        for key in ("secret_key", "client_secret"):
            if updates.get(key) == MASKED:
                updates.pop(key)
        for field, value in updates.items():
            setattr(provider, field, value)
        if updates.get("is_default"):
            await self.repo.unset_default(provider_id)
        provider.updated_by_user_id = user_id
        await self.session.commit()
        await self._invalidate()
        return _to_dict(provider)

    async def delete(self, provider_id: str) -> None:
        provider = await self.repo.get(provider_id)
        if provider is None:
            raise NotFoundError("Storage provider not found")
        await self.repo.delete(provider)
        await self.session.commit()
        await self._invalidate()

    async def set_flag(self, provider_id: str, is_default: bool = False, active: bool = False) -> dict:
        provider = await self.repo.get(provider_id)
        if provider is None:
            raise NotFoundError("Storage provider not found")
        if is_default:
            provider.is_default = True
            await self.repo.unset_default(provider_id)
        if active:
            provider.active = True
        await self.session.commit()
        await self._invalidate()
        return _to_dict(provider)

    async def test_connection(self, provider_id: str) -> dict:
        provider = await self.repo.get(provider_id)
        if provider is None:
            raise NotFoundError("Storage provider not found")
        if provider.type == "local":
            status, message = "connected", "Local storage ready"
        elif provider.type == "minio":
            try:
                from app.services.object_storage_service import ObjectStorageService

                storage = ObjectStorageService.from_provider(provider)
                if not provider.bucket:
                    raise ValueError("Bucket is required")
                if not await storage.bucket_exists():
                    raise ValueError(f"Bucket '{provider.bucket}' does not exist")
                status, message = "connected", f"Connected to MinIO bucket '{provider.bucket}'"
            except Exception as exc:
                status, message = "failed", f"MinIO connection failed: {exc}"
        else:
            status, message = "connected", "Configuration saved"
            if provider.type in ("amazon_s3", "minio", "cloudflare_r2") and not provider.bucket:
                status, message = "failed", "Bucket is required"
        provider.connection_status = status
        provider.last_tested_at = datetime.now(timezone.utc)
        provider.last_test_message = message
        await self.session.commit()
        await self._invalidate()
        return ConnectionResult(status=status, message=message).model_dump()


async def test_telegram_connection(session: AsyncSession, destination_id: str | None = None, send_message: bool = False) -> dict:
    settings_service = SettingService(session)
    config = await settings_service.telegram_config()
    token = config.get("botToken") or settings.telegram_bot_token
    if not token or token == MASKED:
        token = settings.telegram_bot_token
    if not token:
        return ConnectionResult(status="failed", message="Telegram bot token is not configured").model_dump()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            if response.status_code != 200:
                return ConnectionResult(status="failed", message=f"Telegram API error {response.status_code}").model_dump()
            data = response.json().get("result", {})
            username = data.get("username", "")
            bot_label = f"@{username}" if username else "Telegram bot"
            if not send_message:
                return ConnectionResult(status="connected", message=f"Connected to {bot_label}").model_dump()
            chat_id = str(destination_id or config.get("chatId") or "").strip()
            if not chat_id:
                return ConnectionResult(
                    status="failed",
                    message=f"Connected to {bot_label}, but Group ID is not configured",
                ).model_dump()
            sent = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": "HollyWing Motor connection test"},
            )
            if sent.status_code != 200:
                detail = sent.text[:200] if sent.text else f"HTTP {sent.status_code}"
                return ConnectionResult(
                    status="failed",
                    message=f"Bot is valid, but the test message was not delivered: {detail}",
                ).model_dump()
            return ConnectionResult(
                status="connected",
                message=f"Test message sent to {chat_id} via {bot_label}",
            ).model_dump()
    except Exception as exc:
        return ConnectionResult(status="failed", message=str(exc)).model_dump()


async def test_email_connection(session: AsyncSession, send_to: str | None = None) -> dict:
    settings_service = SettingService(session)
    config = await settings_service.get_app_config(mask=False)
    email_config = config.get("email", {})
    host = email_config.get("smtpHost") or ""
    port = int(email_config.get("smtpPort") or 587)
    if not host:
        return ConnectionResult(status="failed", message="SMTP host is not configured").model_dump()
    try:
        with socket.create_connection((host, port), timeout=5):
            pass
        return ConnectionResult(status="connected", message=f"Reached {host}:{port}").model_dump()
    except Exception as exc:
        return ConnectionResult(status="failed", message=f"SMTP connection failed: {exc}").model_dump()

