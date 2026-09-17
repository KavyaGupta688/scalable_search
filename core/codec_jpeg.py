"""Experimental authenticated watermark in JPEG quantized DCT coefficients.

No pixel decode/re-encode is used. Version 1 survives lossless metadata removal;
it does not promise recovery after recompression, cropping or resizing.
"""
import hmac
import struct
import tempfile
import uuid
from pathlib import Path

import jpeglib
import numpy as np
from PIL import Image

VERSION = b"\x01"
PAYLOAD_BYTES = 33  # version + UUID + 128-bit HMAC
REPETITIONS = 3
REQUIRED_BLOCKS = PAYLOAD_BYTES * 8 * REPETITIONS


def _validate(source):
    if Path(source).stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Native JPEG watermark limit is 64 MiB")
    with Image.open(source) as image:
        if image.format != "JPEG" or image.width * image.height > 16_000_000:
            raise ValueError("Expected JPEG with at most 16 million pixels")


def _key(secret):
    key = secret.encode() if isinstance(secret, str) else secret
    if len(key) < 32:
        raise ValueError("Codec watermark secret must contain at least 32 bytes")
    return key


def _payload(download_id, secret):
    body = VERSION + uuid.UUID(download_id).bytes
    tag = hmac.digest(_key(secret), b"jpeg-payload-v1:" + body, "sha256")[:16]
    return body + tag


def _locations(shape, secret):
    count = shape[0] * shape[1]
    if count < REQUIRED_BLOCKS:
        raise ValueError(f"JPEG needs at least {REQUIRED_BLOCKS} luminance blocks; got {count}")
    seed = hmac.digest(_key(secret), b"jpeg-locations-v1:" + struct.pack(">II", *shape[:2]), "sha256")
    # Affine permutation uses O(payload) memory, deterministic across NumPy versions.
    import math
    stride = int.from_bytes(seed[:8], "big") % count or 1
    while math.gcd(stride, count) != 1:
        stride += 1
    start = int.from_bytes(seed[8:16], "big") % count
    return [(start + i * stride) % count for i in range(REQUIRED_BLOCKS)]


def embed_file(source, destination, download_id, secret):
    """Modify one mid-frequency AC coefficient per selected luminance block."""
    if Path(source).resolve() == Path(destination).resolve():
        raise ValueError("Source and destination must differ")
    _validate(source)
    jpeg = jpeglib.read_dct(str(source))
    y = jpeg.Y
    if jpeg.num_components not in (1, 3):
        raise ValueError("Only grayscale and three-component JPEGs are supported")
    bits = np.tile(np.unpackbits(np.frombuffer(_payload(download_id, secret), dtype=np.uint8)), REPETITIONS)
    for block, bit in zip(_locations(y.shape, secret), bits):
        row, col = divmod(block, y.shape[1])
        value = int(y[row, col, 2, 3])
        # Two interleaved quantization lattices: spacing 4, centers 0 or 2.
        target = 2 * int(bit)
        y[row, col, 2, 3] = 4 * round((value - target) / 4) + target
    jpeg.write_dct(str(destination))


def extract_file(source, secret):
    """Return authenticated UUID or None; never attribute from unchecked bits."""
    _key(secret)
    _validate(source)
    jpeg = jpeglib.read_dct(str(source))
    y = jpeg.Y
    try:
        locations = _locations(y.shape, secret)
    except ValueError:
        return None
    bits = []
    for block in locations:
        row, col = divmod(block, y.shape[1])
        bits.append(round(int(y[row, col, 2, 3]) / 2) % 2)
    votes = np.asarray(bits).reshape(REPETITIONS, -1).sum(axis=0) >= 2
    payload = np.packbits(votes).tobytes()
    body, tag = payload[:17], payload[17:]
    expected = hmac.digest(_key(secret), b"jpeg-payload-v1:" + body, "sha256")[:16]
    if body[:1] != VERSION or not hmac.compare_digest(tag, expected):
        return None
    return str(uuid.UUID(bytes=body[1:]))


def embed_bytes(data, download_id, secret):
    with tempfile.TemporaryDirectory(prefix="jpeg-watermark-") as tmp:
        source, dest = Path(tmp) / "source.jpg", Path(tmp) / "marked.jpg"
        source.write_bytes(data)
        embed_file(source, dest, download_id, secret)
        if extract_file(dest, secret) != str(uuid.UUID(download_id)):
            raise ValueError("JPEG watermark failed its post-write recovery check")
        return dest.read_bytes()


def extract_bytes(data, secret):
    with tempfile.TemporaryDirectory(prefix="jpeg-inspect-") as tmp:
        source = Path(tmp) / "source.jpg"
        source.write_bytes(data)
        return extract_file(source, secret)
