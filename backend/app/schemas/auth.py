from pydantic import EmailStr, Field

from app.schemas.common import CamelModel


class LoginRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshRequest(CamelModel):
    refresh_token: str


class LogoutRequest(CamelModel):
    refresh_token: str


class TokenPairResponse(CamelModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_expires_in: int


class SourcePermissionModel(CamelModel):
    id: str
    document_type: str
    only_if_creator: bool = False
    level: int | None = None
    actions: list[str] = []


class AuthUserResponse(CamelModel):
    id: int
    name: str
    email: str
    role: str | None = None
    avatar: str | None = None
    permissions: list[str] = []
    page_access: list[str] = []
    source_permissions: list[str] = []


class ChangePasswordRequest(CamelModel):
    current_password: str
    new_password: str = Field(min_length=6)


class ForgotPasswordRequest(CamelModel):
    email: EmailStr


class VerifyResetCodeRequest(CamelModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=10)


class ResendResetCodeRequest(CamelModel):
    email: EmailStr


class ResetPasswordRequest(CamelModel):
    email: EmailStr
    reset_token: str
    new_password: str = Field(min_length=6)


class AvatarUpdateRequest(CamelModel):
    avatar: str | None = None


class TelegramLinkCodeRequest(CamelModel):
    pass


class ServiceTokenRequest(CamelModel):
    client_id: str
    client_secret: str


class ServiceTokenResponse(CamelModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class GenericMessageResponse(CamelModel):
    message: str
