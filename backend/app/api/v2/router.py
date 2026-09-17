from fastapi import APIRouter

from app.api.v2 import (
    audit_logs,
    auth,
    charges,
    customers,
    dashboard,
    document_sequences,
    expenses,
    exports,
    health,
    motorcycles,
    payments,
    permissions,
    rentals,
    roles,
    search,
    settings,
    tasks,
    telegram,
    users,
)

api_router = APIRouter(prefix="/api/v2")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(permissions.router)
api_router.include_router(motorcycles.router)
api_router.include_router(customers.router)
api_router.include_router(rentals.router)
api_router.include_router(payments.router)
api_router.include_router(charges.router)
api_router.include_router(expenses.router)
api_router.include_router(dashboard.router)
api_router.include_router(audit_logs.router)
api_router.include_router(document_sequences.router)
api_router.include_router(settings.router)
api_router.include_router(search.router)
api_router.include_router(exports.router)
api_router.include_router(tasks.router)
api_router.include_router(telegram.router)
