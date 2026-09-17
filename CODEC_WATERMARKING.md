# Experimental signal and native codec watermarks

Every signal backend embeds a download UUID authenticated with a domain-separated
HMAC. Full user details stay in the audit database. Extraction authenticates the
recovered ID before looking up its record. Conflicting metadata IDs are reported.

| Media | Implemented method | Current scope |
| --- | --- | --- |
| JPEG | Quantized DCT editing through jpeglib | Grayscale/color/progressive; 792 luminance blocks minimum |
| PNG | Haar DWT, block DCT and coefficient QIM | Single-frame 8-bit L/LA/RGB/RGBA; 840 low-band blocks minimum; alpha preserved |
| WAV/FLAC | STFT spectral-group ratio QIM | Mono/stereo, 16–96 kHz, supported PCM/float subtypes |
| MP3 | LAME hybrid MDCT hook before quantization | MPEG-1 at 44.1/48 kHz, mono/stereo, output 320 kbps |
| AAC/M4A | FFmpeg AAC-LC MDCT hook before quantization | 44.1/48 kHz, mono/stereo, output 192 kbps per channel |
| H.264 | x264 quantized luma AC editing before reconstruction | All-intra I16x16, CABAC, QP18, 8-bit YUV420 |
| H.265 | x265 quantized luma transform editing before reconstruction | All-intra, CTU16, QP18, RDOQ/sign hiding disabled, 8-bit YUV420 |

Native MP3/AAC extraction runs inside the matching FFmpeg decoder before inverse
MDCT. Video extraction reads quantized coefficients before inverse transform.
These paths do not substitute PCM/STFT or pixel-domain watermarking for native
codec access. PNG and lossless-audio methods intentionally operate on decoded
data because their storage codecs have no DCT/MDCT stage.

## Installation and local build

Use Python 3.12 or newer (validation used Python 3.13). From the project directory:

    python3 -m venv .venv
    .venv/bin/pip install -r requirements-native-build.txt
    .venv/bin/python scripts/build_native_aac.py
    .venv/bin/python scripts/build_native_mp3.py
    .venv/bin/python scripts/build_native_video.py h264
    .venv/bin/python scripts/build_native_video.py h265
    .venv/bin/python -m pytest tests -q

The AAC builder builds the shared FFmpeg decoders and AAC encoder. Other scripts
build LAME, x264 and x265. Builds live in ignored work/native/ and do not replace
system binaries. FFmpeg 7.1 and LAME 3.100 tarballs are checked against pinned
SHA256 hashes. x264/x265 commits are pinned in the video builder. Source patches
fail when the expected upstream layout does not match. Upstream license notices
remain in the downloaded sources. These experimental builds need an update and
security-maintenance process before deployment.

On the development Mac, the default SDK and linker were incompatible. Appending
this argument to each build command resolved it without changing system settings:

    --sysroot /Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk

Use an installed SDK appropriate to your machine. Native tests skip absent builds;
skips are not evidence that a codec works. imageio-ffmpeg supplies unmodified
reference codecs for compatibility tests, not watermark embedding.

## Enable the gateway

All signal modes are opt-in. Configure .env with a private random key of at least
32 bytes and enable the modes you want:

    CODEC_WATERMARK_SECRET=<private random key>
    JPEG_CODEC_WATERMARK=true
    LOSSLESS_SIGNAL_WATERMARK=true
    NATIVE_AUDIO_WATERMARK=true
    NATIVE_VIDEO_WATERMARK=true

Keep the key stable: extraction needs the same key. Committed test keys are
development fixtures only. Tests do not generate or store a production key.
Also set a private WATERMARK_SECRET_KEY for the older metadata token.

Single downloads, direct ZIPs and Celery packages share the dispatcher. Signal
processing finishes and authenticates saved output before delivery. Failure,
insufficient capacity or unsupported profiles result in errors rather than silent
metadata-only fallback for a requested signal backend. JPEG/PNG/WAV/FLAC/MP3 also
receive metadata tokens. AAC and native video carry the authenticated signal ID
without inserting invalid ad-hoc container headers. Video audio packets are copied
unchanged; the video backend does not separately watermark them.

The forensic API and CLI inspect signal watermarks even when embedding is off,
provided the key and dependencies are available. Signatures and stream probing
handle renamed files.

    .venv/bin/python cli/signal_watermark.py embed input.png --output marked.png --download-id YOUR-UUID
    .venv/bin/python cli/signal_watermark.py embed input.mp3 --native mp3 --output marked.mp3 --download-id YOUR-UUID
    .venv/bin/python cli/signal_watermark.py embed input.aac --native aac --output marked.aac --download-id YOUR-UUID
    .venv/bin/python cli/signal_watermark.py embed input.m4a --native m4a --output marked.m4a --download-id YOUR-UUID
    .venv/bin/python cli/signal_watermark.py embed input.mp4 --native video --output marked.mp4 --download-id YOUR-UUID
    .venv/bin/python cli/signal_watermark.py extract marked.mp4
    .venv/bin/python cli/forensic_verify.py marked.mp4

The standalone signal tool uses .env/process configuration and requires no S3,
Redis or database. It refuses to overwrite output files.

## Limits and evidence

Signal inputs and forensic uploads are capped at 64 MiB. JPEG/PNG are capped at
16 million pixels. PNG rejects palette, 16-bit and animated images. STFT input
is capped at 10 million channel samples and needs at least 215,040 samples with
enough spectral energy. Silence or unsuitable stereo cancellation fails recovery.
Native audio is limited to 120 seconds and rejects clipped/non-finite output.
Native video is limited to 1920x1080 pixels, 12 seconds and constant frame rate up to
30 fps, in MP4/MOV/MKV. All-intra output can substantially increase file size.
Processing uses temporary files and full coefficient/sample arrays; it is not
constant-memory or a validated multi-terabyte pipeline.

Tests exercise metadata stripping, renamed-file extraction, wrong-key/unmarked
rejection, synthetic coefficient damage, alpha preservation, saved-file recovery,
gateway downloads and Celery processing. Native video is decoded by unmodified
FFmpeg; frame counts and unchanged audio packet hashes are checked. Lossless audio
tests cover WAV/FLAC conversion and moderate volume reduction. Native audio is
compared with otherwise identical unmarked encodes. Native tests require builds.

Synthetic quality thresholds are JPEG PSNR >35 dB, PNG >40 dB, STFT SNR >35 dB,
native audio SNR >25 dB, and video PSNR >30 dB. These are regression checks, not
guarantees of imperceptibility or training neutrality. Real speech, music, medical
imagery, varied videos and downstream training still need evaluation. AAC uses
stronger embedding than the lossless-audio method.

Repetition and authenticated synchronization provide limited recovery. There is
no promise of survival after arbitrary resizing, cropping, resampling, transcoding,
denoising or deliberate removal. The HMAC authenticates an identifier, not the
whole media content. Tokens can be copied; the system does not prove who leaked
a file. Client-supplied user identity remains a separate trust limitation, and
production authentication/authorization remain necessary work.

References: [jpeglib](https://jpeglib.readthedocs.io/en/latest/usage.html),
[PyWavelets](https://pywavelets.readthedocs.io/en/latest/ref/2d-dwt-and-idwt.html),
[SciPy STFT](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.stft.html).
