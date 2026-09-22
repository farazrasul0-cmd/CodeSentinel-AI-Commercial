"""Security utilities: SSRF defense, envelope encryption, JWT authentication, and API key hashing."""

import base64
import hashlib
import ipaddress
import re
import secrets
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

ALLOWED_SCHEMES = {"http", "https", "git", "ssh"}

BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


# ============================================================================
# SSRF Defense
# ============================================================================


def is_safe_repository_url(url: str) -> tuple[bool, str]:
    """Validates that a Git repository URL does not target internal subnets or local resources (SSRF defense)."""
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string"

    url = url.strip()

    # Allow local directories in development/testing mode for standalone execution
    if (settings.APP_ENV in {"development", "testing"} or settings.DEBUG) and (
        url.startswith("file://") or (len(url) > 2 and Path(url).exists())
    ):
        raw_path = url[7:] if url.startswith("file://") else url
        try:
            local_path = Path(raw_path).expanduser().resolve()
            if local_path.exists() and local_path.is_dir():
                return True, "Safe local development directory"
        except Exception:
            pass

    # Regex check for typical git/https URLs
    if not (url.startswith("https://") or url.startswith("http://") or url.startswith("git@")):
        return False, "URL must use https:// or git@"

    if url.startswith("git@"):
        match = re.match(r"^git@([a-zA-Z0-9.-]+):([\w.-]+)/([\w.-]+)(\.git)?$", url)
        if not match:
            return False, "Invalid SSH git URL format"
        hostname = match.group(1)
    else:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            return False, f"Unsupported scheme: {parsed.scheme}"
        hostname = parsed.hostname
        if not hostname:
            return False, "URL does not contain a valid hostname"

    if hostname.lower() in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return False, "Access to localhost/loopback addresses is forbidden"

    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for entry in addr_info:
            ip_str = entry[4][0]
            ip_obj = ipaddress.ip_address(ip_str)
            for blocked in BLOCKED_NETWORKS:
                if ip_obj in blocked:
                    return False, f"Host resolves to prohibited internal address: {ip_str}"
    except (socket.gaierror, ValueError):
        if hostname.lower() in {"github.com", "gitlab.com", "bitbucket.org"}:
            return True, "Valid domain"
        return False, f"Failed to resolve hostname: {hostname}"

    return True, "URL is safe"


# ============================================================================
# Envelope Encryption for Secrets & Third-Party Tokens (KMS / Fernet)
# ============================================================================


def _get_fernet() -> Fernet:
    """Returns a Fernet instance safely derived from settings.ENCRYPTION_KEY."""
    raw_bytes = settings.ENCRYPTION_KEY.encode("utf-8")
    derived_32bytes = hashlib.sha256(raw_bytes).digest()
    urlsafe_b64 = base64.urlsafe_b64encode(derived_32bytes)
    return Fernet(urlsafe_b64)


def encrypt_secret(plain_text: str | None) -> str | None:
    """Encrypts a sensitive string (GitHub OAuth token, private key) before storing in DB."""
    if plain_text is None:
        return None
    fernet = _get_fernet()
    return fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str | None) -> str | None:
    """Decrypts an envelope-encrypted string from DB."""
    if cipher_text is None:
        return None
    fernet = _get_fernet()
    try:
        return fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        return None


# ============================================================================
# JWT Session Authentication
# ============================================================================


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Creates a signed JWT access token with an expiration timestamp."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Creates a signed JWT refresh token with a longer expiration window."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_jwt_token(token: str) -> dict[str, Any] | None:
    """Decodes and validates a JWT token; returns payload or None if expired/invalid."""
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError:
        return None


# ============================================================================
# API Key Management & Hashing
# ============================================================================


def generate_api_key(prefix: str = "cs_live") -> tuple[str, str, str]:
    """Generates a secure API key.
    
    Returns:
        (raw_key, display_prefix, sha256_hash)
        raw_key: Returned ONCE to the user (e.g. cs_live_9f81a7...)
        display_prefix: Safe to show in UI (e.g. cs_live_9f81...)
        sha256_hash: Stored in the database for constant-time lookup/verification
    """
    entropy = secrets.token_hex(24)
    raw_key = f"{prefix}_{entropy}"
    display_prefix = f"{prefix}_{entropy[:6]}..."
    sha256_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return raw_key, display_prefix, sha256_hash


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Constant-time verification of an API key against its stored SHA-256 hash."""
    computed_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return secrets.compare_digest(computed_hash, stored_hash)