import io
import uuid

import numpy as np
from PIL import Image
import pytest
import soundfile as sf

from core import signal_png, signal_audio

SECRET = "development-test-secret-" * 3
ID = str(uuid.UUID("35b63f71-74d5-45dc-bdd7-7b5a00d227e9"))


@pytest.mark.parametrize("mode", ["L", "LA", "RGB", "RGBA"])
def test_png_pixels_and_recovery(mode):
    rng = np.random.default_rng(14)
    shape = (512, 514) if mode == "L" else (512, 514, len(mode))
    pixels = rng.integers(20, 235, shape, dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(pixels, mode=mode).save(buf, "PNG")
    marked = signal_png.embed_bytes(buf.getvalue(), ID, SECRET)
    assert signal_png.extract_bytes(marked, SECRET) == ID
    assert signal_png.extract_bytes(marked, SECRET + "wrong") is None
    assert signal_png.extract_bytes(buf.getvalue(), SECRET) is None
    out = np.asarray(Image.open(io.BytesIO(marked)))
    assert out.shape == pixels.shape
    if "A" in mode:
        np.testing.assert_array_equal(out[:, :, -1], pixels[:, :, -1])
    mse = np.mean((out.astype(float) - pixels) ** 2)
    assert 10 * np.log10(255 ** 2 / mse) > 40
    # Pixel-preserving PNG reserialization without any metadata.
    clean = io.BytesIO()
    Image.fromarray(out).save(clean, "PNG")
    assert signal_png.extract_bytes(clean.getvalue(), SECRET) == ID


def make_audio(fmt="WAV", subtype="PCM_16", channels=1, rate=44100):
    rng = np.random.default_rng(27)
    t = np.arange(rate * 6) / rate
    samples = 0.18 * np.sin(2 * np.pi * 440 * t) + 0.04 * rng.normal(size=len(t))
    if channels == 2:
        samples = np.column_stack((samples, samples * 0.8))
    buf = io.BytesIO()
    sf.write(buf, samples, rate, format=fmt, subtype=subtype)
    return buf.getvalue()


@pytest.mark.parametrize("fmt,subtype,channels", [("WAV", "PCM_16", 1), ("WAV", "FLOAT", 2), ("FLAC", "PCM_24", 2)])
def test_audio_roundtrip_and_quality(fmt, subtype, channels):
    data = make_audio(fmt, subtype, channels)
    marked = signal_audio.embed_bytes(data, ID, SECRET)
    assert signal_audio.extract_bytes(marked, SECRET) == ID
    assert signal_audio.extract_bytes(marked, SECRET + "wrong") is None
    assert signal_audio.extract_bytes(data, SECRET) is None
    a, rate = sf.read(io.BytesIO(data))
    b, out_rate = sf.read(io.BytesIO(marked))
    assert a.shape == b.shape and rate == out_rate
    assert 10 * np.log10(np.sum(a ** 2) / np.sum((a - b) ** 2)) > 35
    # Lossless format conversion drops the original container metadata.
    converted = io.BytesIO()
    sf.write(converted, b, rate, format="FLAC", subtype="PCM_24")
    assert signal_audio.extract_bytes(converted.getvalue(), SECRET) == ID
    quieter = io.BytesIO()
    sf.write(quieter, b * 0.75, rate, format="WAV", subtype="PCM_24")
    assert signal_audio.extract_bytes(quieter.getvalue(), SECRET) == ID


def test_quiet_and_short_audio_fail():
    for samples in (np.zeros(44100 * 6), np.ones(44100) * 0.1):
        buffer = io.BytesIO()
        sf.write(buffer, samples, 44100, format="WAV")
        with pytest.raises(ValueError):
            signal_audio.embed_bytes(buffer.getvalue(), ID, SECRET)


def test_small_png_fails():
    buf = io.BytesIO()
    Image.new("RGB", (64, 64)).save(buf, "PNG")
    with pytest.raises(ValueError, match="capacity"):
        signal_png.embed_bytes(buf.getvalue(), ID, SECRET)
