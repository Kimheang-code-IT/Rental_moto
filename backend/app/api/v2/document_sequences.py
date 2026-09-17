from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ListParams, envelope, get_db_session, require_permission
from app.schemas.admin import DocumentSequenceCreate, DocumentSequenceUpdate
from app.services.admin_service import default_document_sequences
from app.repositories.admin import DocumentSequenceRepository

router = APIRouter(prefix="/document-sequences", tags=["document-sequences"])


def _to_dict(seq) -> dict:
    return {
        "id": seq.id,
        "documentType": seq.document_type,
        "prefix": seq.prefix,
        "year": seq.year,
        "paddingLength": seq.padding_length,
        "lastValue": seq.last_value,
        "status": seq.status,
        "note": seq.note,
        "createdAt": seq.created_at.isoformat(),
        "updatedAt": seq.updated_at.isoformat(),
    }


@router.get("")
async def list_sequences(
    params: ListParams = Depends(),
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("configuration.view")),
) -> dict:
    repo = DocumentSequenceRepository(session)
    items, total = await repo.list(params.q, params.page, params.limit)
    return envelope([_to_dict(s) for s in items], {"page": params.page, "limit": params.limit, "total": total})


@router.post("/seed-defaults", status_code=201)
async def seed_defaults(
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("configuration.create")),
) -> dict:
    repo = DocumentSequenceRepository(session)
    created = 0
    for spec in default_document_sequences():
        existing = await repo.get_by_type(spec["document_type"])
        if existing is None:
            from app.models import DocumentSequence

            seq_id = f"ds-{spec['document_type'].lower().replace('_', '-')}"
            await repo.add(
                DocumentSequence(
                    id=seq_id,
                    document_type=spec["document_type"],
                    prefix=spec.get("prefix", ""),
                    padding_length=spec.get("padding_length", 6),
                    year=spec.get("year"),
                )
            )
            created += 1
    await session.commit()
    return envelope({"created": created})


@router.post("", status_code=201)
async def create_sequence(
    body: DocumentSequenceCreate,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("configuration.create")),
) -> dict:
    repo = DocumentSequenceRepository(session)
    existing = await repo.get_by_type(body.document_type)
    if existing is not None:
        from app.core.errors import ConflictError

        raise ConflictError(f"Sequence for {body.document_type} already exists")
    seq_id = body.id or f"ds-{body.document_type.lower().replace('_', '-')}"
    from app.models import DocumentSequence

    seq = await repo.add(
        DocumentSequence(
            id=seq_id,
            document_type=body.document_type,
            prefix=body.prefix,
            year=body.year,
            padding_length=body.padding_length,
            last_value=body.last_value,
            status=body.status,
            note=body.note,
        )
    )
    await session.commit()
    return envelope(_to_dict(seq))


@router.get("/{seq_id}")
async def get_sequence(
    seq_id: str,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("configuration.view")),
) -> dict:
    from app.core.errors import NotFoundError

    repo = DocumentSequenceRepository(session)
    seq = await repo.get(seq_id)
    if seq is None:
        raise NotFoundError("Document sequence not found")
    return envelope(_to_dict(seq))


@router.put("/{seq_id}")
async def update_sequence(
    seq_id: str,
    body: DocumentSequenceUpdate,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("configuration.edit")),
) -> dict:
    from app.core.errors import NotFoundError

    repo = DocumentSequenceRepository(session)
    seq = await repo.get(seq_id)
    if seq is None:
        raise NotFoundError("Document sequence not found")
    updates = body.model_dump(exclude_unset=True, by_alias=False)
    for field, value in updates.items():
        setattr(seq, field, value)
    await session.commit()
    return envelope(_to_dict(seq))


@router.delete("/{seq_id}")
async def delete_sequence(
    seq_id: str,
    session: AsyncSession = Depends(get_db_session),
    user=Depends(require_permission("configuration.delete")),
) -> dict:
    from app.core.errors import NotFoundError

    repo = DocumentSequenceRepository(session)
    seq = await repo.get(seq_id)
    if seq is None:
        raise NotFoundError("Document sequence not found")
    await repo.delete(seq)
    await session.commit()
    return envelope({"deleted": True})
