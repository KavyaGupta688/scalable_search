# worker/pipeline/image_processor.py
"""
Layer 5 - Image Processor.

Loads an image, normalizes orientation using EXIF data, resizes for model
input, and extracts useful metadata. Pure Pillow - no torch/model
dependencies here, so this stays fast to iterate on standalone.
"""

from dataclasses import dataclass
from PIL import Image, ExifTags, ImageOps


# Most vision models (CLIP, BLIP, YOLO) expect a consistent input size.
# 224 is CLIP's native size; if a later model needs a different size,
# resize again at that model's boundary rather than changing this default.
DEFAULT_TARGET_SIZE = (224, 224)


@dataclass
class ProcessedImage:
    image: Image.Image          # the processed PIL image, ready for model input
    original_image: Image.Image # orientation-normalized full-resolution RGB image
    original_size: tuple[int, int]
    exif_metadata: dict
    was_rotated: bool


def process_image(file_path: str, target_size: tuple[int, int] = DEFAULT_TARGET_SIZE) -> ProcessedImage:
    with Image.open(file_path) as source:
        original_size = source.size
        exif_metadata = _extract_exif(source)
        orientation = source.getexif().get(274, 1)
        original_image = ImageOps.exif_transpose(source).convert("RGB")

    # Phone/camera photos often store orientation as an EXIF flag instead
    # of physically rotating pixels. Without this, a portrait photo can
    # load sideways into every downstream model.
    was_rotated = orientation not in (None, 1)

    # Resize with aspect-preserving thumbnail + pad, rather than a hard
    # stretch - avoids distorting object proportions before detection/
    # tagging models ever see the image.
    img = _resize_with_padding(original_image, target_size)

    return ProcessedImage(
        image=img,
        original_image=original_image,
        original_size=original_size,
        exif_metadata=exif_metadata,
        was_rotated=was_rotated,
    )


def _extract_exif(img: Image.Image) -> dict:
    raw_exif = img.getexif()
    if not raw_exif:
        return {}

    readable = {}
    for tag_id, value in raw_exif.items():
        tag_name = ExifTags.TAGS.get(tag_id, tag_id)
        # Some EXIF values are bytes and not JSON-serializable later when
        # this dict eventually lands in a Postgres JSON column - stringify
        # anything that isn't a plain str/int/float.
        if isinstance(value, (bytes, tuple)):
            value = str(value)
        readable[str(tag_name)] = value
    return readable


def _resize_with_padding(img: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    img = img.copy()
    img.thumbnail(target_size, Image.LANCZOS)

    padded = Image.new("RGB", target_size, (0, 0, 0))
    offset = ((target_size[0] - img.width) // 2, (target_size[1] - img.height) // 2)
    padded.paste(img, offset)
    return padded


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "sample.jpg"
    result = process_image(path)

    print(f"Original size: {result.original_size}")
    print(f"Processed size: {result.image.size}")
    print(f"Was rotated: {result.was_rotated}")
    print(f"EXIF keys found: {list(result.exif_metadata.keys())}")

    result.image.save("processed_output.jpg")
    print("Saved processed_output.jpg for visual check")
