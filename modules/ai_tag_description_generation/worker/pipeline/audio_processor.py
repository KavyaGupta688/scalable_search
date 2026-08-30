# worker/pipeline/audio_processor.py
"""
Layer 5 - Audio Processor.

Normalizes audio to 16kHz mono (Whisper's expected input format), checks
for silence/near-empty audio before it ever reaches an expensive STT call,
and extracts basic metadata.
"""

from dataclasses import dataclass

import librosa
import numpy as np


TARGET_SAMPLE_RATE = 16000  # Whisper's required input sample rate

# Below this RMS energy, treat audio as effectively silent - matters
# because the doc explicitly calls out "empty/noisy audio" as a
# data-quality failure to flag, not an infrastructure error.
SILENCE_RMS_THRESHOLD = 0.01


@dataclass
class ProcessedAudio:
    waveform: np.ndarray        # normalized float32 array, 16kHz mono - ready for Whisper
    duration_seconds: float
    original_sample_rate: int
    is_likely_silent: bool
    rms_energy: float


def process_audio(file_path: str) -> ProcessedAudio:
    # librosa.load handles resampling and mono conversion in one call -
    # sr=TARGET_SAMPLE_RATE forces the resample, mono=True averages channels.
    waveform, original_sr = librosa.load(file_path, sr=TARGET_SAMPLE_RATE, mono=True)

    duration_seconds = len(waveform) / TARGET_SAMPLE_RATE
    rms_energy = float(np.sqrt(np.mean(waveform ** 2)))
    is_likely_silent = rms_energy < SILENCE_RMS_THRESHOLD

    # Peak-normalize volume so quiet recordings don't get worse STT
    # accuracy purely due to low volume - skip if silent, nothing to normalize.
    if not is_likely_silent:
        peak = np.max(np.abs(waveform))
        if peak > 0:
            waveform = waveform / peak * 0.95  # leave a little headroom, avoid clipping

    return ProcessedAudio(
        waveform=waveform,
        duration_seconds=duration_seconds,
        original_sample_rate=original_sr,
        is_likely_silent=is_likely_silent,
        rms_energy=rms_energy,
    )


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "sample.wav"
    result = process_audio(path)

    print(f"Duration: {result.duration_seconds:.1f}s")
    print(f"Original sample rate: {result.original_sample_rate}Hz -> resampled to {TARGET_SAMPLE_RATE}Hz")
    print(f"RMS energy: {result.rms_energy:.4f}")
    print(f"Likely silent: {result.is_likely_silent}")
    print(f"Waveform shape: {result.waveform.shape}")