"""config/s3.py — S3/MinIO client helper.

Uses boto3 sync client wrapped in asyncio.to_thread for async compatibility.
"""
from __future__ import annotations

import asyncio
import logging

import boto3
from botocore.exceptions import ClientError

from config.settings import settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    """Lazily create a boto3 S3 client."""
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
        )
    return _client


async def upload_file(bucket: str, key: str, data: bytes, content_type: str) -> str:
    """Upload a file to S3 and return the key."""
    def _upload():
        client = _get_client()
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key

    return await asyncio.to_thread(_upload)


def get_file_url(bucket: str, key: str) -> str:
    """Construct the URL for an S3 object."""
    return f"{settings.S3_ENDPOINT}/{bucket}/{key}"


async def delete_file(bucket: str, key: str) -> None:
    """Delete an object from S3."""
    def _delete():
        client = _get_client()
        client.delete_object(Bucket=bucket, Key=key)

    await asyncio.to_thread(_delete)


async def ensure_bucket(bucket: str) -> None:
    """Create the bucket if it does not exist."""
    def _ensure():
        client = _get_client()
        try:
            client.head_bucket(Bucket=bucket)
        except ClientError:
            client.create_bucket(Bucket=bucket)
            logger.info("Created S3 bucket: %s", bucket)

    await asyncio.to_thread(_ensure)
