from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ingestion.connectors.s3 import S3Connector
from ingestion.schemas.connector import S3AuthenticationUpdate, S3ConnectorFields
from ingestion.services.source_access import SourceAccessDeniedError, entitlement_url_lifetime


def test_static_keys_remain_supported_for_development():
    fields = S3ConnectorFields(
        endpoint_url="https://s3.ap-south-1.amazonaws.com",
        bucket="development-bucket",
        access_key="development-key",
        secret_key="development-secret",
    )
    assert fields.auth_mode == "static_keys"


def test_assume_role_rejects_vendor_static_keys():
    with pytest.raises(ValueError, match="Do not send vendor access keys"):
        S3ConnectorFields(
            endpoint_url="https://s3.ap-south-1.amazonaws.com",
            bucket="vendor-bucket",
            auth_mode="aws_assume_role",
            role_arn="arn:aws:iam::123456789012:role/VendorRead",
            access_key="must-not-be-used",
            secret_key="must-not-be-used",
        )


def test_existing_connector_can_be_switched_to_assume_role():
    update = S3AuthenticationUpdate(
        auth_mode="aws_assume_role",
        role_arn="arn:aws:iam::123456789012:role/VendorRead",
        external_id="vendor-external-id",
        session_duration_seconds=1800,
    )
    assert update.auth_mode == "aws_assume_role"
    assert update.access_key is None


def test_assume_role_credentials_are_cached_and_include_session_token(monkeypatch):
    calls = {"assume": 0, "assume_request": None, "s3": []}

    class FakeSTS:
        def assume_role(self, **request):
            calls["assume"] += 1
            calls["assume_request"] = request
            assert request["ExternalId"] == "vendor-external-id"
            return {
                "Credentials": {
                    "AccessKeyId": "temporary-key",
                    "SecretAccessKey": "temporary-secret",
                    "SessionToken": "temporary-token",
                    "Expiration": datetime.now(UTC) + timedelta(hours=1),
                }
            }

    class FakeS3:
        pass

    def fake_boto_client(service_name, **kwargs):
        if service_name == "sts":
            return FakeSTS()
        calls["s3"].append(kwargs)
        return FakeS3()

    monkeypatch.setattr("ingestion.connectors.s3.boto3.client", fake_boto_client)
    connector = S3Connector(
        endpoint_url="https://s3.ap-south-1.amazonaws.com",
        bucket="vendor-bucket",
        access_key="",
        secret_key="",
        auth_mode="aws_assume_role",
        role_arn="arn:aws:iam::123456789012:role/VendorRead",
        external_id="vendor-external-id",
        connector_id=uuid4(),
    )

    client = connector.client_for_entitlement(1800)
    assert client is connector.client
    assert calls["assume"] == 1
    assert calls["assume_request"]["DurationSeconds"] == 1800
    assert calls["s3"][0]["aws_session_token"] == "temporary-token"


def test_presigned_url_lifetime_never_crosses_entitlement_expiry():
    now = datetime(2026, 9, 19, tzinfo=UTC)
    assert entitlement_url_lifetime(now + timedelta(seconds=120), 3600, now=now) == 120
    with pytest.raises(SourceAccessDeniedError):
        entitlement_url_lifetime(now, 3600, now=now)


def test_assume_role_does_not_issue_session_inside_final_fifteen_minutes(monkeypatch):
    monkeypatch.setattr("ingestion.connectors.s3.boto3.client", lambda *_args, **_kwargs: object())
    connector = S3Connector(
        endpoint_url="https://s3.ap-south-1.amazonaws.com",
        bucket="vendor-bucket",
        access_key="",
        secret_key="",
        auth_mode="aws_assume_role",
        role_arn="arn:aws:iam::123456789012:role/VendorRead",
    )
    with pytest.raises(PermissionError, match="minimum session duration"):
        connector.client_for_entitlement(899)
