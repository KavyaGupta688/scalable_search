"""Experimental lossless-audio STFT watermark with authenticated recovery.

Uses nonoverlapping rectangular STFT windows and keyed spectral-group ratio
quantization. It is not a codec-level MP3/AAC MDCT implementation. Timing and
sample rate must be preserved. Quiet/insufficient carriers fail closed.
"""
import io

import numpy as np
import soundfile as sf
from scipy.fft import rfft, irfft

from core.signal_payload import BIT_COUNT, COPIES, encode, decode, positions

DOMAIN = "audio-stft-v1"
WINDOW = 2048
LANES = 8
STEP = 0.12
MIN_FRAMES = BIT_COUNT * COPIES // LANES


def _read(data):
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("Audio signal limit is 64 MiB")
    with sf.SoundFile(io.BytesIO(data)) as audio:
        if audio.format not in ("WAV", "FLAC") or audio.subtype not in ("PCM_16", "PCM_24", "PCM_32", "FLOAT", "DOUBLE"):
            raise ValueError("STFT backend supports WAV/FLAC PCM16/24/32 or floating-point WAV")
        if not 16000 <= audio.samplerate <= 96000 or audio.channels not in (1, 2):
            raise ValueError("STFT backend requires mono/stereo audio at 16–96 kHz")
        if audio.frames * audio.channels > 10_000_000:
            raise ValueError("Audio signal limit is 10 million channel samples")
        samples = audio.read(dtype="float64", always_2d=True)
        if not np.all(np.isfinite(samples)):
            raise ValueError("Audio contains non-finite samples")
        return samples, audio.samplerate, audio.format, audio.subtype


def _groups(rate, secret):
    lower = max(1, int(700 * WINDOW / rate))
    upper = min(WINDOW // 2 - 1, int(6000 * WINDOW / rate))
    selected = np.asarray(positions(upper - lower, LANES * 8, secret, DOMAIN + "-bins")) + lower
    return selected.reshape(LANES, 2, 4)


def _spectra(samples):
    frames = len(samples) // WINDOW
    # Rectangular STFT, hop == window. Trailing samples are preserved unchanged.
    return rfft(samples[:frames * WINDOW].reshape(frames, WINDOW, samples.shape[1]), axis=1)


def embed_bytes(data, download_id, secret):
    samples, rate, fmt, subtype = _read(data)
    spectrum = _spectra(samples)
    if len(spectrum) < MIN_FRAMES:
        raise ValueError(f"STFT watermark needs at least {MIN_FRAMES * WINDOW / rate:.2f} seconds at this sample rate")
    bits = encode(download_id, secret, DOMAIN)
    groups = _groups(rate, secret)
    # Apply the same multiplicative factors to both channels, preserving phase.
    # Ratios are measured from the mono mix so stereo-to-mono can be tested.
    for frame in range(len(spectrum)):
        mono = spectrum[frame].mean(axis=1)
        for lane, (a, b) in enumerate(groups):
            ea, eb = np.linalg.norm(mono[a]), np.linalg.norm(mono[b])
            if min(ea, eb) < 0.01:
                continue
            ratio = np.log(ea / eb)
            target = bits[(frame * LANES + lane) % BIT_COUNT] * STEP / 2
            desired = STEP * np.round((ratio - target) / STEP) + target
            gain = np.exp((desired - ratio) / 2)
            spectrum[frame, a, :] *= gain
            spectrum[frame, b, :] /= gain
    marked = samples.copy()
    marked[:len(spectrum) * WINDOW] = irfft(spectrum, n=WINDOW, axis=1).reshape(-1, samples.shape[1])
    if np.max(np.abs(marked)) >= 1.0:
        raise ValueError("Watermark would clip audio; input requires headroom")
    buffer = io.BytesIO()
    sf.write(buffer, marked, rate, format=fmt, subtype=subtype)
    result = buffer.getvalue()
    if extract_bytes(result, secret) != download_id.lower():
        raise ValueError("Insufficient usable audio carrier: authenticated post-write recovery failed")
    return result


def extract_bytes(data, secret):
    samples, rate, _, _ = _read(data)
    spectrum = _spectra(samples)
    if len(spectrum) < MIN_FRAMES:
        return None
    groups = _groups(rate, secret)
    votes, totals = np.zeros(BIT_COUNT), np.zeros(BIT_COUNT)
    for frame in range(len(spectrum)):
        mono = spectrum[frame].mean(axis=1)
        for lane, (a, b) in enumerate(groups):
            ea, eb = np.linalg.norm(mono[a]), np.linalg.norm(mono[b])
            if min(ea, eb) < 0.01:
                continue
            bit = int(np.round(np.log(ea / eb) / (STEP / 2))) % 2
            index = (frame * LANES + lane) % BIT_COUNT
            votes[index] += bit
            totals[index] += 1
    if np.any(totals < 2) or np.any(votes * 2 == totals):
        return None
    return decode(votes * 2 > totals, secret, DOMAIN)
