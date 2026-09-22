"""Commercial Object Storage Service (AWS S3, MinIO, and Local Fallback)."""

import hashlib
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import logger


class ObjectStorageService:
    """Manages offloading heavy reports, SARIF payloads, and graph snapshots to S3/MinIO.
    
    Prevents PostgreSQL BLOB bloat and supports strict multi-tenant key prefixes:
    `{org_id}/{job_id}/{artifact_type}`
    """

    def __init__(self) -> None:
        self.bucket = settings.S3_BUCKET_NAME
        self.endpoint_url = settings.S3_ENDPOINT_URL
        self.fallback_dir = Path(settings.STORAGE_LOCAL_FALLBACK_DIR)
        self.fallback_dir.mkdir(parents=True, exist_ok=True)
        self._s3_client: Any = None
        self._init_s3_client()

    def _init_s3_client(self) -> None:
        """Initializes boto3 client if credentials are configured."""
        if settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY:
            try:
                import boto3
                self._s3_client = boto3.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=settings.S3_ACCESS_KEY,
                    aws_secret_access_key=settings.S3_SECRET_KEY,
                    region_name=settings.S3_REGION,
                )
                logger.info(f"[Storage] Connected to Object Storage at {self.endpoint_url or 'AWS S3'}")
            except Exception as e:
                logger.warning(f"[Storage] Boto3 client initialization failed: {e}. Using local storage fallback.")
                self._s3_client = None

    async def upload_artifact(
        self,
        org_id: str,
        job_id: str,
        artifact_type: str,
        data: bytes | str,
    ) -> tuple[str, str]:
        """Uploads an artifact and returns (uri, sha256_hash).
        
        Key format: `{org_id}/{job_id}/{artifact_type}`
        """
        payload_bytes = data.encode("utf-8") if isinstance(data, str) else data
        sha256_hash = hashlib.sha256(payload_bytes).hexdigest()
        clean_key = f"{org_id}/{job_id}/{artifact_type}"

        if self._s3_client:
            try:
                self._s3_client.put_object(
                    Bucket=self.bucket,
                    Key=clean_key,
                    Body=payload_bytes,
                )
                uri = f"s3://{self.bucket}/{clean_key}"
                logger.debug(f"[Storage] Uploaded {clean_key} to S3 bucket {self.bucket}")
                return uri, sha256_hash
            except Exception as e:
                logger.error(f"[Storage] S3 upload failed for {clean_key}: {e}. Storing to local fallback.")

        # Local filesystem fallback
        dest = self.fallback_dir / clean_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload_bytes)
        uri = f"file://{dest.resolve().as_posix()}"
        logger.debug(f"[Storage] Stored artifact locally at {uri}")
        return uri, sha256_hash

    async def get_artifact(self, uri: str) -> bytes:
        """Retrieves raw artifact bytes by URI."""
        if uri.startswith("s3://") and self._s3_client:
            parts = uri[5:].split("/", 1)
            bucket = parts[0]
            key = parts[1]
            response = self._s3_client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()

        if uri.startswith("file://"):
            local_path = Path(uri[7:])
            if not local_path.exists():
                raise FileNotFoundError(f"Local artifact not found: {uri}")
            return local_path.read_bytes()

        # Try resolving as key within fallback dir
        candidate = self.fallback_dir / uri
        if candidate.exists():
            return candidate.read_bytes()

        raise FileNotFoundError(f"Artifact URI could not be resolved: {uri}")

    async def delete_artifact(self, uri: str) -> bool:
        """Deletes an artifact by URI."""
        if uri.startswith("s3://") and self._s3_client:
            try:
                parts = uri[5:].split("/", 1)
                self._s3_client.delete_object(Bucket=parts[0], Key=parts[1])
                return True
            except Exception as e:
                logger.warning(f"[Storage] Failed to delete S3 object {uri}: {e}")
                return False

        if uri.startswith("file://"):
            local_path = Path(uri[7:])
            if local_path.exists():
                local_path.unlink()
                return True

        return False


# Global singleton
object_storage = ObjectStorageService()