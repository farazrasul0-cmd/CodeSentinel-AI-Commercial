"""Unit tests for Object Storage artifact offloading and local fallback."""

import hashlib
import tempfile
from pathlib import Path
import pytest
from app.infrastructure.storage.object_storage import ObjectStorageService


@pytest.mark.asyncio
async def test_object_storage_upload_and_retrieval():
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = ObjectStorageService()
        storage.fallback_dir = Path(tmp_dir)

        org_id = "org_alpha_123"
        job_id = "job_omega_456"
        artifact_type = "report.sarif.json"
        raw_payload = '{"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "CodeSentinel"}}}]}'

        # 1. Upload
        uri, sha256_hash = await storage.upload_artifact(
            org_id=org_id,
            job_id=job_id,
            artifact_type=artifact_type,
            data=raw_payload,
        )

        expected_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
        assert sha256_hash == expected_hash
        assert org_id in uri
        assert job_id in uri

        # 2. Retrieve
        retrieved_bytes = await storage.get_artifact(uri)
        assert retrieved_bytes.decode("utf-8") == raw_payload

        # 3. Delete
        deleted = await storage.delete_artifact(uri)
        assert deleted is True

        # 4. Confirm deleted
        with pytest.raises(FileNotFoundError):
            await storage.get_artifact(uri)