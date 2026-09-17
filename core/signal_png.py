"""Experimental PNG watermark: Haar DWT followed by block DCT on luminance.

Version 1 supports metadata removal, not crop/resize synchronization.
"""
import io

import numpy as np
import pywt
from PIL import Image
from scipy.fft import dctn, idctn

from core.signal_payload import BIT_COUNT, COPIES, encode, decode, positions

DOMAIN = "png-dwt-dct-v1"
STEP = 32.0


def _read(data):
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("PNG signal limit is 64 MiB")
    with Image.open(io.BytesIO(data)) as image:
        if image.format != "PNG" or image.width * image.height > 16_000_000:
            raise ValueError("Expected PNG with at most 16 million pixels")
        if getattr(image, "n_frames", 1) != 1:
            raise ValueError("Animated PNG is not supported for signal watermarking")
        if image.mode not in ("L", "LA", "RGB", "RGBA"):
            raise ValueError("PNG signal watermark requires 8-bit L, LA, RGB or RGBA pixels")
        pixels = np.asarray(image).copy()
        return pixels, image.mode, {k: image.info[k] for k in ("icc_profile", "exif", "dpi") if k in image.info}


def _luminance(pixels, mode):
    if mode in ("L", "LA"):
        return pixels.astype(float) if mode == "L" else pixels[:, :, 0].astype(float)
    return np.sum(pixels[:, :, :3].astype(float) * np.array([0.299, 0.587, 0.114]), axis=2)


def _blocks(y):
    low, detail = pywt.dwt2(y, "haar", mode="symmetric")
    rows, cols = low.shape[0] // 8, low.shape[1] // 8
    blocks = low[:rows * 8, :cols * 8].reshape(rows, 8, cols, 8).transpose(0, 2, 1, 3)
    return low, detail, dctn(blocks, axes=(-2, -1), norm="ortho")


def embed_bytes(data, download_id, secret):
    pixels, mode, info = _read(data)
    y = _luminance(pixels, mode)
    low, detail, coeff = _blocks(y)
    rows, cols = coeff.shape[:2]
    bits = np.tile(encode(download_id, secret, DOMAIN), COPIES)
    for index, bit in zip(positions(rows * cols, len(bits), secret, DOMAIN), bits):
        r, c = divmod(index, cols)
        value = coeff[r, c, 2, 3]
        target = float(bit) * STEP / 2
        coeff[r, c, 2, 3] = STEP * np.round((value - target) / STEP) + target
    low[:rows * 8, :cols * 8] = idctn(coeff, axes=(-2, -1), norm="ortho").transpose(0, 2, 1, 3).reshape(rows * 8, cols * 8)
    marked_y = pywt.idwt2((low, detail), "haar", mode="symmetric")[:y.shape[0], :y.shape[1]]
    delta = marked_y - y
    output = pixels.copy()
    if mode == "L":
        output = np.clip(np.round(pixels.astype(float) + delta), 0, 255).astype(np.uint8)
    elif mode == "LA":
        output[:, :, 0] = np.clip(np.round(pixels[:, :, 0].astype(float) + delta), 0, 255).astype(np.uint8)
    else:
        output[:, :, :3] = np.clip(np.round(pixels[:, :, :3].astype(float) + delta[:, :, None]), 0, 255).astype(np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(output).save(buffer, format="PNG", **info)
    result = buffer.getvalue()
    if extract_bytes(result, secret) != download_id.lower():
        raise ValueError("PNG watermark did not survive pixel rounding/clipping; no output delivered")
    return result


def extract_bytes(data, secret):
    pixels, mode, _ = _read(data)
    _, _, coeff = _blocks(_luminance(pixels, mode))
    rows, cols = coeff.shape[:2]
    if rows * cols < BIT_COUNT * COPIES:
        return None
    bits = []
    for index in positions(rows * cols, BIT_COUNT * COPIES, secret, DOMAIN):
        r, c = divmod(index, cols)
        bits.append(int(np.round(coeff[r, c, 2, 3] / (STEP / 2))) % 2)
    votes = np.asarray(bits).reshape(COPIES, BIT_COUNT).sum(axis=0)
    return decode(votes >= 2, secret, DOMAIN)
