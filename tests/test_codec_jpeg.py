import uuid
import jpeglib
import numpy as np
import pytest
from PIL import Image
from core.codec_jpeg import embed_file, extract_file, _locations, REQUIRED_BLOCKS

SECRET = "test-only-secret-" * 4
ID = str(uuid.UUID("0474e846-dfa2-43ce-8e0e-18a79f5b2831"))


@pytest.mark.parametrize("mode,progressive", [("RGB", False), ("RGB", True), ("L", False)])
def test_recovery_coefficients_and_quality(tmp_path, mode, progressive):
    rng = np.random.default_rng(71)
    shape = (320, 320, 3) if mode == "RGB" else (320, 320)
    original, marked = tmp_path / "original.jpg", tmp_path / "marked.jpg"
    Image.fromarray(rng.integers(0, 256, shape, dtype=np.uint8)).save(original, quality=90, progressive=progressive)
    embed_file(original, marked, ID, SECRET)
    assert extract_file(marked, SECRET) == ID
    assert extract_file(marked, "different-private-secret-" * 3) is None
    assert extract_file(original, SECRET) is None
    before, after = jpeglib.read_dct(str(original)), jpeglib.read_dct(str(marked))
    np.testing.assert_array_equal(before.qt, after.qt)
    np.testing.assert_array_equal(before.Y[:, :, 0, 0], after.Y[:, :, 0, 0])
    mask = np.ones((8, 8), dtype=bool)
    mask[2, 3] = False
    np.testing.assert_array_equal(before.Y[:, :, mask], after.Y[:, :, mask])
    if mode == "RGB":
        np.testing.assert_array_equal(before.Cb, after.Cb)
        np.testing.assert_array_equal(before.Cr, after.Cr)
    a, b = np.asarray(Image.open(original), dtype=float), np.asarray(Image.open(marked), dtype=float)
    psnr = 10 * np.log10(255 ** 2 / np.mean((a - b) ** 2))
    assert psnr > 35


def test_repetition_recovers_one_damaged_copy(tmp_path):
    source, marked, damaged = [tmp_path / p for p in ("source.jpg", "marked.jpg", "damaged.jpg")]
    Image.new("RGB", (320, 320), (110, 130, 160)).save(source)
    embed_file(source, marked, ID, SECRET)
    jpeg = jpeglib.read_dct(str(marked))
    for index in _locations(jpeg.Y.shape, SECRET)[:REQUIRED_BLOCKS // 3]:
        row, col = divmod(index, jpeg.Y.shape[1])
        jpeg.Y[row, col, 2, 3] += 2
    jpeg.write_dct(str(damaged))
    assert extract_file(damaged, SECRET) == ID


def test_small_image_rejected(tmp_path):
    source = tmp_path / "small.jpg"
    Image.new("RGB", (64, 64)).save(source)
    with pytest.raises(ValueError, match="blocks"):
        embed_file(source, tmp_path / "marked.jpg", ID, SECRET)
