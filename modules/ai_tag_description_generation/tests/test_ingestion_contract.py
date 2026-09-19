import unittest

from modules.ai_tag_description_generation.app.event_schemas import IngestionDocumentEvent
from modules.ai_tag_description_generation.app.ingestion_client import (
    _download_url,
    document_from_event,
)


EVENT = {
    "run_id": "00000000-0000-0000-0000-000000000001",
    "document_id": "00000000-0000-0000-0000-000000000002",
    "source_asset_id": "00000000-0000-0000-0000-000000000003",
    "mime_type": "application/pdf",
    "size_bytes": 123,
    "checksum_sha256": "a" * 64,
    "source_connector_id": "00000000-0000-0000-0000-000000000004",
    "source_ref": "vendor-bucket/reports/a.pdf",
    "source_type": "S3",
    "entitlement_id": "00000000-0000-0000-0000-000000000005",
    "first_successful_ingested_at": "2026-09-19T00:00:00Z",
    "effective_expiry_at": "2029-09-19T00:00:00Z",
    "metadata_available": True,
    "metadata": {"title": "Vendor title", "tags": ["vendor-tag"]},
}


class IngestionContractTests(unittest.TestCase):
    def test_ingestion_event_preserves_identity_and_vendor_metadata(self) -> None:
        event = IngestionDocumentEvent.model_validate(EVENT)
        document = document_from_event(event)

        self.assertEqual(document.document_id, EVENT["document_id"])
        self.assertEqual(document.source_asset_id, EVENT["source_asset_id"])
        self.assertEqual(document.checksum_sha256, "a" * 64)
        self.assertEqual(document.metadata["tags"], ["vendor-tag"])

    def test_presigned_url_is_used_without_ai_credentials(self) -> None:
        url, headers = _download_url(
            {"access_mode": "presigned_url", "access_url": "https://vendor.example/object?signature=secret"},
            EVENT["document_id"],
        )
        self.assertTrue(url.startswith("https://vendor.example/"))
        self.assertEqual(headers, {})

    def test_nas_connector_stream_uses_ingestion_proxy(self) -> None:
        url, headers = _download_url(
            {"access_mode": "connector_stream", "access_url": None},
            EVENT["document_id"],
        )
        self.assertIn(f"/documents/{EVENT['document_id']}/content", url)
        self.assertIsInstance(headers, dict)


if __name__ == "__main__":
    unittest.main()
