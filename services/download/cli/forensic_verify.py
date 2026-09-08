"""
Forensic CLI Verification Tool.

Usage:
    python cli/forensic_verify.py <path_to_suspect_file>

Extracts the embedded tracking token from container headers, validates cryptographic authenticity,
and outputs the forensic audit trail (Leaker Identity, Download Session, Timestamp).
"""
import sys
import os
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.injectors.extractor import extract_token_from_file
from core.crypto import verify_watermark_token
from database.db import db


def analyze_file(file_path_str: str):
    file_path = Path(file_path_str)
    print("=" * 70)
    print(f" [FORENSIC LEAK INSPECTION]: {file_path.name}")
    print("=" * 70)

    if not file_path.exists():
        print(f"[!] Error: File '{file_path_str}' does not exist.")
        return

    print(f"File Path:         {file_path.resolve()}")
    print(f"File Size:         {file_path.stat().st_size:,} bytes")
    
    # 1. Extract Token from container headers
    token, detected_format = extract_token_from_file(file_path)
    print(f"Detected Format:   {detected_format}")

    if not token:
        print("\n[RESULT] No enterprise tracking watermark found in file headers.")
        print("=" * 70)
        return

    print(f"Embedded Token:    {token[:35]}...{token[-15:]}")

    # 2. Cryptographic Verification
    is_valid, payload, msg = verify_watermark_token(token)
    if is_valid:
        print(f"Crypto Signature:  [VALID & AUTHENTIC] (HMAC-SHA256)")
    else:
        print(f"Crypto Signature:  [TAMPERED / INVALID] ({msg})")
        print("=" * 70)
        return

    # 3. Decoded Token Details
    print("-" * 70)
    print(" FORENSIC IDENTITY REPORT")
    print("-" * 70)
    print(f" * User ID:        {payload.get('uid', 'N/A')}")
    print(f" * User Email:     {payload.get('uem', 'N/A')}")
    print(f" * Download UUID:  {payload.get('did', 'N/A')}")
    print(f" * S3 Source Key:  {payload.get('key', 'N/A')}")
    print(f" * Download IP:    {payload.get('ip', 'N/A')}")
    print(f" * Epoch Time:     {payload.get('ts', 'N/A')}")
    
    # 4. Database Audit Registry Match
    audit_record = db.find_by_download_id(payload.get("did", ""))
    if audit_record:
        print(f" * Audit Registry: [MATCH CONFIRMED] (Status: {audit_record.get('status')})")
        print(f" * Logged Time:    {audit_record.get('iso_timestamp')}")
    else:
        print(" * Audit Registry: Token authentic, but transaction is outside local database.")

    print("=" * 70)
    print("[CONCLUSION] Origin and downloading user conclusively identified.")
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python cli/forensic_verify.py <path_to_image_file>")
        sys.exit(1)

    analyze_file(sys.argv[1])
