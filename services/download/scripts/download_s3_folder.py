"""
High-Performance S3 Folder & File Downloader.
Downloads an entire folder (prefix) or specific file from Amazon S3 to your local directory
with multi-threaded chunking and real-time progress tracking.
"""
import os
import sys
import time
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import boto3
from boto3.s3.transfer import TransferConfig

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from config import AWS_REGION, S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
except ImportError:
    AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "demo-bucket-prism")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")

from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import NoCredentialsError, ClientError


class DownloadProgressTracker:
    """Tracks and displays real-time download progress across all files."""
    def __init__(self, filename: str, total_bytes: int):
        self.filename = filename
        self.total_bytes = total_bytes
        self.downloaded = 0
        self.start_time = time.time()
        self.last_print = time.time()

    def __call__(self, bytes_amount: int):
        self.downloaded += bytes_amount
        now = time.time()
        if now - self.last_print >= 0.3 or self.downloaded >= self.total_bytes:
            self.last_print = now
            elapsed = now - self.start_time
            speed = (self.downloaded / (1024 * 1024)) / elapsed if elapsed > 0 else 0
            if self.total_bytes > 0:
                pct = (self.downloaded / self.total_bytes) * 100
                total_mb = self.total_bytes / (1024 * 1024)
                curr_mb = self.downloaded / (1024 * 1024)
                sys.stdout.write(f"\r  -> {self.filename[:30]:<30} | {pct:5.1f}% | {curr_mb:7.1f}/{total_mb:.1f} MB | {speed:5.1f} MB/s")
            else:
                curr_mb = self.downloaded / (1024 * 1024)
                sys.stdout.write(f"\r  -> {self.filename[:30]:<30} | {curr_mb:7.1f} MB | {speed:5.1f} MB/s")
            sys.stdout.flush()


def get_s3_client(access_key=None, secret_key=None, region=None, anonymous=False):
    reg = region or AWS_REGION or "ap-south-1"
    
    if anonymous:
        return boto3.client("s3", region_name=reg, config=Config(signature_version=UNSIGNED))
        
    ak = access_key or AWS_ACCESS_KEY_ID or os.getenv("AWS_ACCESS_KEY_ID")
    sk = secret_key or AWS_SECRET_ACCESS_KEY or os.getenv("AWS_SECRET_ACCESS_KEY")
    
    if ak and sk:
        return boto3.client("s3", region_name=reg, aws_access_key_id=ak, aws_secret_access_key=sk)
    
    return boto3.client("s3", region_name=reg)


def download_single_file(s3_client, bucket: str, key: str, local_file_path: Path, transfer_config: TransferConfig):
    local_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Get file size
    try:
        head = s3_client.head_object(Bucket=bucket, Key=key)
        total_size = head.get("ContentLength", 0)
    except Exception:
        total_size = 0

    tracker = DownloadProgressTracker(local_file_path.name, total_size)
    
    s3_client.download_file(
        Bucket=bucket,
        Key=key,
        Filename=str(local_file_path),
        Callback=tracker,
        Config=transfer_config
    )
    print()  # Print newline after progress finishes


