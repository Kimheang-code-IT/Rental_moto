from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import envelope, get_db_session, require_permission
from app.schemas.settings import (
    AppInfoUpdate,
    AppConfigUpdate,
    StorageProviderCreate,
    StorageProviderUpdate,
    TestEmailRequest,
    TestTelegramRequest,
)
from app.services.admin_service import SettingService
from app.services.settings_service import StorageProviderService, test_email_connection, test_telegram_connection

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/app-info")
async def get_app_info(
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.view")),
) -> dict:
    service = SettingService(session)
    return envelope(await service.get_app_info())


@router.patch("/app-info")
async def patch_app_info(
    body: AppInfoUpdate,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.edit")),
) -> dict:
    service = SettingService(session, user)
    updated = await service.update_app_info(body.model_dump(exclude_unset=True, by_alias=True))
    return envelope(updated)


@router.put("/app-info")
async def put_app_info(
    body: AppInfoUpdate,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.edit")),
) -> dict:
    return await patch_app_info(body, session, user)


@router.post("/app-info/reset")
async def reset_app_info(
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.configure")),
) -> dict:
    service = SettingService(session, user)
    return envelope(await service.reset_app_info())


@router.post("/reset-data")
async def reset_all_data(
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.configure")),
) -> dict:
    service = SettingService(session, user)
    return envelope(await service.reset_all_data())


@router.get("/app-config")
async def get_app_config(
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.view")),
) -> dict:
    service = SettingService(session)
    return envelope(await service.get_app_config(mask=True))


@router.patch("/app-config")
async def patch_app_config(
    body: AppConfigUpdate,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.edit")),
) -> dict:
    service = SettingService(session, user)
    updated = await service.update_app_config(body.model_dump(exclude_unset=True, by_alias=True))
    return envelope(updated)


@router.put("/app-config")
async def put_app_config(
    body: AppConfigUpdate,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.edit")),
) -> dict:
    return await patch_app_config(body, session, user)


@router.post("/app-config/email/test-connection")
async def email_test_connection(
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.configure")),
) -> dict:
    result = await test_email_connection(session)
    return envelope(result)


@router.post("/app-config/email/send-test")
async def email_send_test(
    body: TestEmailRequest,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.configure")),
) -> dict:
    result = await test_email_connection(session, send_to=body.to)
    return envelope(result)


@router.post("/app-config/telegram/test-connection")
async def telegram_test_connection(
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.configure")),
) -> dict:
    result = await test_telegram_connection(session, send_message=True)
    return envelope(result)


@router.post("/app-config/telegram/send-test")
async def telegram_send_test(
    body: TestTelegramRequest,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.configure")),
) -> dict:
    result = await test_telegram_connection(session, destination_id=body.destination_id, send_message=True)
    return envelope(result)


@router.get("/storage")
async def list_storage(
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.view")),
) -> dict:
    service = StorageProviderService(session)
    providers = await service.list()
    return envelope(providers, {"page": 1, "limit": max(len(providers), 1), "total": len(providers)})


@router.post("/storage", status_code=201)
async def create_storage(
    body: StorageProviderCreate,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.configure")),
) -> dict:
    service = StorageProviderService(session)
    provider = await service.create(body, user.id if user else None)
    return envelope(provider)


@router.get("/storage/{provider_id}")
async def get_storage(
    provider_id: str,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.view")),
) -> dict:
    service = StorageProviderService(session)
    return envelope(await service.get(provider_id))


@router.put("/storage/{provider_id}")
async def update_storage(
    provider_id: str,
    body: StorageProviderUpdate,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.configure")),
) -> dict:
    service = StorageProviderService(session)
    return envelope(await service.update(provider_id, body, user.id if user else None))


@router.delete("/storage/{provider_id}")
async def delete_storage(
    provider_id: str,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.configure")),
) -> dict:
    service = StorageProviderService(session)
    await service.delete(provider_id)
    return envelope({"deleted": True})


@router.post("/storage/{provider_id}/test-connection")
async def test_storage(
    provider_id: str,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.configure")),
) -> dict:
    service = StorageProviderService(session)
    return envelope(await service.test_connection(provider_id))


@router.post("/storage/{provider_id}/set-default")
async def set_default_storage(
    provider_id: str,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.configure")),
) -> dict:
    service = StorageProviderService(session)
    return envelope(await service.set_flag(provider_id, is_default=True))


@router.post("/storage/{provider_id}/set-active")
async def set_active_storage(
    provider_id: str,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("settings.app_config.configure")),
) -> dict:
    service = StorageProviderService(session)
    return envelope(await service.set_flag(provider_id, active=True))

