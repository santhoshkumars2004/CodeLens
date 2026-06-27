"""
CodeLens S3 Service.

Stores repository metadata and indexing state on AWS S3 free tier.
Optional — falls back gracefully when AWS credentials are not set.
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_client = None


def _get_s3_client():
    """Get or initialize the S3 client."""
    global _client
    if _client is None:
        if not settings.aws_access_key_id:
            logger.debug("s3_disabled", reason="No AWS credentials configured")
            return None
        try:
            import boto3
            _client = boto3.client(
                "s3",
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region,
            )
        except Exception as e:
            logger.warning("s3_init_failed", error=str(e))
            return None
    return _client


def save_repo_metadata(repo_id: str, metadata: Dict[str, Any]) -> bool:
    """Save repository indexing metadata to S3."""
    client = _get_s3_client()
    if client is None:
        return False

    try:
        key = f"repos/{repo_id.replace('/', '_')}/metadata.json"
        metadata["updated_at"] = datetime.utcnow().isoformat()

        client.put_object(
            Bucket=settings.s3_bucket_name,
            Key=key,
            Body=json.dumps(metadata, indent=2),
            ContentType="application/json",
        )
        logger.info("metadata_saved_to_s3", repo_id=repo_id)
        return True
    except Exception as e:
        logger.warning("s3_save_failed", repo_id=repo_id, error=str(e))
        return False


def get_repo_metadata(repo_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve repository metadata from S3."""
    client = _get_s3_client()
    if client is None:
        return None

    try:
        key = f"repos/{repo_id.replace('/', '_')}/metadata.json"
        response = client.get_object(
            Bucket=settings.s3_bucket_name, Key=key
        )
        return json.loads(response["Body"].read().decode("utf-8"))
    except Exception:
        return None
