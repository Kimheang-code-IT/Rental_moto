from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    client_ip,
    envelope,
    get_current_user,
    get_db_session,
    get_redis_dep,
)
from app.core.config import settings
from app.core.errors import AccessDeniedError
from app.core.permissions import effective_permissions
from app.core.security import create_service_token
from app.schemas.auth import (
    AvatarUpdateRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    ResendResetCodeRequest,
    ResetPasswordRequest,
    ServiceTokenRequest,
    VerifyResetCodeRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_user_payload(user) -> dict:
    permissions = effective_permissions(user)
    return {
        "id": user.id,
        "name": user.display_name,
        "email": user.email,
        "roleId": user.role_id,
        "role": user.role_ref.name,
        "avatar": user.avatar_url,
        "telegramLinked": bool(user.telegram_linked_at and user.telegram_chat_id),
        "effectivePermissions": permissions,
        "permissions": permissions,
        "pageAccess": permissions,
        "sourcePermissions": permissions,
    }


@router.post("/login", response_model=None)
async def login(
    body: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    redis=Depends(get_redis_dep),
) -> dict:
    service = AuthService(session, redis)
    access, refresh, expires_in, refresh_expires_in, user = await service.login(
        body.email, body.password, client_ip(request), request.headers.get("user-agent")
    )
    return envelope(
        {
            "accessToken": access,
            "refreshToken": refresh,
            "tokenType": "Bearer",
            "expiresIn": expires_in,
            "refreshExpiresIn": refresh_expires_in,
            "user": _auth_user_payload(user),
        }
    )


@router.post("/refresh")
async def refresh(
    body: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    redis=Depends(get_redis_dep),
) -> dict:
    service = AuthService(session, redis)
    access, new_refresh, expires_in, refresh_expires_in = await service.refresh(body.refresh_token, client_ip(request))
    return envelope(
        {
            "accessToken": access,
            "refreshToken": new_refresh,
            "tokenType": "Bearer",
            "expiresIn": expires_in,
            "refreshExpiresIn": refresh_expires_in,
        }
    )


@router.post("/logout")
async def logout(
    body: LogoutRequest,
    session: AsyncSession = Depends(get_db_session),
    redis=Depends(get_redis_dep),
) -> dict:
    service = AuthService(session, redis)
    await service.logout(body.refresh_token)
    return envelope({"message": "Logged out"})


@router.get("/me")
async def me(user=Depends(get_current_user)) -> dict:
    return envelope(_auth_user_payload(user))


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    redis=Depends(get_redis_dep),
) -> dict:
    service = AuthService(session, redis)
    await service.change_password(user, body.current_password, body.new_password)
    return envelope({"message": "Password changed"})


@router.patch("/profile/avatar")
async def update_avatar(
    body: AvatarUpdateRequest,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    user.avatar_url = body.avatar
    await session.commit()
    return envelope({"avatar": body.avatar})


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    redis=Depends(get_redis_dep),
) -> dict:
    service = AuthService(session, redis)
    await service.forgot_password(body.email, client_ip(request))
    return envelope({"message": "If the account is eligible, a reset code has been sent via Telegram"})


@router.post("/forgot-password/verify")
async def verify_reset_code(
    body: VerifyResetCodeRequest,
    session: AsyncSession = Depends(get_db_session),
    redis=Depends(get_redis_dep),
) -> dict:
    service = AuthService(session, redis)
    token = await service.verify_reset_code(body.email, body.code)
    return envelope({"resetToken": token, "message": "Code verified"})


@router.post("/forgot-password/resend")
async def resend_reset_code(
    body: ResendResetCodeRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    redis=Depends(get_redis_dep),
) -> dict:
    service = AuthService(session, redis)
    await service.forgot_password(body.email, client_ip(request))
    return envelope({"message": "If the account is eligible, a new reset code has been sent via Telegram"})


@router.post("/forgot-password/reset")
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
    redis=Depends(get_redis_dep),
) -> dict:
    service = AuthService(session, redis)
    await service.reset_password(body.email, body.reset_token, body.new_password)
    return envelope({"message": "Password has been reset"})


@router.post("/forgot-password/handoff")
async def forgot_password_handoff(
    body: dict,
    session: AsyncSession = Depends(get_db_session),
    redis=Depends(get_redis_dep),
) -> dict:
    handoff = str(body.get("handoff") or body.get("handoffToken") or "")
    if not handoff:
        raise ValidationError("handoff token is required")
    service = AuthService(session, redis)
    data = await service.exchange_handoff_token(handoff)
    return envelope({"email": data["email"], "resetToken": data["resetToken"], "message": "Handoff accepted"})


@router.post("/telegram/link-code")
async def telegram_link_code(
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    redis=Depends(get_redis_dep),
) -> dict:
    service = AuthService(session, redis)
    code = await service.create_link_code(user)
    return envelope({"code": code, "expiresIn": 600})


@router.post("/service-token")
async def service_token(body: ServiceTokenRequest) -> dict:
    import secrets

    if not secrets.compare_digest(body.client_id, settings.telegram_bot_client_id):
        raise AccessDeniedError("Invalid service credentials")
    if not secrets.compare_digest(body.client_secret, settings.telegram_bot_client_secret):
        raise AccessDeniedError("Invalid service credentials")
    token, expires = create_service_token(body.client_id)
    return envelope(
        {
            "accessToken": token,
            "tokenType": "Bearer",
            "expiresIn": settings.service_token_expire_minutes * 60,
        }
    )

