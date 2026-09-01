import hashlib
import secrets
from datetime import datetime, timezone

import jwt as pyjwt
from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AccessDeniedError, AuthRequiredError, ConflictError, NotFoundError, RateLimitedError, ValidationError
from app.core.redis import get_redis
from app.core.security import (
    create_access_token,
    create_password_reset_jwt,
    create_refresh_token,
    decode_token,
    generate_reset_code,
    hash_password,
    hash_token,
    utcnow,
    verify_password,
)
from app.models import AuditLog, RefreshTokenSession, User
from app.repositories.admin import AuditRepository, UserRepository

DENYLIST_PREFIX = "auth:deny:jti:"
RL_PREFIX = "auth:rl:"
RESET_PREFIX = "auth:pwreset:"
RESET_DELIVERY_PREFIX = "auth:pwdeliver:"
LINK_PREFIX = "auth:link:"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _reset_key(email: str) -> str:
    return f"{RESET_PREFIX}{email.lower()}"


class RateLimiter:
    def __init__(self, redis: aioredis.Redis | None) -> None:
        self.redis = redis

    async def hit(self, key: str, limit: int, window_seconds: int) -> None:
        if self.redis is None:
            return
        full_key = f"{RL_PREFIX}{key}"
        try:
            count = await self.redis.incr(full_key)
            if count == 1:
                await self.redis.expire(full_key, window_seconds)
            if count > limit:
                raise RateLimitedError("Too many requests. Please try again later.")
        except RateLimitedError:
            raise
        except Exception:
            return


