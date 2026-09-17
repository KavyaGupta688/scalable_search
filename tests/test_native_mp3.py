import io

import numpy as np
import pytest
import soundfile as sf

from core import native_mp3, native_aac

SECRET = "native-mp3-development-secret-" * 3
ID = "35b63f71-74d5-45dc-bdd7-7b5a00d227e9"
pytestmark = pytest.mark.skipif(not (native_mp3.ROOT / "work/native/lame-3.100/frontend/lame").is_file(), reason="Native MP3 build required")


@pytest.mark.parametrize("channels", [1, 2])
def test_native_mp3(channels, tmp_path):
    rate = 44100
    t = np.arange(rate * 12) / rate
    x = 0.15 * np.sin(2 * np.pi * 440 * t) + 0.035 * np.random.default_rng(57).normal(size=len(t))
    if channels == 2:
        x = np.column_stack((x, x * 0.8))
    buffer = io.BytesIO()
    sf.write(buffer, x, rate, format="WAV", subtype="PCM_16")
    marked = native_mp3.embed_bytes(buffer.getvalue(), ID, SECRET)
    assert native_mp3.extract_bytes(marked, SECRET) == ID
    assert native_mp3.extract_bytes(marked, SECRET + "wrong") is None
    source = tmp_path / "source.wav"
    baseline = tmp_path / "baseline.mp3"
    marked_path = tmp_path / "marked.mp3"
    source.write_bytes(buffer.getvalue())
    marked_path.write_bytes(marked)
    lame = native_mp3.ROOT / "work/native/lame-3.100/frontend/lame"
    native_aac._run([str(lame), "--silent", "--noreplaygain", "-q", "2", "-b", "320", "-m", "m" if channels == 1 else "j", str(source), str(baseline)])
    assert native_mp3.extract_bytes(baseline.read_bytes(), SECRET) is None
    def decoded(path):
        raw = native_aac._run([native_aac._tool("ffmpeg"), "-v", "error", "-i", str(path), "-c:a", "pcm_f32le", "-f", "wav", "-"])
        return sf.read(io.BytesIO(raw))[0]
    clean, changed = decoded(baseline), decoded(marked_path)
    assert clean.shape == changed.shape
    snr = 10 * np.log10(np.sum(clean ** 2) / np.sum((clean - changed) ** 2))
    assert snr > 25, f"MP3 watermark SNR: {snr:.2f} dB"
    assert np.max(np.abs(changed)) < 1
