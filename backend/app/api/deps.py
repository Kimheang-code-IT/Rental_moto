import jwt as pyjwt
from dataclasses import dataclass

from fastapi import Depends, Header, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionFactory, get_session
from app.core.errors import AccessDeniedError, AuthRequiredError
from app.core.permissions import effective_permissions, is_super_admin_user, user_has_permission
from app.core.redis import get_redis
from app.core.security import decode_token
from app.models import User
from app.repositories.admin import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> AsyncSession:
    return get_session()


async def get_db_session() -> AsyncSession:
    async with SessionFactory() as session:
        yield session


async def get_redis_dep() -> aioredis.Redis | None:
    try:
        return get_redis()
    except Exception:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    if credentials is None or not credentials.credentials:
        raise AuthRequiredError("Missing bearer token")
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except pyjwt.PyJWTError:
        raise AuthRequiredError("Invalid or expired access token")
    user = await UserRepository(session).get(int(payload["sub"]))
    if user is None:
        raise AuthRequiredError("User not found")
    if user.status != "Active":
        raise AuthRequiredError("Account is inactive")
    return user


def user_permissions(user: User) -> list[str]:
    return effective_permissions(user)


def require_permission(required: str):
    async def checker(user: User = Depends(get_current_user)) -> User:
        if not user_has_permission(user, required):
            raise AccessDeniedError(f"Missing permission: {required}")
        return user

    return checker


def require_any_permission(*required: str):
    async def checker(user: User = Depends(get_current_user)) -> User:
        if not any(user_has_permission(user, permission) for permission in required):
            raise AccessDeniedError(f"Missing one of permissions: {', '.join(required)}")
        return user

    return checker


def can_access_owned_resource(user: User, owner_user_id: int | None) -> bool:
    return is_super_admin_user(user) or owner_user_id == user.id


async def get_service_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None or not credentials.credentials:
        raise AuthRequiredError("Missing bearer token")
    try:
        payload = decode_token(credentials.credentials, expected_type="service")
    except pyjwt.PyJWTError:
        raise AuthRequiredError("Invalid service token")
    if "telegram.reports.read" not in (payload.get("scope") or ""):
        raise AccessDeniedError("Service token lacks required scope")
    return {"client_id": payload["sub"], "scope": payload.get("scope")}


async def get_actor_or_service(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User | dict:
    if credentials is None or not credentials.credentials:
        raise AuthRequiredError("Missing bearer token")
    try:
        payload = decode_token(credentials.credentials)
    except pyjwt.PyJWTError:
        raise AuthRequiredError("Invalid or expired token")
    if payload.get("type") == "service":
        if "telegram.reports.read" not in (payload.get("scope") or ""):
            raise AccessDeniedError("Service token lacks required scope")
        return {"client_id": payload["sub"], "scope": payload.get("scope")}
    if payload.get("type") != "access":
        raise AuthRequiredError("Invalid token type")
    user = await UserRepository(session).get(int(payload["sub"]))
    if user is None or user.status != "Active":
        raise AuthRequiredError("User not found or inactive")
    return user


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


class ListParams:
    def __init__(
        self,
        q: str | None = Query(default=None),
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=settings.default_page_size, ge=1, le=settings.max_page_size),
        sort: str | None = Query(default=None),
        status: str | None = Query(default=None),
        start_date: str | None = Query(default=None, alias="startDate"),
        end_date: str | None = Query(default=None, alias="endDate"),
    ) -> None:
        self.q = q
        self.page = page
        self.limit = limit
        self.sort = sort
        self.status = status
        self.start_date = start_date
        self.end_date = end_date


def parse_date_range(start: str | None, end: str | None) -> tuple[object | None, object | None]:
    from datetime import datetime, timedelta, timezone

    def parse_one(value: str | None, is_end: bool):
        if not value:
            return None
        v = value.strip()
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(v, fmt)
                if is_end and fmt == "%Y-%m-%d":
                    dt = dt + timedelta(days=1) - timedelta(seconds=1)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None

    return parse_one(start, False), parse_one(end, True)


def envelope(data, meta: dict | None = None) -> dict:
    return {"data": data, "meta": meta or {"page": 1, "limit": 1, "total": 1}}


@dataclass
class TelegramHeaders:
    user_id: str
    chat_id: str
    chat_type: str


async def get_telegram_headers(
    x_telegram_user_id: str | None = Header(default=None, alias="X-Telegram-User-Id"),
    x_telegram_chat_id: str | None = Header(default=None, alias="X-Telegram-Chat-Id"),
    x_telegram_chat_type: str | None = Header(default=None, alias="X-Telegram-Chat-Type"),
) -> TelegramHeaders:
    if not x_telegram_user_id or not x_telegram_chat_id or not x_telegram_chat_type:
        raise AuthRequiredError("Missing Telegram context headers")
    return TelegramHeaders(
        user_id=str(x_telegram_user_id),
        chat_id=str(x_telegram_chat_id),
        chat_type=str(x_telegram_chat_type).lower(),
    )


async def get_telegram_context(
    headers: TelegramHeaders = Depends(get_telegram_headers),
    _service=Depends(get_service_principal),
    session: AsyncSession = Depends(get_db_session),
):
    from app.services.admin_service import SettingService
    from app.services.telegram_context import build_telegram_context

    settings_svc = SettingService(session)
    config = await settings_svc.get_app_config(mask=False)
    telegram = config.get("telegram") or {}
    localization = config.get("localization") or {}
    return await build_telegram_context(
        session,
        headers.user_id,
        headers.chat_id,
        headers.chat_type,
        telegram,
        localization,
    )