def download_s3_folder(
    bucket: str = S3_BUCKET_NAME,
    s3_prefix: str = "",
    local_dir: str = "./downloaded_data",
    access_key: str = None,
    secret_key: str = None,
    region: str = None,
    anonymous: bool = False
):
    """
    Recursively downloads all files under `s3_prefix` in `bucket` to `local_dir`.
    """
    try:
        s3 = get_s3_client(access_key=access_key, secret_key=secret_key, region=region, anonymous=anonymous)
    except Exception as e:
        print(f"❌ Failed to initialize S3 client: {e}")
        return

    local_base = Path(local_dir).resolve()
    local_base.mkdir(parents=True, exist_ok=True)

    # Normalize prefix (remove leading slash)
    s3_prefix = s3_prefix.lstrip("/")
    
    print("=" * 70)
    print(">> S3 FOLDER & FILE DOWNLOADER")
    print("=" * 70)
    print(f" * S3 Bucket:       {bucket}")
    print(f" * S3 Folder/Prefix: s3://{bucket}/{s3_prefix}")
    print(f" * Local Target:    {local_base}")
    print(f" * Region:          {region or AWS_REGION or 'ap-south-1'}")
    print("-" * 70)

    print("Connecting to S3 and listing files...")
    paginator = s3.get_paginator("list_objects_v2")
    try:
        pages = list(paginator.paginate(Bucket=bucket, Prefix=s3_prefix))
    except NoCredentialsError:
        print("\n[ERROR] AWS CREDENTIALS NOT FOUND!")
        print("-" * 70)
        print("To fix this, provide your AWS credentials in one of these ways:\n")
        print("1. Pass credentials directly in the command:")
        print("   python scripts/download_s3_folder.py --access-key YOUR_KEY --secret-key YOUR_SECRET --bucket YOUR_BUCKET --prefix your-folder/\n")
        print("2. Set environment variables in PowerShell:")
        print('   $env:AWS_ACCESS_KEY_ID="YOUR_ACCESS_KEY"')
        print('   $env:AWS_SECRET_ACCESS_KEY="YOUR_SECRET_KEY"')
        print('   $env:AWS_DEFAULT_REGION="ap-south-1"\n')
        print("3. If the S3 bucket is public/open, add --anonymous:")
        print("   python scripts/download_s3_folder.py --anonymous --bucket YOUR_BUCKET --prefix your-folder/")
        print("-" * 70)
        return
    except ClientError as ce:
        print(f"\n[ERROR] S3 Client Error: {ce}")
        return
    except Exception as e:
        print(f"\n[ERROR] Error listing S3 objects: {e}")
        return

    items_to_download = []
    total_bytes = 0

    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            # Skip virtual folder keys that end with '/'
            if key.endswith("/"):
                continue
            size = obj["Size"]
            total_bytes += size
            
            # Compute relative local path
            if s3_prefix and key.startswith(s3_prefix):
                rel_path = key[len(s3_prefix):].lstrip("/")
                if not rel_path:
                    rel_path = Path(key).name
            else:
                rel_path = key

            local_path = local_base / rel_path
            items_to_download.append((key, local_path, size))

    if not items_to_download:
        print(f"[WARNING] No files found matching prefix '{s3_prefix}' in bucket '{bucket}'.")
        return

    print(f"Found {len(items_to_download)} file(s) ({total_bytes / (1024*1024):.2f} MB total). Starting download...\n")

    transfer_config = TransferConfig(
        multipart_threshold=8 * 1024 * 1024,
        max_concurrency=4,
        multipart_chunksize=8 * 1024 * 1024,
        use_threads=True
    )

    start_time = time.time()
    for idx, (key, local_path, size) in enumerate(items_to_download, 1):
        print(f"[{idx}/{len(items_to_download)}] Downloading: {key} -> {local_path.name}")
        try:
            download_single_file(s3, bucket, key, local_path, transfer_config)
        except Exception as e:
            print(f"[ERROR] Failed to download {key}: {e}")

    elapsed = time.time() - start_time
    print("=" * 70)
    print(f"[SUCCESS] DOWNLOAD COMPLETE in {elapsed:.1f}s!")
    print(f" * Files saved to: {local_base}")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download a folder or files from S3 to local system.")
    parser.add_argument("--bucket", "-b", default=S3_BUCKET_NAME, help=f"S3 bucket name (default: {S3_BUCKET_NAME})")
    parser.add_argument("--prefix", "-p", default="", help="S3 folder path / key prefix to download (e.g. 'my-folder/' or 'val2014.zip')")
    parser.add_argument("--output", "-o", default="./downloaded_data", help="Local directory to save files into (default: ./downloaded_data)")
    parser.add_argument("--access-key", default=None, help="AWS Access Key ID")
    parser.add_argument("--secret-key", default=None, help="AWS Secret Access Key")
    parser.add_argument("--region", default=AWS_REGION, help=f"AWS Region (default: {AWS_REGION})")
    parser.add_argument("--anonymous", action="store_true", help="Use unsigned/anonymous requests for public S3 buckets")
    
    args = parser.parse_args()
    download_s3_folder(
        bucket=args.bucket,
        s3_prefix=args.prefix,
        local_dir=args.output,
        access_key=args.access_key,
        secret_key=args.secret_key,
        region=args.region,
        anonymous=args.anonymous
    )
