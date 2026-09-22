"""Production Environment & Configuration Validator for CodeSentinel AI Commercial.

Run this script before launching the production Docker container stack to verify
that all mandatory credentials, cryptographic keys, and settings are present.

Usage:
    python backend/scripts/verify_production_env.py
"""

import os
import sys

REQUIRED_VARS = [
    ("DATABASE_URL", "PostgreSQL database connection string (asyncpg)"),
    ("REDIS_URL", "Redis cache and session broker connection URL"),
    ("CELERY_BROKER_URL", "Celery task queue broker URL"),
    ("FERNET_MASTER_KEY", "Fernet symmetric key for token envelope encryption"),
    ("JWT_SECRET", "Cryptographic secret string for signing JWT session tokens"),
    ("GITHUB_APP_ID", "Registered GitHub App identifier"),
    ("GITHUB_APP_PRIVATE_KEY", "PEM-formatted RSA private key for minting App JWTs"),
    ("GITHUB_APP_WEBHOOK_SECRET", "Shared secret for verifying GitHub webhook HMAC-SHA256 signatures"),
    ("STRIPE_API_KEY", "Stripe API secret key (sk_live_...)"),
    ("STRIPE_WEBHOOK_SECRET", "Stripe Webhook signing secret (whsec_...)"),
]

OPTIONAL_VARS = [
    ("S3_ENDPOINT_URL", "Object storage endpoint for MinIO/S3"),
    ("S3_BUCKET_NAME", "S3 bucket name for SARIF and AST cache storage"),
    ("SENTRY_DSN", "Sentry error monitoring DSN"),
]


def check_environment() -> bool:
    print("=" * 65)
    print("CodeSentinel AI Commercial - Production Readiness Diagnostic")
    print("=" * 65)

    all_passed = True
    missing_required = []

    print("\n[1/2] Checking Critical Production Variables:")
    for var, description in REQUIRED_VARS:
        val = os.getenv(var)
        if not val or "change_me" in val or "replace_with" in val:
            print(f"  [MISSING] {var} - {description}")
            missing_required.append(var)
            all_passed = False
        else:
            masked = val[:4] + "..." + val[-4:] if len(val) > 10 else "***"
            print(f"  [OK]      {var} = {masked}")

    print("\n[2/2] Checking Recommended Auxiliary Variables:")
    for var, description in OPTIONAL_VARS:
        val = os.getenv(var)
        if val:
            masked = val[:4] + "..." + val[-4:] if len(val) > 10 else "***"
            print(f"  [CONFIGURED] {var} = {masked}")
        else:
            print(f"  [OPTIONAL]   {var} - {description}")

    print("\n" + "=" * 65)
    if all_passed:
        print("[SUCCESS] ALL PRODUCTION CHECKS PASSED - READY FOR DOCKER DEPLOYMENT")
        print("=" * 65)
        return True
    else:
        print(f"[ACTION REQUIRED] {len(missing_required)} CRITICAL VARIABLES NEED ATTENTION IN .env")
        print("=" * 65)
        return False


if __name__ == "__main__":
    success = check_environment()
    sys.exit(0 if success else 1)
