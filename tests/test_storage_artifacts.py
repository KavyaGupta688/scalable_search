import pytest

from core.s3_client import is_ignored_storage_key, s3_client


@pytest.mark.parametrize(
    "key",
    [
        "dataset/._clip.mp4",
        "__MACOSX/dataset/clip.mp4",
        "dataset/__MACOSX/clip.mp4",
        "dataset/.DS_Store",
    ],
)
def test_macos_storage_artifacts_are_ignored(key):
    assert is_ignored_storage_key(key)


@pytest.mark.parametrize(
    "key",
    ["dataset/clip.mp4", "dataset/frame.jpg", "dataset/.hidden-data.csv"],
)
def test_real_assets_are_not_ignored(key):
    assert not is_ignored_storage_key(key)


def test_sidecar_cannot_be_downloaded():
    with pytest.raises(FileNotFoundError, match="sidecar"):
        s3_client.get_file_stream("dataset/._clip.mp4")
