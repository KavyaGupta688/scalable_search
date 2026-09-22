from __future__ import annotations

from uuid import uuid4

import pytest

from ingestion.connectors.base import PermanentConnectorError
from ingestion.schemas.job import JobDescriptor
from ingestion.storage.source_metadata import clear_metadata_cache, resolve_source_metadata, is_metadata_control_file
from ingestion.worker.validator import PermanentProcessingError


class MetadataConnector:
    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects

    async def open_stream(self, job):
        key = job.object_key
        if key not in self.objects:
            raise PermanentConnectorError(f"NoSuchKey: {key}")
        yield self.objects[key]


def s3_job(key: str) -> JobDescriptor:
    return JobDescriptor(
        source_type="S3",
        connector_id=uuid4(),
        source_ref=f"demo-bucket/{key}",
        provisional_id="etag",
        bucket="demo-bucket",
        object_key=key,
        size_bytes=10,
        etag="etag",
        run_id=uuid4(),
    )


@pytest.fixture(autouse=True)
def empty_manifest_cache():
    clear_metadata_cache()
    yield
    clear_metadata_cache()


def test_files_only_does_not_silently_discard_a_csv_named_metadata():
    job = s3_job('data/metadata.csv')
    assert not is_metadata_control_file(job, 'none')
    assert is_metadata_control_file(job, 'required')
    assert is_metadata_control_file(job, 'optional')


@pytest.mark.asyncio
async def test_optional_metadata_accepts_files_without_manifests():
    connector = MetadataConnector({})
    connector.metadata_mode = "optional"
    assert await resolve_source_metadata(connector, s3_job("images/photo.jpg")) is None


@pytest.mark.asyncio
async def test_explicit_required_metadata_overrides_legacy_global_default(monkeypatch):
    from ingestion.config import get_settings
    monkeypatch.setattr(get_settings().external_metadata, 'required', False)
    connector = MetadataConnector({})
    connector.metadata_mode = 'required'
    with pytest.raises(PermanentProcessingError, match='No vendor metadata matched'):
        await resolve_source_metadata(connector, s3_job('images/photo.jpg'))


@pytest.mark.asyncio
async def test_files_only_never_reads_vendor_sidecars():
    class FilesOnly:
        metadata_mode = "none"

        async def open_stream(self, job):
            raise AssertionError("Files-only mode must not request sidecars")
            yield
    assert await resolve_source_metadata(FilesOnly(), s3_job("images/photo.jpg")) is None


@pytest.mark.asyncio
async def test_metadata_csv_is_parsed_into_typed_fields():
    csv = (
        "id,filename,title,category,tags,width,height,file_size_bytes,mime_type,"
        "camera_make,camera_model,location_name,gps_lat,gps_lon,taken_at,uploaded_at,"
        "view_count,download_count\n"
        "4821,street.jpg,Man with umbrella,Photography,people|rain,1920,1080,3847291,"
        "image/jpeg,Canon,EOS R5,Tokyo,35.6762,139.6503,2025-03-12T09:14:00Z,"
        "2025-06-01T08:00:00Z,142,37\n"
    ).encode()
    result = await resolve_source_metadata(
        MetadataConnector({"images/metadata.csv": csv}),
        s3_job("images/street.jpg"),
    )

    assert result is not None
    assert result.external_asset_id == "4821"
    assert result.tags == ["people", "rain"]
    assert result.additional_metadata == {}
    assert result.metadata_formats == ["metadata_csv"]


@pytest.mark.asyncio
async def test_stock_manifest_matches_full_s3_target_path():
    csv = (
        "asset_id,target_path,brand,image_type,description,keywords,categories,contributor_id\n"
        "23475689,s3://demo-bucket/images/huge.jpg,Shutterstock,photo,A city,"
        '"adventure, coast","building, landmark",vendor-7\n'
    ).encode()
    result = await resolve_source_metadata(
        MetadataConnector({"metadata11.csv": csv}),
        s3_job("images/huge.jpg"),
    )

    assert result is not None
    assert result.external_asset_id == "23475689"
    assert result.brand == "Shutterstock"
    assert result.tags == ["adventure", "coast"]
    assert result.categories == ["building", "landmark"]


@pytest.mark.asyncio
async def test_sidecars_merge_tags_and_labels_and_allow_missing_fields():
    connector = MetadataConnector(
        {
            "images/4821/.id": b"4821",
            "images/4821/.desc": b"Man walking with umbrella",
            "images/4821/.tags": b"people, rain, street",
            "images/4821/.lab": b"outdoor, street",
            "images/4821/.cate": b"Photography",
        }
    )
    result = await resolve_source_metadata(connector, s3_job("images/4821/.jpg"))

    assert result is not None
    assert result.external_asset_id == "4821"
    assert result.primary_category == "Photography"
    assert result.tags == ["people", "rain", "street", "outdoor"]
    assert result.metadata_formats == ["sidecar"]


@pytest.mark.asyncio
async def test_multimodal_extra_fields_are_bounded_vendor_metadata():
    csv = (
        "asset_id,target_path,title,description,keywords,categories,duration_seconds,frame_rate\n"
        "VID-7,s3://demo-bucket/videos/coast.mp4,Coast,A coastal video,sea,Video,125.4,29.97\n"
    ).encode()
    result = await resolve_source_metadata(
        MetadataConnector({"videos/metadata11.csv": csv}),
        s3_job("videos/coast.mp4"),
    )

    assert result is not None
    assert result.external_asset_id == "VID-7"
    assert result.title == "Coast"
    assert result.tags == ["sea"]
    assert result.additional_metadata == {
        "duration_seconds": 125.4,
        "frame_rate": 29.97,
    }


@pytest.mark.parametrize(
    "filename",
    ["clip.mp4", "speech.mp3", "report.pdf", "letter.docx", "notes.txt", "data.csv"],
)
@pytest.mark.asyncio
async def test_common_metadata_is_not_limited_to_images(filename):
    csv = (
        "id,filename,title,description,category,tags\n"
        f"ASSET-1,{filename},Example asset,Vendor description,Demo,one|two\n"
    ).encode()
    result = await resolve_source_metadata(
        MetadataConnector({"mixed/metadata.csv": csv}),
        s3_job(f"mixed/{filename}"),
    )

    assert result is not None
    assert result.external_asset_id == "ASSET-1"
    assert result.title == "Example asset"
    assert result.tags == ["one", "two"]
