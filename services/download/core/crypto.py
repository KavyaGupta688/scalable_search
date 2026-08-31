"""
Cryptographic module for generating and validating tamper-proof HMAC-SHA256 tracking tokens.
"""
import hmac
import hashlib
import json
import base64
import time
import uuid
from typing import Dict, Any, Tuple, Optional
from config import HMAC_SECRET_KEY


def create_tracking_payload(
    user_id: str,
    user_email: str,
    s3_key: str,
    client_ip: str = "127.0.0.1",
    extra_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Constructs the canonical payload dictionary for a download transaction.
    """
    download_id = str(uuid.uuid4())
    timestamp = int(time.time())
    
    payload = {
        "ver": "1.0",
        "did": download_id,
        "uid": user_id,
        "uem": user_email,
        "key": s3_key,
        "ts": timestamp,
        "ip": client_ip,
        "meta": extra_metadata or {}
    }
    return payload


def generate_watermark_token(payload: Dict[str, Any], secret_key: str = HMAC_SECRET_KEY) -> str:
    """
    Generates a cryptographically signed, tamper-proof tracking token:
    Format: base64(json(payload)).hmac_sha256_hex
    """
    payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode('utf-8')).decode('ascii')
    
    signature = hmac.new(
        secret_key.encode('utf-8'),
        payload_b64.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return f"AGY-WM-{payload_b64}.{signature}"


def verify_watermark_token(token_str: str, secret_key: str = HMAC_SECRET_KEY) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Verifies the integrity of a watermark token.
    Returns: (is_valid, payload_dict_or_none, error_or_success_message)
    """
    if not token_str or not isinstance(token_str, str):
        return False, None, "Empty or invalid token format"
    
    clean_token = token_str.strip()
    if clean_token.startswith("AGY-WM-"):
        clean_token = clean_token[len("AGY-WM-"):]
        
    parts = clean_token.split(".")
    if len(parts) != 2:
        return False, None, "Invalid token structure (expected payload.signature)"
    
    payload_b64, signature = parts[0], parts[1]
    
    expected_sig = hmac.new(
        secret_key.encode('utf-8'),
        payload_b64.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_sig, signature):
        return False, None, "Cryptographic signature mismatch! Token has been tampered with."
    
    try:
        payload_json = base64.urlsafe_b64decode(payload_b64.encode('ascii')).decode('utf-8')
        payload = json.loads(payload_json)
        return True, payload, "Token verified and authentic."
    except Exception as e:
        return False, None, f"Failed to decode token payload: {str(e)}"
