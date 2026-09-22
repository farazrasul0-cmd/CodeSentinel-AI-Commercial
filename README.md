<div align="center">

# CodeSentinel AI (Commercial Edition)

**Enterprise Automated Pull-Request Review, Polyglot Static Analysis & SaaS Quality Platform.**

[![Backend Tests](https://img.shields.io/badge/backend%20tests-117%20passed-2ea44f?style=flat-square)](https://github.com/farazrasul0-cmd/CodeSentinel-AI-Commercial)
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

[Overview](#overview) &bull; [Visual Walkthrough](#platform-visuals) &bull; [Competitive Advantage](#competitive-advantage) &bull; [Architecture](#enterprise-architecture) &bull; [Quickstart](#commercial-quickstart) &bull; [Billing Model](#seat-metering--billing) &bull; [Security Readiness](#enterprise-security--audit-readiness)

</div>

---

## Overview

**CodeSentinel AI Commercial** transforms software quality analysis and code review into a scalable, enterprise-grade B2B SaaS platform. Engineered to compete directly with **CodeRabbit** ($24&ndash;$72/dev/mo) and **SonarQube Cloud**, CodeSentinel delivers automated pull-request review comments, AST-validated 1-click remediation suggestions, polyglot static analysis, and TreeSHAP explainable defect prediction under a strict **<60-second SLA**.

Unlike legacy static analysis tools that flood developers with noisy warnings or open-ended LLM wrappers that inflate inference costs and hallucinate syntax, CodeSentinel combines:
1. **Tree-sitter Polyglot AST Parsing**: Instant parsing across Python, TypeScript, JavaScript, Go, Java, and Rust.
2. **Dual-Layer Secret Detection**: Deterministic signatures paired with Shannon entropy calculations (>3.8 bits/sym) and test-fixture suppression.
3. **Diff-Scoped PR Review Bot**: Fast, hunk-targeted evaluation that updates pull requests in-place and formats suggestions as native GitHub 1-click apply blocks.
4. **SaaS Multi-Tenancy & Active PR Contributor Seat Metering**: PostgreSQL Row-Level Security (RLS), constant-time API key verification, and metered billing where only active PR authors consume seats.

---

## Platform Visuals

### 1. Automated GitHub PR Review with 1-Click Suggestion

```markdown
<!-- codesentinel-pr-summary -->
### 🛡️ CodeSentinel AI — PR Review & Quality Gate

| Metric | Baseline | This PR | Delta | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Repository Quality Index (RQI)** | `84.8` | `89.0` | `+4.2` | ✅ **PASSED** |
| **Security Finding Count** | `0` | `0` | `0` | ✅ **CLEAN** |
| **Maintainability Score** | `81.0` | `87.5` | `+6.5` | ✅ **IMPROVED** |

> **Summary**: Comprehensive cryptographic upgrade verified. Replaced legacy ECB cipher with AES-256-GCM. 
> 1 inline suggestion generated for nonce uniqueness check.
```

**Inline Hunk Review Comment**:
```diff
@@ -24,8 +24,14 @@ export class EnvelopeEncryptor {
   async encrypt(data: Buffer, masterKey: string): Promise<CipherPayload> {
-    const cipher = crypto.createCipher('aes-128-ecb', masterKey);
+    const iv = crypto.randomBytes(12);
+    const cipher = crypto.createCipheriv('aes-256-gcm', keyBuffer, iv);
```
> ⚠️ **CodeSentinel AI** `[CRYPTO-GCM-NONCE-CHECK]` &bull; Severity: **MEDIUM**
> 
> *Ensure Nonce Uniqueness under High Throughput*: Standard `randomBytes(12)` is strong, but in ultra-high concurrency distributed services, prepending a sequential counter or host identifier prevents birthday-bound IV reuse.
>
> ```suggestion
>     // Ensure 96-bit unique IV combining high-res timestamp and CSPRNG
>     const iv = Buffer.concat([crypto.randomBytes(8), Buffer.alloc(4, Date.now() & 0xffffffff)]);
> ```
> <button><b>Commit suggestion</b></button> *(Native 1-Click Commit directly on GitHub)*

---

### 2. Commercial Web Dashboard & Seat Utilization

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  🛡️ CodeSentinel AI  [ Acme Payments Inc. ▾ ] [ Team Plan ]    Seats: 4 / 10 Active     │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  [PR Bot Reviews]  [Connected Repositories]  [Deep Scanner]  [Radar Scorecard]  [Billing]│
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   ORGANIZATION REPOSITORY HEALTH                  ACTIVE PR SEAT METER (30-DAY)        │
│   ┌───────────────────────────────────┐           ┌──────────────────────────────────┐ │
│   │ 4-Pillar RQI Score: 88.4 / 100    │           │ Active Contributors: 4 / 10      │ │
│   │                                   │           │ [████████████░░░░░░░░░░] 40%     │ │
│   │   Security:       94.0 (Grade A)  │           │                                  │ │
│   │   Maintainability:88.2 (Grade B)  │           │ Roster (Trailing 30 Days):       │ │
│   │   Architecture:   86.5 (Grade B)  │           │  • @farazrasul  (Last PR: Today) │ │
│   │   Test Coverage:  85.0 (Grade B)  │           │  • @sarahchen   (Last PR: Today) │ │
│   └───────────────────────────────────┘           │  • @mkaiser     (Last PR: 2d ago)│ │
│                                                   │  • @dev-bot-lead(Last PR: 4d ago)│ │
│                                                   └──────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Competitive Advantage

| Feature | CodeSentinel AI Commercial | CodeRabbit | SonarQube Cloud |
| :--- | :--- | :--- | :--- |
| **Pricing Model** | **$29/active PR author/mo** (Soft-gated) | $24–$72/dev/mo | Line of Code (LOC) tiering |
| **Review Turnaround SLA** | **<60s** (Dedicated `pr_lane`) | 2–5 minutes | 3–15 minutes |
| **Remediation Engine** | **AST-Validated Suggestions** (Tree-sitter checked) | LLM-generated suggestions | Manual remediation guides |
| **Inline Comment Policy** | **Capped Top-5** (Strict anti-fatigue) | Configurable / Full review | PR decoration / check-runs |
| **Secret Detection** | **Dual-Layer** (Regex + Shannon Entropy) | LLM heuristics | Static rule patterns |
| **Defect Risk Explainability** | **TreeSHAP local feature drivers** | Black-box LLM | Heuristic rule debt |
| **Execution Sandboxing** | **Ephemeral container** (`.git/hooks` stripped) | Cloud workers | Server agent |
| **Deployment Model** | **Self-hosted Docker / Multi-tenant SaaS** | SaaS only | SaaS / Self-hosted |

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

## Enterprise Security & Audit Readiness

- **PostgreSQL Row-Level Security (RLS)**: Enforced directly inside PostgreSQL via session variables (`SET LOCAL app.current_org_id = :org_id`), providing mathematical tenant isolation at the query level.
- **Cryptographic Envelope Encryption**: Symmetric Fernet ciphers protect third-party access tokens and credentials at rest using SHA-256 derived keys.
- **Structured Audit Logging**: Comprehensive audit trail recording user logins, role modifications, API key generation, and quality policy overrides via `/api/v1/audit/logs`.
- **Zero-Trust Execution Sandbox**: Ephemeral container execution removes executable `.git/hooks`, enforces process timeouts, and guards against symlink path traversal.
