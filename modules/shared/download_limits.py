"""Download limits, shared by Search (which plans a download) and Download (which enforces it).

Both services read the same environment variables, so the size estimate a user sees before
starting a download always matches what the download service will accept.
"""

import os

MiB = 1024**2
GiB = 1024**3


def _int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, default))
    except ValueError:
        return default
    return value if value > 0 else default


# A single file above this is never packaged. Selections leave such files out.
MAX_FILE_BYTES = _int("DOWNLOAD_MAX_FILE_BYTES", 128 * MiB)
# Size of one archive part. A larger selection is split into several parts of this size.
PART_BYTES = _int("DOWNLOAD_MAX_BATCH_BYTES", 2 * GiB)
# Whole-request ceilings apply to original source bytes. Watermark and ZIP overhead can
# change delivered archive sizes; each finished part reports its exact compressed size.
MAX_FILES = _int("DOWNLOAD_MAX_FILES", 10_000)
MAX_TOTAL_BYTES = _int("DOWNLOAD_MAX_TOTAL_BYTES", 20 * GiB)


def limits() -> dict:
    """The limits as reported to clients."""
    return {
        "max_file_bytes": MAX_FILE_BYTES,
        "part_bytes": PART_BYTES,
        "max_files": MAX_FILES,
        "max_total_bytes": MAX_TOTAL_BYTES,
    }
