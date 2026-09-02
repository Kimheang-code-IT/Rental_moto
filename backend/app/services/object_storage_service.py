from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from urllib.parse import urlparse

from app.core.config import settings


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    object_name: str
    etag: str
    size: int


class ObjectStorageService:
    """Small async adapter around the synchronous MinIO Python client."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
        client=None,
    ) -> None:
        self.bucket = bucket
        if client is not None:
            self.client = client
            return

        from minio import Minio

        host, endpoint_secure = _normalize_endpoint(endpoint, secure)
        self.client = Minio(
            endpoint=host,
            access_key=access_key,
            secret_key=secret_key,
            secure=endpoint_secure,
        )

    @classmethod
    def from_settings(cls) -> "ObjectStorageService":
        return cls(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            secure=settings.minio_secure,
        )

    @classmethod
    def from_provider(cls, provider) -> "ObjectStorageService":
        endpoint = str(provider.endpoint or settings.minio_endpoint)
        return cls(
            endpoint=endpoint,
            access_key=str(provider.access_key or ""),
            secret_key=str(provider.secret_key or ""),
            bucket=str(provider.bucket or ""),
            secure=endpoint.lower().startswith("https://"),
        )

    async def bucket_exists(self) -> bool:
        return bool(await asyncio.to_thread(self.client.bucket_exists, self.bucket))

    async def ensure_bucket(self) -> None:
        if not await self.bucket_exists():
            await asyncio.to_thread(self.client.make_bucket, self.bucket)

    async def put_bytes(self, object_name: str, content: bytes, content_type: str) -> StoredObject:
        await self.ensure_bucket()
        result = await asyncio.to_thread(
            self.client.put_object,
            self.bucket,
            object_name,
            BytesIO(content),
            len(content),
            content_type=content_type,
        )
        return StoredObject(
            bucket=self.bucket,
            object_name=object_name,
            etag=str(getattr(result, "etag", "") or ""),
            size=len(content),
        )

    async def archive_invoice(
        self,
        rental_no: str,
        filename: str,
        content: bytes,
        *,
        at: datetime | None = None,
    ) -> StoredObject:
        object_name = invoice_object_name(rental_no, filename, at=at)
        return await self.put_bytes(object_name, content, "application/pdf")


def invoice_object_name(rental_no: str, filename: str, *, at: datetime | None = None) -> str:
    timestamp = at or datetime.now(timezone.utc)
    safe_rental = _safe_segment(rental_no)
    safe_filename = _safe_segment(filename)
    return f"invoices/{timestamp:%Y/%m}/{safe_rental}/{safe_filename}"


def _safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip("-.")
    return cleaned or "unknown"


def _normalize_endpoint(endpoint: str, secure: bool) -> tuple[str, bool]:
    raw = endpoint.strip()
    parsed = urlparse(raw if "://" in raw else f"{'https' if secure else 'http'}://{raw}")
    if not parsed.netloc or parsed.path not in ("", "/"):
        raise ValueError("MinIO endpoint must be a host and optional port without a path")
    return parsed.netloc, parsed.scheme.lower() == "https"
