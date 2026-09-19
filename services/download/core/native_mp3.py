"""Experimental LAME native hybrid-MDCT embedding and FFmpeg spectral extraction."""
from pathlib import Path
import tempfile

from core.native_aac import ROOT, _tool, _run, _probe, _configuration, _environment, _recover, _check_audio_output

DOMAIN = "mp3-native-mdct-v1"


def embed_bytes(data, download_id, secret):
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("Native MP3 input limit is 64 MiB")
    lame = ROOT / "work/native/lame-3.100/frontend/lame"
    if not lame.is_file():
        raise RuntimeError("Native MP3 backend not built; run scripts/build_native_mp3.py")
    with tempfile.TemporaryDirectory(prefix="native-mp3-") as directory:
        tmp = Path(directory)
        source, wav, output, config = (tmp / p for p in ("input.bin", "input.wav", "output.mp3", "embed.cfg"))
        source.write_bytes(data)
        rate, channels = _probe(source, allow_mp3=True)
        _run([_tool("ffmpeg"), "-v", "error", "-i", str(source), "-map", "0:a:0", "-map_metadata", "-1",
              "-c:a", "pcm_s16le", "-f", "wav", str(wav)])
        _configuration(config, rate, secret, download_id, DOMAIN, 576)
        _run([str(lame), "--silent", "--noreplaygain", "-q", "2", "-b", "320", "-m", "m" if channels == 1 else "j",
              str(wav), str(output)], env=_environment(config, embed=True, kind="MP3"))
        if _recover(output, tmp, rate, secret, DOMAIN, 576, "MP3", step=0.72) != download_id.lower():
            raise ValueError("Native MP3 watermark did not survive quantization; no output delivered")
        _check_audio_output(output)
        return output.read_bytes()


def extract_bytes(data, secret):
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("Native MP3 input limit is 64 MiB")
    with tempfile.TemporaryDirectory(prefix="native-mp3-extract-") as directory:
        tmp = Path(directory)
        source = tmp / "input.mp3"
        source.write_bytes(data)
        rate, _ = _probe(source, allow_mp3=True)
        return _recover(source, tmp, rate, secret, DOMAIN, 576, "MP3", step=0.72)
