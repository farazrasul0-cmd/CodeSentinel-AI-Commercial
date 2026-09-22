# CodeSentinel AI Commercial Architecture Specification

## 1. Executive Summary

CodeSentinel AI Commercial is an enterprise software quality engineering and automated pull-request review platform designed to compete directly with platforms like CodeRabbit and SonarQube Cloud. Built with multi-engine static analysis, tree-sitter polyglot AST parsing, Shannon entropy dual-layer secret detection, and local ML defect forecasting (TreeSHAP), CodeSentinel delivers low-latency (<60s) pull-request feedback with 1-click remediation directly on GitHub.

---

## 2. Seven-Pillar SaaS Architecture

```
                    +------------------------------------+
                    |       GitHub Webhooks / PRs        |
                    +-----------------+------------------+
                                      |
                                      v
                    +------------------------------------+
                    |    FastAPI Enterprise Ingestion     |
                    | (HMAC-SHA256, Dynamic RS256 JWT)   |
                    +-----------------+------------------+
                                      |
         +----------------------------+----------------------------+
         |                                                         |
         v                                                         v
+--------------------------+                             +--------------------------+
|  Celery Lane: pr_lane    |                             | Celery Lane: batch_lane  |
|  Interactive PR Bot SLA  |                             | Full Repo Nightly Audit  |
|  Hard Timeout: 60s       |                             | Timeout: 1800s           |
+------------+-------------+                             +------------+-------------+
             |                                                        |
             +----------------------------+---------------------------+
                                          |
                                          v
                    +------------------------------------+
                    |      Ephemeral Sandbox Context     |
                    | (.git/hooks stripped, RCE blocked) |
                    +-----------------+------------------+
                                      |
         +----------------------------+----------------------------+
         |                                                         |
         v                                                         v
+--------------------------+                             +--------------------------+
|  Polyglot AST Engine     |                             | Dual-Layer Secret Engine |
|  Tree-sitter (6 targets) |                             | Pattern + Shannon Entropy|
|  Cyclomatic & Halstead   |                             | Heuristic Suppressions   |
+--------------------------+                             +--------------------------+
                                      |
                                      v
                    +------------------------------------+
                    |  4-Pillar RQI Aggregation Engine   |
                    |  Quality Gate Checks (Pass/Block)  |
                    +-----------------+------------------+
                                      |
         +----------------------------+----------------------------+
         |                                                         |
         v                                                         v
+--------------------------+                             +--------------------------+
| GitHub PR Bot Actions    |                             | PostgreSQL RLS Database  |
| In-place Summary PATCH   |                             | SET LOCAL app.org_id=... |
| 1-Click Suggestion Blocks|                             | Fernet Token Encryption  |
+--------------------------+                             +--------------------------+
```

---

## 3. Core Enterprise Pillars

### Pillar 1: Tenant Isolation & Cryptographic Hygiene
- **PostgreSQL Row-Level Security (RLS)**: Enforces tenant data isolation at the engine level via `SET LOCAL app.current_org_id = :org_id`.
- **Envelope Encryption**: All OAuth credentials, GitHub installation tokens, and API tokens are encrypted using symmetric Fernet encryption with keys derived via SHA-256.
- **Constant-Time Verification**: API keys are authenticated using `secrets.compare_digest` to eliminate side-channel timing attacks.

### Pillar 2: Ephemeral Sandbox Confinement
- **Zero-RCE Isolation**: Every analysis task executes within a temporary directory created via `tempfile.TemporaryDirectory()`.
- **Git Hook Neutralization**: `.git/hooks/` directories are immediately removed before any analysis to prevent malicious executable execution.
- **Symlink Escape Guards**: Path resolution checks (`os.path.realpath`) verify that no symlink points outside the assigned sandbox root.
- **Disk Quota Constraints**: Enforces maximum repository size limits (`MAX_REPO_SIZE_MB = 2000`).

### Pillar 3: Dedicated Dual-Queue Asynchronous Architecture
- **Interactive PR Lane (`pr_lane`)**: Webhook-triggered PR reviews are prioritized with a strict 45-second soft timeout and 60-second hard timeout.
- **Monorepo Batch Lane (`batch_lane`)**: Heavy repository-wide scans, historical commit audits, and ML re-training jobs execute asynchronously without impacting interactive PR latency.

### Pillar 4: Polyglot Parsing & Dual-Layer Secret Scanning
- **Tree-sitter AST Bindings**: Native support across Python, TypeScript, JavaScript, Go, Java, and Rust with zero compiler build-time dependencies.
- **Dual-Layer Secret Detection**: Combines deterministic regex signatures (AWS, GitHub, Slack, RSA) with mathematical Shannon entropy verification (>3.8 bits/symbol) while filtering benign test fixtures.

### Pillar 5: SaaS Billing & Seat Metering
- **Active PR Contributor Model**: Only developers who author pull requests reviewed within a trailing 30-day window count against paid seats.
- **Soft-Gating Architecture**: When seat limits are reached, PR scanning continues uninterrupted while administrative notices and soft alerts guide account owners to add seats.
- **Idempotent Webhooks**: All Stripe events (`checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`) are deduplicated using database idempotency records.

### Pillar 6: Enterprise Security & Audit Readiness
- **Structured Audit Trails**: Every sensitive action (`API_KEY_CREATED`, `SEATS_UPGRADED`, `SETTINGS_CHANGED`, `QUALITY_GATE_BLOCKED`) is immutably logged with actor, IP address, timestamp, and metadata.
- **Role-Based Audit Queries**: Audit log query and export endpoints are strictly restricted to `ADMIN` and `OWNER` roles.

---

## 4. Production Deployment Topology

The commercial platform is delivered as a containerized stack configured for Docker Swarm, Amazon ECS, or Kubernetes:

| Service | Technology | Role |
| :--- | :--- | :--- |
| **Frontend SPA** | React 18, Vite, TailwindCSS, Lucide | Modern B2B SaaS dashboard & PR review inspector |
| **Reverse Proxy** | Nginx Alpine | Serves frontend assets, terminates TLS, proxies `/api/` |
| **Backend API** | FastAPI, Python 3.12, Uvicorn | REST API, webhook receivers, OAuth2 SSO, RBAC |
| **PR Worker** | Celery 5.3 (`pr_lane`) | Dedicated low-latency PR review worker (<60s SLA) |
| **Batch Worker** | Celery 5.3 (`batch_lane`) | Dedicated high-throughput repository scan worker |
| **Primary Database**| PostgreSQL 16 (RLS enabled) | Multi-tenant relational storage & audit logging |
| **Cache & Broker** | Redis 7 Alpine | Installation token cache (50m TTL) & Celery queue broker |
| **Artifact Storage**| S3 / MinIO | SARIF exports, raw diffs, and AST cache storage |
