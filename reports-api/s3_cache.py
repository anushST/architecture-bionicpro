"""S3 (MinIO) cache for generated reports."""

import json
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from config import settings

_s3_client = None
_bucket_ensured = False


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name="us-east-1",
        )
    return _s3_client


def ensure_bucket():
    """Create the S3 bucket if it doesn't exist and set public read policy."""
    global _bucket_ensured
    if _bucket_ensured:
        return
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=settings.S3_BUCKET)
    except ClientError:
        s3.create_bucket(Bucket=settings.S3_BUCKET)
        policy = json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"AWS": "*"},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{settings.S3_BUCKET}/*"],
            }],
        })
        s3.put_bucket_policy(Bucket=settings.S3_BUCKET, Policy=policy)
    _bucket_ensured = True


def _report_key(user_id: str) -> str:
    """S3 key for a user's report."""
    return f"{user_id}/report.json"


def check_cache(user_id: str) -> Optional[str]:
    """Check if report exists in S3. Returns CDN URL if found, None otherwise."""
    s3 = get_s3_client()
    key = _report_key(user_id)
    try:
        s3.head_object(Bucket=settings.S3_BUCKET, Key=key)
        return f"{settings.CDN_BASE_URL}/{key}"
    except ClientError:
        return None


def store_report(user_id: str, report_data: list[dict]) -> str:
    """Store report JSON in S3. Returns CDN URL."""
    s3 = get_s3_client()
    key = _report_key(user_id)
    body = json.dumps(report_data, default=str, ensure_ascii=False)

    s3.put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json",
    )

    return f"{settings.CDN_BASE_URL}/{key}"


def invalidate_cache(user_id: str) -> None:
    """Delete cached report for a user (e.g., after ETL refresh)."""
    s3 = get_s3_client()
    key = _report_key(user_id)
    try:
        s3.delete_object(Bucket=settings.S3_BUCKET, Key=key)
    except ClientError:
        pass
