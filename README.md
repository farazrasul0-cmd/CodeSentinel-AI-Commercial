<div align="center">

# CodeSentinel AI (Commercial Edition)

**Enterprise Automated Pull-Request Review, Polyglot Static Analysis & SaaS Quality Platform.**

[![Backend Tests](https://img.shields.io/badge/backend%20tests-114%20passed-2ea44f?style=flat-square)](https://github.com/farazrasul0-cmd/CodeSentinel-AI-Commercial)
[![Frontend Tests](https://img.shields.io/badge/frontend%20tests-11%20passed-2ea44f?style=flat-square)](https://github.com/farazrasul0-cmd/CodeSentinel-AI-Commercial)
[![Python](https://img.shields.io/badge/python-3.12-387baf?style=flat-square)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/react-18-61dafb?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/typescript-5.2-3178c6?style=flat-square)](https://www.typescriptlang.org)
[![Tree-sitter](https://img.shields.io/badge/AST-Tree--sitter%20Polyglot-teal?style=flat-square)](https://tree-sitter.github.io)
[![Celery](https://img.shields.io/badge/Celery-Dual--Queue%20SLA-37814A?style=flat-square)](https://docs.celeryq.dev)
[![Stripe](https://img.shields.io/badge/Stripe-Seat%20Metering-635BFF?style=flat-square)](https://stripe.com)
[![License](https://img.shields.io/badge/license-Commercial-blue?style=flat-square)](LICENSE)

<br/>

[Overview](#overview) &bull; [Competitive Comparison](#competitive-advantage) &bull; [Architecture](#enterprise-architecture) &bull; [Quickstart](#commercial-quickstart) &bull; [Billing Model](#seat-metering--billing) &bull; [SOC2 Compliance](#soc2-compliance--security)

</div>

---

## Overview

**CodeSentinel AI Commercial** transforms software quality analysis and code review into a scalable, enterprise-grade B2B SaaS platform. Engineered to compete directly with **CodeRabbit** ($24&ndash;$72/dev/mo) and **SonarQube Cloud**, CodeSentinel delivers automated pull-request review comments, native 1-click remediation suggestions, polyglot AST security analysis, and TreeSHAP explainable defect prediction under a strict **<60-second SLA**.

Unlike legacy static analysis tools that flood developers with noisy warnings or naive LLM wrappers that inflate inference costs and hallucinate syntax, CodeSentinel combines:
1. **Tree-sitter Polyglot AST Parsing**: Instant parsing across Python, TypeScript, JavaScript, Go, Java, and Rust.
2. **Dual-Layer Secret Detection**: Deterministic signatures paired with Shannon entropy calculations (>3.8 bits/sym) and test-fixture suppression.
3. **Diff-Scoped PR Review Bot**: Fast, hunk-targeted evaluation that updates pull requests in-place and formats suggestions as native GitHub 1-click apply blocks.
4. **SaaS Multi-Tenancy & Active PR Contributor Seat Metering**: PostgreSQL Row-Level Security (RLS), constant-time API key verification, and metered billing where only active PR authors consume seats.

---

## Competitive Advantage

| Feature | CodeSentinel AI Commercial | CodeRabbit | SonarQube Cloud |
| :--- | :---: | :---: | :---: |
| **Pricing Model** | $29/active PR author/mo (Soft-gated) | $24&ndash;$72/dev/mo | Line of Code (LOC) tiering |
| **Diff-Scoped Review SLA** | **<60s** (Dedicated `pr_lane`) | 2&ndash;5 minutes | 3&ndash;15 minutes |
| **1-Click Remediation** | Native GitHub ```suggestion``` blocks | Inline markdown | Manual remediation |
| **Noise & Anti-Spam** | Single in-place comment (HTTP PATCH) | Multiple PR comments | External check-run only |
| **Secret Detection** | Dual-Layer (Regex + Shannon Entropy) | Basic AI check | Pattern-based |
| **Explainable Defect Risk**| TreeSHAP feature contributions | None | None |
| **Sandboxing & Isolation** | Ephemeral context (.git/hooks stripped) | Cloud containers | Server agent |
| **Deployment Model** | Self-hosted Docker / Multi-tenant SaaS | SaaS only | SaaS or Self-hosted |

---

## Enterprise Architecture

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

## Commercial Quickstart

### Production Docker Compose Stack

1. **Clone the Commercial Repository**:
   ```bash
   git clone https://github.com/farazrasul0-cmd/CodeSentinel-AI-Commercial.git
   cd CodeSentinel-AI-Commercial
   ```

2. **Configure Environment Variables**:
   ```bash
   cp .env.production.example .env
   # Set your Fernet key, PostgreSQL password, Redis password, and Stripe credentials
   ```

3. **Launch the Container Stack**:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

4. **Verify Healthchecks**:
   ```bash
   curl http://localhost:8000/api/v1/health/live
   # {"status": "alive"}

   curl http://localhost:8000/api/v1/health/ready
   # {"status": "ready", "checks": {"database": "connected", "environment": "production"}}
   ```

---

## Seat Metering & Billing

CodeSentinel AI employs a transparent, developer-friendly **Active PR Contributor Seat Model**:
- **Who Consumes a Seat**: Only engineers who authored at least one PR reviewed by the platform in the trailing 30-day window. Passive reviewers, managers, and product leads do not require paid licenses.
- **Soft-Gating Architecture**: If a team temporarily exceeds its seat capacity during a release sprint, PR reviews continue uninterrupted. The system notifies administrators and displays a gentle banner rather than abruptly breaking developer workflows.
- **Self-Serve Stripe Portal**: Integrated with Stripe Checkout and Stripe Customer Portal for automated upgrades, card management, and VAT/tax invoice downloads.

---

## SOC2 Compliance & Security

- **Row-Level Security (RLS)**: Enforced directly inside PostgreSQL via session variables, ensuring complete isolation across customer tenants.
- **Cryptographic Hygiene**: Envelope encryption with Fernet symmetric ciphers encrypts all OAuth secrets and installation tokens at rest.
- **Immutable Audit Logging**: Every administrative action, API key generation, seat adjustment, and security finding override is recorded in an immutable, append-only SOC2 audit trail accessible via `/api/v1/audit/logs`.
- **Ephemeral Sandbox Neutralization**: Repositories are cloned into ephemeral isolation sandboxes with `.git/hooks/` stripped immediately to prevent remote code execution (RCE) and symlink escape attacks.
