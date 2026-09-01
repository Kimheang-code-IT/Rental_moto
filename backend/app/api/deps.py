import jwt as pyjwt
from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionFactory, get_session
from app.core.errors import AccessDeniedError, AuthRequiredError
from app.core.permissions import has_permission
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
    if user.permissions:
        return list(user.permissions)
    if user.page_access:
        return list(user.page_access)
    return []


def require_permission(required: str):
    async def checker(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user.role, user_permissions(user), required):
            raise AccessDeniedError(f"Missing permission: {required}")
        return user

    return checker


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
        start_date: str | None = Query(default=None),
        end_date: str | None = Query(default=None),
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
