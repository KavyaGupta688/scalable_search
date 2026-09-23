"""Technical metadata (pixel size, duration, fps) captured for the search resolution filter."""

import shutil
from types import SimpleNamespace

import pytest

from modules.ai_tag_description_generation.worker.pipeline import technical_metadata as tm
from modules.ai_tag_description_generation.worker.pipeline.metadata_fusion import fuse_metadata


def prep(modality, data):
    return SimpleNamespace(modality=SimpleNamespace(value=modality), data=data)


def test_image_size_comes_from_the_orientation_normalized_image():
    data = SimpleNamespace(
        original_image=SimpleNamespace(size=(2160, 3840)), original_size=(3840, 2160)
    )
    assert tm.from_preprocessing(prep("image", data)) == {"width": 2160, "height": 3840}


def test_video_reports_size_duration_and_fps():
    data = SimpleNamespace(resolution=(3840, 2160), duration_seconds=12.5, fps=29.97)
    assert tm.from_preprocessing(prep("video", data)) == {
        "width": 3840, "height": 2160, "duration": 12.5, "fps": 29.97,
    }


def test_audio_reports_only_duration():
    assert tm.from_preprocessing(prep("audio", SimpleNamespace(duration_seconds=61.0))) == {"duration": 61.0}


def test_other_modalities_and_failed_preprocessing_yield_nothing():
    assert tm.from_preprocessing(prep("document", SimpleNamespace())) == {}
    assert tm.from_preprocessing(prep("csv", SimpleNamespace())) == {}
    assert tm.from_preprocessing(SimpleNamespace(modality=SimpleNamespace(value="image"), data=None)) == {}
    assert tm.from_preprocessing(None) == {}


def test_unknown_values_are_omitted_never_stored_as_zero():
    data = SimpleNamespace(resolution=(0, 0), duration_seconds=0, fps=None)
    assert tm.from_preprocessing(prep("video", data)) == {}


def test_fusion_stores_technical_facts_next_to_quality_labels():
    quality = SimpleNamespace(blur_score=1.0, overall_quality="good", is_blurry=False, low_light=False, noisy_audio=False)
    safety = SimpleNamespace(
        contains_pii=False, nsfw_flagged=False, ai_generated_flagged=False, pii_types=[], faces_detected=0,
        nsfw_score=0.0, ai_generated_score=0.0, toxicity_score=0.0, analysis_incomplete=False,
        analysis_errors=[], pii_details=[],
    )
    common = dict(tags=[], captions={}, extracted_text={}, quality_labels=quality, safety_labels=safety, modality="image", model_versions={})
    with_facts = fuse_metadata(**common, technical={"width": 4000, "height": 3000})
    assert with_facts["quality_labels"]["technical"] == {"width": 4000, "height": 3000}
    assert with_facts["quality_labels"]["overall_quality"] == "good"  # existing keys untouched
    assert fuse_metadata(**common)["quality_labels"]["technical"] == {}


def test_probe_reads_image_size_and_honours_exif_rotation(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    plain = tmp_path / "plain.png"
    Image.new("RGB", (4000, 3000)).save(plain)
    assert tm.probe(str(plain), "image/png") == {"width": 4000, "height": 3000}

    rotated = tmp_path / "rotated.jpg"
    photo = Image.new("RGB", (4000, 3000))
    exif = photo.getexif()
    exif[274] = 6  # stored landscape, displayed portrait
    photo.save(rotated, exif=exif)
    assert tm.probe(str(rotated), "image/jpeg") == {"width": 3000, "height": 4000}


def test_probe_ignores_other_media_types(tmp_path):
    assert tm.probe(str(tmp_path / "a.pdf"), "application/pdf") == {}


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe not installed")
def test_probe_reads_video_size_with_ffprobe(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg not installed")
    import subprocess

    clip = tmp_path / "clip.mp4"
    subprocess.run(
        [ffmpeg, "-v", "quiet", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=1", "-pix_fmt", "yuv420p", str(clip)],
        check=True,
    )
    result = tm.probe(str(clip), "video/mp4")
    assert (result["width"], result["height"]) == (1280, 720)
    assert result["duration"] > 0