class AuthService:
    def __init__(self, session: AsyncSession, redis: aioredis.Redis | None = None) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.audit = AuditRepository(session)
        self.redis = redis if redis is not None else _safe_redis()
        self.limiter = RateLimiter(self.redis)

    async def login(self, email: str, password: str, ip: str | None, user_agent: str | None) -> tuple[str, str, int, int, User]:
        await self.limiter.hit(f"login:{ip}", settings.rate_limit_login_per_minute, 60)
        await self.limiter.hit(f"login:email:{email.lower()}", settings.rate_limit_login_per_minute, 60)
        user = await self.users.get_by_email(email)
        if user is None or not verify_password(user.password_hash, password):
            raise AccessDeniedError("Invalid email or password")
        if user.status != "Active":
            raise AccessDeniedError("Account is inactive")
        access, access_exp, _ = create_access_token(user.id)
        refresh, refresh_exp, jti, family = create_refresh_token(user.id)
        self.session.add(
            RefreshTokenSession(
                user_id=user.id,
                family_id=family,
                jti=jti,
                token_hash=hash_token(refresh),
                expires_at=refresh_exp,
                user_agent=(user_agent or "")[:300] or None,
                ip_address=ip,
            )
        )
        user.last_login_at = utcnow()
        await self.audit.add(
            AuditLog(
                user_id=user.id,
                user_name=user.display_name,
                action="login",
                entity_type="user",
                entity_id=str(user.id),
                entity_label=user.email,
            )
        )
        await self.session.commit()
        return (
            access,
            refresh,
            settings.access_token_expire_minutes * 60,
            settings.refresh_token_expire_days * 24 * 3600,
            user,
        )

    async def refresh(self, refresh_token: str, ip: str | None) -> tuple[str, str, int, int]:
        await self.limiter.hit(f"refresh:{ip}", settings.rate_limit_refresh_per_minute, 60)
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except pyjwt.PyJWTError:
            raise AuthRequiredError("Invalid refresh token")
        jti = payload["jti"]
        family = payload.get("fam")
        user_id = int(payload["sub"])

        if self.redis is not None:
            try:
                if await self.redis.get(f"{DENYLIST_PREFIX}{jti}"):
                    await self._revoke_family(user_id, family, reason="reuse")
                    raise AuthRequiredError("Refresh token has been revoked")
            except AuthRequiredError:
                raise
            except Exception:
                pass

        result = await self.session.execute(
            RefreshTokenSession.__table__.select().where(RefreshTokenSession.jti == jti)
        )
        row = result.mappings().first()
        if row is None:
            await self._revoke_family(user_id, family, reason="reuse")
            raise AuthRequiredError("Refresh token not recognized")
        if row["revoked_at"] is not None:
            await self._revoke_family(user_id, family, reason="reuse")
            raise AuthRequiredError("Refresh token has been revoked")
        if row["token_hash"] != hash_token(refresh_token):
            await self._revoke_family(user_id, family, reason="reuse")
            raise AuthRequiredError("Refresh token has been revoked")

        expires_at = row["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < utcnow():
            raise AuthRequiredError("Refresh token expired")

        await self.session.execute(
            RefreshTokenSession.__table__.update()
            .where(RefreshTokenSession.jti == jti)
            .values(revoked_at=utcnow())
        )
        user = await self.users.get(user_id)
        if user is None or user.status != "Active":
            raise AuthRequiredError("Account is inactive")

        access, access_exp, _ = create_access_token(user.id)
        new_refresh, new_exp, new_jti, _ = create_refresh_token(user.id, family_id=family)
        self.session.add(
            RefreshTokenSession(
                user_id=user_id,
                family_id=family,
                jti=new_jti,
                token_hash=hash_token(new_refresh),
                expires_at=new_exp,
                ip_address=ip,
            )
        )
        await self._deny_jti(jti, expires_at)
        await self.session.commit()
        return access, new_refresh, settings.access_token_expire_minutes * 60, settings.refresh_token_expire_days * 24 * 3600

    async def logout(self, refresh_token: str) -> None:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except pyjwt.PyJWTError:
            return
        jti = payload["jti"]
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        await self.session.execute(
            RefreshTokenSession.__table__.update()
            .where(RefreshTokenSession.jti == jti, RefreshTokenSession.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        await self._deny_jti(jti, exp)
        await self.session.commit()

    async def _revoke_family(self, user_id: int, family: str | None, reason: str) -> None:
        if not family:
            return
        result = await self.session.execute(
            RefreshTokenSession.__table__.select().where(
                RefreshTokenSession.user_id == user_id, RefreshTokenSession.family_id == family
            )
        )
        rows = result.mappings().all()
        now = utcnow()
        await self.session.execute(
            RefreshTokenSession.__table__.update()
            .where(
                RefreshTokenSession.user_id == user_id,
                RefreshTokenSession.family_id == family,
                RefreshTokenSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        if self.redis is not None:
            try:
                for row in rows:
                    exp = row["expires_at"]
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    if exp > now:
                        await self.redis.set(f"{DENYLIST_PREFIX}{row['jti']}", reason, ex=max(int((exp - now).total_seconds()), 1))
            except Exception:
                pass
        await self.session.commit()

    async def _deny_jti(self, jti: str, expires_at: datetime) -> None:
        if self.redis is None:
            return
        try:
            ttl = max(int((expires_at - utcnow()).total_seconds()), 1)
            await self.redis.set(f"{DENYLIST_PREFIX}{jti}", "revoked", ex=ttl)
        except Exception:
            pass

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(user.password_hash, current_password):
            raise ValidationError("Current password is incorrect", field_errors={"currentPassword": "Incorrect password"})
        user.password_hash = hash_password(new_password)
        user.password_changed_at = utcnow()
        await self.users.revoke_all_refresh_sessions(user.id)
        await self.audit.add(
            AuditLog(
                user_id=user.id, user_name=user.display_name, action="password_changed",
                entity_type="user", entity_id=str(user.id), entity_label=user.email,
            )
        )
        await self.session.commit()

    async def forgot_password(self, email: str, ip: str | None) -> bool:
        await self.limiter.hit(f"pwreset:{email.lower()}", settings.rate_limit_reset_per_hour, 3600)
        await self.limiter.hit(f"pwreset:ip:{ip}", settings.rate_limit_reset_per_hour * 5, 3600)
        user = await self.users.get_by_email(email)
        if user is None or user.status != "Active":
            return False
        if not user.telegram_chat_id or not user.telegram_linked_at:
            return False
        if self.redis is None:
            return False
        code = generate_reset_code()
        payload = {
            "user_id": user.id,
            "code_hash": _hash_code(code),
            "attempts": 0,
            "chat_id": user.telegram_chat_id,
        }
        ttl = settings.telegram_reset_code_expire_minutes * 60
        key = _reset_key(email)
        await _safe_set(self.redis, key, payload, ttl)
        await _safe_set(
            self.redis,
            f"{RESET_DELIVERY_PREFIX}{email.lower()}",
            {"code": code, "chat_id": user.telegram_chat_id},
            min(ttl, 300),
        )
        from app.models import OutboxEvent

        self.session.add(
            OutboxEvent(
                event_type="password_reset_requested",
                payload={"email": user.email, "user_id": user.id},
                queue="critical",
            )
        )
        await self.session.commit()
        return True

    async def take_reset_delivery(self, email: str) -> dict | None:
        if self.redis is None:
            return None
        try:
            import json

            raw = await self.redis.get(f"{RESET_DELIVERY_PREFIX}{email.lower()}")
            if raw is None:
                return None
            await self.redis.delete(f"{RESET_DELIVERY_PREFIX}{email.lower()}")
            return json.loads(raw)
        except Exception:
            return None

    async def get_reset_challenge(self, email: str) -> dict | None:
        if self.redis is None:
            return None
        return await _safe_get(self.redis, _reset_key(email))

    async def consume_reset_challenge(self, email: str) -> dict | None:
        if self.redis is None:
            return None
        key = _reset_key(email)
        data = await _safe_get(self.redis, key)
        if data:
            await _safe_delete(self.redis, key)
        return data

    async def bump_reset_attempts(self, email: str, challenge: dict, ttl: int) -> int:
        challenge["attempts"] = int(challenge.get("attempts", 0)) + 1
        if self.redis is not None:
            await _safe_set(self.redis, _reset_key(email), challenge, max(ttl, 1))
        return int(challenge["attempts"])

    async def verify_reset_code(self, email: str, code: str) -> str:
        await self.limiter.hit(f"pwverify:{email.lower()}", 10, 600)
        challenge = await self.get_reset_challenge(email)
        if not challenge:
            raise ValidationError("Reset code is invalid or expired")
        user = await self.users.get(int(challenge["user_id"]))
        if user is None or user.email.lower() != email.lower():
            raise ValidationError("Reset code is invalid or expired")
        ttl = settings.telegram_reset_code_expire_minutes * 60
        if _hash_code(code.strip()) != challenge["code_hash"]:
            attempts = await self.bump_reset_attempts(email, challenge, ttl)
            if attempts >= settings.telegram_reset_max_attempts:
                await self.consume_reset_challenge(email)
            raise ValidationError("Reset code is invalid or expired")
        await self.consume_reset_challenge(email)
        token, _ = create_password_reset_jwt(user.id)
        await self.audit.add(
            AuditLog(
                user_id=user.id, user_name=user.display_name, action="password_reset_verified",
                entity_type="user", entity_id=str(user.id), entity_label=user.email,
            )
        )
        await self.session.commit()
        return token

    async def reset_password(self, email: str, reset_token: str, new_password: str) -> None:
        try:
            payload = decode_token(reset_token, expected_type="password_reset")
        except pyjwt.PyJWTError:
            raise ValidationError("Reset token is invalid or expired")
        user = await self.users.get(int(payload["sub"]))
        if user is None or user.email.lower() != email.lower():
            raise ValidationError("Reset token is invalid or expired")
        user.password_hash = hash_password(new_password)
        user.password_changed_at = utcnow()
        await self.users.revoke_all_refresh_sessions(user.id)
        await self.audit.add(
            AuditLog(
                user_id=user.id, user_name=user.display_name, action="password_reset",
                entity_type="user", entity_id=str(user.id), entity_label=user.email,
            )
        )
        await self.session.commit()

    async def create_link_code(self, user: User) -> str:
        code = secrets.token_hex(4).upper()
        if self.redis is None:
            raise ConflictError("Link codes require Redis")
        await _safe_set(self.redis, f"{LINK_PREFIX}{code}", {"user_id": user.id}, 600)
        return code

    async def consume_link_code(self, code: str, telegram_user_id: str, telegram_chat_id: str) -> User:
        if self.redis is None:
            raise ValidationError("Link code is invalid or expired")
        key = f"{LINK_PREFIX}{code.strip().upper()}"
        data = await _safe_get(self.redis, key)
        if not data:
            raise ValidationError("Link code is invalid or expired")
        user = await self.users.get(int(data["user_id"]))
        if user is None:
            raise NotFoundError("User not found")
        user.telegram_user_id = str(telegram_user_id)
        user.telegram_chat_id = str(telegram_chat_id)
        user.telegram_linked_at = utcnow()
        await _safe_delete(self.redis, key)
        await self.audit.add(
            AuditLog(
                user_id=user.id, user_name=user.display_name, action="telegram_linked",
                entity_type="user", entity_id=str(user.id), entity_label=user.email,
            )
        )
        await self.session.commit()
        return user

    async def unlink_telegram(self, user: User) -> None:
        user.telegram_user_id = None
        user.telegram_chat_id = None
        user.telegram_linked_at = None
        await self.audit.add(
            AuditLog(
                user_id=user.id, user_name=user.display_name, action="telegram_unlinked",
                entity_type="user", entity_id=str(user.id), entity_label=user.email,
            )
        )
        await self.session.commit()


def _safe_redis() -> aioredis.Redis | None:
    try:
        return get_redis()
    except Exception:
        return None


async def _safe_get(redis: aioredis.Redis, key: str) -> dict | None:
    try:
        import json

        raw = await redis.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def _safe_set(redis: aioredis.Redis, key: str, value: dict, ttl: int) -> None:
    try:
        import json

        await redis.set(key, json.dumps(value), ex=ttl)
    except Exception:
        pass


async def _safe_delete(redis: aioredis.Redis, key: str) -> None:
    try:
        await redis.delete(key)
    except Exception:
        pass
