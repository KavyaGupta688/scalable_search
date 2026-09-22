import io
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from core import native_aac

SECRET = "native-aac-development-secret-" * 3
ID = "35b63f71-74d5-45dc-bdd7-7b5a00d227e9"
pytestmark = pytest.mark.skipif(not (native_aac.NATIVE_ROOT / "ffmpeg-7.1/ffmpeg").is_file(), reason="Native AAC build required")


@pytest.mark.parametrize("channels,container", [(1, "adts"), (2, "ipod")])
def test_native_mdct_roundtrip(channels, container, tmp_path):
    rate = 44100
    t = np.arange(rate * 12) / rate
    rng = np.random.default_rng(53)
    x = 0.15 * np.sin(2 * np.pi * 440 * t) + 0.035 * rng.normal(size=len(t))
    if channels == 2:
        x = np.column_stack((x, x * 0.8))
    buffer = io.BytesIO()
    sf.write(buffer, x, rate, format="WAV", subtype="PCM_16")
    marked = native_aac.embed_bytes(buffer.getvalue(), ID, SECRET, container)
    assert native_aac.extract_bytes(marked, SECRET) == ID
    assert native_aac.extract_bytes(marked, SECRET + "wrong") is None
    original = tmp_path / "original.wav"
    baseline = tmp_path / "baseline.aac"
    watermarked = tmp_path / "marked.aac"
    original.write_bytes(buffer.getvalue())
    watermarked.write_bytes(marked)
    # Compare against an identical AAC encode without the watermark hook, so
    # ordinary codec loss is reported separately from watermark-induced change.
    native_aac._run([native_aac._tool("ffmpeg"), "-v", "error", "-i", str(original),
                     "-c:a", "aac", "-b:a", str(192000 * channels), "-aac_ms", "0",
                     "-aac_is", "0", "-aac_pns", "0", "-aac_tns", "0", "-f", container, str(baseline)])
    assert native_aac.extract_bytes(baseline.read_bytes(), SECRET) is None
    def decode(path):
        raw = native_aac._run([native_aac._tool("ffmpeg"), "-v", "error", "-i", str(path), "-c:a", "pcm_f32le", "-f", "wav", "-"])
        return sf.read(io.BytesIO(raw))[0]
    clean, changed = decode(baseline), decode(watermarked)
    assert clean.shape == changed.shape
    snr = 10 * np.log10(np.sum(clean ** 2) / np.sum((clean - changed) ** 2))
    assert snr > 25, f"AAC watermark SNR versus baseline: {snr:.2f} dB"
    assert np.max(np.abs(changed)) < 1
    remuxed = tmp_path / "remuxed.m4a"
    native_aac._run([native_aac._tool("ffmpeg"), "-v", "error", "-i", str(watermarked),
                     "-map_metadata", "-1", "-c:a", "copy", "-f", "ipod", str(remuxed)])
    assert native_aac.extract_bytes(remuxed.read_bytes(), SECRET) == ID
