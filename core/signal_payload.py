"""Authenticated, repeated signal payloads. No downloader PII is embedded."""
import hmac
import uuid

import numpy as np

BODY_PREFIX = b"\xd3\x91\x01"
BYTE_COUNT = 35
BIT_COUNT = BYTE_COUNT * 8
COPIES = 3


def key_bytes(secret):
    key = secret.encode() if isinstance(secret, str) else secret
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("Signal watermark secret must be at least 32 bytes")
    return key


def encode(download_id, secret, domain):
    body = BODY_PREFIX + uuid.UUID(download_id).bytes
    mac = hmac.digest(key_bytes(secret), domain.encode() + b":" + body, "sha256")[:16]
    return np.unpackbits(np.frombuffer(body + mac, dtype=np.uint8))


def decode(bits, secret, domain):
    if len(bits) != BIT_COUNT:
        return None
    payload = np.packbits(np.asarray(bits, dtype=np.uint8)).tobytes()
    body, mac = payload[:-16], payload[-16:]
    expected = hmac.digest(key_bytes(secret), domain.encode() + b":" + body, "sha256")[:16]
    if not body.startswith(BODY_PREFIX) or not hmac.compare_digest(mac, expected):
        return None
    return str(uuid.UUID(bytes=body[3:]))


def positions(count, needed, secret, domain):
    """Keyed sample without replacement; O(needed) memory, stable ordering."""
    if count < needed:
        raise ValueError(f"Insufficient watermark capacity: need {needed}, have {count}")
    key = key_bytes(secret)
    swaps = {}
    result = []
    for i in range(needed):
        digest = hmac.digest(key, domain.encode() + b":" + count.to_bytes(8, "big") + i.to_bytes(8, "big"), "sha256")
        j = i + int.from_bytes(digest, "big") % (count - i)
        result.append(swaps.get(j, j))
        swaps[j] = swaps.get(i, i)
    return result
