"""Object Storage Package for Artifact Offloading."""

from app.infrastructure.storage.object_storage import (
    ObjectStorageService,
    object_storage,
)

__all__ = ["ObjectStorageService", "object_storage"]