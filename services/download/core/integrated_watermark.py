"""Format-safe integrated policy; never append arbitrary bytes to training data."""
import io
from pathlib import Path
from core.injectors import dispatcher


def methods_for(name):
    ext = Path(name).suffix.lower()
    signal = dispatcher.signal_method(name)
    signal_only = signal and ext in {".bmp", ".tif", ".tiff", ".webp", ".aac", ".m4a", ".mp4", ".mov", ".m4v", ".mkv"}
    if signal_only:
        return [signal]
    metadata = ext in {".jpg", ".jpeg", ".jfif", ".png", ".pdf", ".wav", ".flac", ".mp3", ".ogg", ".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
    return ([signal] if signal else []) + (["metadata-HMAC-SHA256"] if metadata else ["sidecar-HMAC-SHA256"])


def watermark(data, token, name):
    methods = methods_for(name)
    if "sidecar-HMAC-SHA256" in methods:
        # CSV/JSON/text/unsupported binary retain exactly their original bytes.
        return data
    if Path(name).suffix.lower() == ".pdf":
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs cannot be watermarked without a document password")
        writer = PdfWriter(clone_from=reader)
        writer.add_metadata({"/NexusWatermark": token})
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()
    return dispatcher.inject_watermark_bytes(data, token, file_identifier=name)
