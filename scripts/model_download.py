"""Atomic, resumable large-weight downloads with optional checksum verification."""
import hashlib
from pathlib import Path
import time
import urllib.request

from filelock import FileLock


def download(url: str, target: Path, expected_sha256: str | None = None):
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".partial")

    def valid(path):
        if not path.is_file():
            return False
        if not expected_sha256:
            return True
        with path.open("rb") as file:
            return hashlib.file_digest(file, "sha256").hexdigest().startswith(expected_sha256)

    with FileLock(str(target) + ".lock"):
        if valid(target):
            return str(target)
        # Adopt a partial file left by a library's non-atomic downloader.
        if target.is_file() and not partial.exists():
            target.replace(partial)
        legacy_partial = target.with_suffix(".partial")
        if not partial.exists() and legacy_partial.is_file():
            legacy_partial.replace(partial)
        if expected_sha256 and valid(partial):
            partial.replace(target)
            return str(target)
        for attempt in range(3):
            try:
                offset = partial.stat().st_size if partial.exists() else 0
                request = urllib.request.Request(url, headers={"Range":f"bytes={offset}-"} if offset else {})
                with urllib.request.urlopen(request, timeout=60) as response:
                    resumed = response.status == 206
                    if resumed and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                        raise ValueError("Server returned the wrong byte range")
                    with partial.open("ab" if resumed else "wb") as file:
                        while chunk := response.read(1024 * 1024):
                            file.write(chunk)
                if not valid(partial):
                    partial.replace(partial.with_suffix(".invalid"))
                    raise ValueError("Downloaded checkpoint checksum mismatch")
                partial.replace(target)
                return str(target)
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
