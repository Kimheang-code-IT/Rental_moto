from datetime import UTC, datetime

from app.services.object_storage_service import ObjectStorageService, invoice_object_name


class FakePutResult:
    etag = "etag-123"


class FakeMinioClient:
    def __init__(self, bucket_exists: bool = True):
        self.exists = bucket_exists
        self.created = []
        self.uploaded = []

    def bucket_exists(self, bucket):
        return self.exists

    def make_bucket(self, bucket):
        self.created.append(bucket)
        self.exists = True

    def put_object(self, bucket, object_name, stream, length, content_type):
        self.uploaded.append((bucket, object_name, stream.read(), length, content_type))
        return FakePutResult()


async def test_invoice_pdf_is_archived_under_readable_prefix():
    client = FakeMinioClient(bucket_exists=False)
    service = ObjectStorageService(
        endpoint="minio:9000",
        access_key="access",
        secret_key="secret",
        bucket="rental-files",
        client=client,
    )

    stored = await service.archive_invoice(
        "RNT-2026-000002",
        "Final-Invoice-RNT-2026-000002.pdf",
        b"%PDF-test",
        at=datetime(2026, 9, 3, tzinfo=UTC),
    )

    assert client.created == ["rental-files"]
    assert client.uploaded == [(
        "rental-files",
        "invoices/2026/09/RNT-2026-000002/Final-Invoice-RNT-2026-000002.pdf",
        b"%PDF-test",
        9,
        "application/pdf",
    )]
    assert stored.object_name == client.uploaded[0][1]
    assert stored.etag == "etag-123"


def test_invoice_object_name_sanitizes_path_segments():
    assert invoice_object_name(
        "RNT / unsafe",
        "Invoice name.pdf",
        at=datetime(2026, 1, 2, tzinfo=UTC),
    ) == "invoices/2026/01/RNT-unsafe/Invoice-name.pdf"
