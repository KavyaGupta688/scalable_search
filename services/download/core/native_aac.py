"""Experimental AAC-LC watermark inside a patched native encoder's MDCT path.

Extraction reads dequantized spectral values inside the paired native decoder,
before inverse MDCT. No PCM/STFT fallback. This backend requires an explicit build.
"""
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import io

import numpy as np

from core.signal_payload import BIT_COUNT, encode, decode, positions, key_bytes

ROOT = Path(__file__).resolve().parent.parent
DOMAIN = "aac-native-mdct-v1"
STEP = 0.96


def _tool(name):
    path = ROOT / "work/native/ffmpeg-7.1" / name
    if not path.is_file():
        raise RuntimeError("Native AAC backend is not built; run scripts/build_native_aac.py")
    return str(path)


def _run(args, env=None):
    try:
        result = subprocess.run(args, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=120)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Native media processing exceeded 120 seconds") from exc
    if result.returncode:
        raise ValueError("Native media processing failed: " + result.stderr.decode(errors="replace")[-800:])
    return result.stdout


def _probe(source, allow_mp3=False):
    raw = _run([_tool("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)])
    info = json.loads(raw)
    streams = info.get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_type") != "audio":
        raise ValueError("Native AAC requires exactly one audio stream and no other streams")
    stream = streams[0]
    allowed = ("aac", "pcm_s16le", "pcm_s24le", "pcm_f32le") + (("mp3",) if allow_mp3 else ())
    if stream.get("codec_name") not in allowed:
        raise ValueError("Native AAC accepts AAC-LC or WAV PCM input")
    if stream.get("codec_name") == "aac" and stream.get("profile") != "LC":
        raise ValueError("Only AAC-LC is supported; HE-AAC and other profiles are not enabled")
    rate, channels = int(stream["sample_rate"]), int(stream["channels"])
    if rate not in (44100, 48000) or channels not in (1, 2):
        raise ValueError("Native AAC v1 requires mono/stereo at 44.1 or 48 kHz")
    duration = float(info.get("format", {}).get("duration", 0))
    if not 0 < duration <= 120:
        raise ValueError("Native AAC input must have a known duration of at most 120 seconds")
    return rate, channels


def _configuration(path, rate, secret, download_id=None, domain=DOMAIN, lines=1024):
    key_bytes(secret)
    bits = encode(download_id, secret, domain) if download_id else np.zeros(BIT_COUNT, dtype=np.uint8)
    lower, upper = int(700 * lines * 2 / rate), int(6000 * lines * 2 / rate)
    bins = [lower + i for i in positions(upper-lower, 64, secret, domain + "-bins")]
    path.write_bytes(b"AWM1" + bytes(bits) + struct.pack("<64H", *bins))


def _environment(config, extract=None, embed=False, kind="AAC"):
    env = dict(os.environ)
    for prefix in ("AAC", "MP3"):
        for name in ("CONFIG", "EMBED", "EXTRACT"):
            env.pop(f"AGY_{prefix}_{name}", None)
    env[f"AGY_{kind}_CONFIG"] = str(config)
    if embed:
        env[f"AGY_{kind}_EMBED"] = "1"
    if extract:
        env[f"AGY_{kind}_EXTRACT"] = str(extract)
    return env


def _recover(source, tmp, rate, secret, domain=DOMAIN, lines=1024, kind="AAC", step=STEP):
    config, report = tmp / "extract.cfg", tmp / "coefficients.txt"
    _configuration(config, rate, secret, domain=domain, lines=lines)
    decoder = ["-c:a", "mp3float"] if kind == "MP3" else []
    _run([_tool("ffmpeg"), "-v", "error", "-threads", "1"] + decoder + ["-i", str(source), "-map", "0:a:0",
          "-f", "null", "-"], env=_environment(config, extract=report, kind=kind))
    if not report.exists():
        raise RuntimeError("Native decoder emitted no coefficient report; check the patched build")
    rows = []
    for line in report.read_text().splitlines():
        fields = line.split()
        if len(fields) == 9:
            rows.append((int(fields[0]), np.asarray([float(v) for v in fields[1:]])))
    # AAC priming / container edits may shift complete frames. Scan one packet
    # period; accept a candidate only after verifying its 128-bit MAC.
    for offset in range(BIT_COUNT // 8):
        votes, counts = np.zeros(BIT_COUNT), np.zeros(BIT_COUNT)
        for frame, ratios in rows:
            for lane, ratio in enumerate(ratios):
                if not np.isfinite(ratio):
                    continue
                index = ((frame + offset) * 8 + lane) % BIT_COUNT
                votes[index] += int(np.round(ratio / (step / 2))) % 2
                counts[index] += 1
        if np.any(counts < 3) or np.any(votes * 2 == counts):
            continue
        recovered = decode(votes * 2 > counts, secret, domain)
        if recovered:
            return recovered
    return None


def _check_audio_output(source):
    """Reject invalid/clipped output instead of silently delivering it."""
    import soundfile as sf
    raw = _run([_tool("ffmpeg"), "-v", "error", "-i", str(source), "-t", "121", "-map", "0:a:0",
                "-c:a", "pcm_f32le", "-f", "wav", "-"])
    samples, rate = sf.read(io.BytesIO(raw), dtype="float32", always_2d=True)
    if len(samples) > 120 * rate:
        raise ValueError("Native audio output exceeds the 120-second limit")
    if not samples.size or not np.all(np.isfinite(samples)) or np.max(np.abs(samples)) >= 1:
        raise ValueError("Native audio output is empty, invalid or clips; no output delivered")


def embed_bytes(data, download_id, secret, container="adts"):
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("Native AAC input limit is 64 MiB")
    if container not in ("adts", "ipod"):
        raise ValueError("Native AAC output must be ADTS or M4A")
    with tempfile.TemporaryDirectory(prefix="native-aac-") as directory:
        tmp = Path(directory)
        source, output, cfg = tmp / "input.bin", tmp / "output.bin", tmp / "embed.cfg"
        source.write_bytes(data)
        rate, channels = _probe(source)
        _configuration(cfg, rate, secret, download_id)
        _run([_tool("ffmpeg"), "-v", "error", "-threads", "1", "-i", str(source), "-map", "0:a:0",
              "-c:a", "aac", "-profile:a", "aac_low", "-b:a", str(192000 * channels),
              "-aac_ms", "0", "-aac_is", "0", "-aac_pns", "0", "-aac_tns", "0",
              "-map_metadata", "-1", "-f", container, str(output)], env=_environment(cfg, embed=True))
        if _recover(output, tmp, rate, secret) != download_id.lower():
            raise ValueError("Native AAC watermark did not survive codec quantization; no output delivered")
        _check_audio_output(output)
        return output.read_bytes()


def extract_bytes(data, secret):
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("Native AAC input limit is 64 MiB")
    with tempfile.TemporaryDirectory(prefix="native-aac-extract-") as directory:
        tmp = Path(directory)
        source = tmp / "input.bin"
        source.write_bytes(data)
        rate, _ = _probe(source)
        return _recover(source, tmp, rate, secret)
