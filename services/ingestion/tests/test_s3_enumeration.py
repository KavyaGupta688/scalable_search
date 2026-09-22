from __future__ import annotations

from uuid import uuid4

import pytest

from ingestion.connectors.s3 import S3Connector


def test_public_bucket_does_not_sign_requests_or_assume_roles():
    from botocore import UNSIGNED
    connector = S3Connector(endpoint_url="https://s3.us-east-1.amazonaws.com",
                            bucket="public-images", connector_id=uuid4(),
                            access_key="", secret_key="", auth_mode="anonymous")
    assert connector.client.meta.config.signature_version is UNSIGNED
    assert connector.client_for_entitlement(300) is connector.client


class FakeS3Client:
    def __init__(self, pages: list[dict]):
        self.pages = pages
        self.calls: list[dict] = []

    def list_objects_v2(self, **kwargs):
        self.calls.append(kwargs)
        token = kwargs.get("ContinuationToken")
        return self.pages[1] if token == "page-2" else self.pages[0]


def page(keys: list[str], next_token: str | None = None) -> dict:
    result = {
        "Contents": [{"Key": key, "Size": 100, "ETag": f'"etag-{key}"'} for key in keys],
        "IsTruncated": next_token is not None,
    }
    if next_token:
        result["NextContinuationToken"] = next_token
    return result


@pytest.mark.asyncio
async def test_s3_enumeration_yields_after_first_page_without_materialising_all_pages():
    connector = S3Connector(
        endpoint_url="https://s3.ap-south-1.amazonaws.com",
        bucket="images",
        access_key="test",
        secret_key="test",
        connector_id=uuid4(),
        prefix="dataset/",
        page_size=2,
    )
    connector.checkpoint_interval = 1
    fake_client = FakeS3Client([page(["dataset/a.jpg", "dataset/b.jpg"], "page-2"), page(["dataset/c.jpg"])])
    connector._s3_client = fake_client

    iterator = connector.enumerate().__aiter__()
    first_job, first_checkpoint = await iterator.__anext__()

    assert first_job.object_key == "dataset/a.jpg"
    assert first_checkpoint is None
    # This is the regression assertion: the second page has not been fetched.
    assert len(fake_client.calls) == 1
    assert fake_client.calls[0] == {
        "Bucket": "images",
        "MaxKeys": 2,
        "Prefix": "dataset/",
    }

    remaining = [item async for item in iterator]
    assert [job.object_key for job, _ in remaining] == ["dataset/b.jpg", "dataset/c.jpg"]
    assert remaining[0][1] == "page-2"
    assert len(fake_client.calls) == 2
    assert fake_client.calls[1]["ContinuationToken"] == "page-2"


@pytest.mark.asyncio
async def test_s3_max_objects_is_a_hard_cap_and_does_not_scan_next_page():
    connector = S3Connector(
        endpoint_url="https://s3.ap-south-1.amazonaws.com",
        bucket="images",
        access_key="test",
        secret_key="test",
        connector_id=uuid4(),
        max_objects=3,
        page_size=1000,
    )
    fake_client = FakeS3Client([page(["a.jpg", "b.jpg", "c.jpg", "d.jpg"], "page-2"), page(["e.jpg"])])
    connector._s3_client = fake_client

    rows = [item async for item in connector.enumerate()]

    assert [job.object_key for job, _ in rows] == ["a.jpg", "b.jpg", "c.jpg"]
    assert len(fake_client.calls) == 1
    assert connector.last_enumeration_stats["limit_reached"] is True
