# trending-scout — Technical Collaboration Prospectus

> **Anti-distillation, sanitized edition.** This document is released under
> [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) with an
> explicit **no-LLM-training / no-distillation clause** (see §6).
> Code in this repository: MIT. Documents: CC BY-NC-ND 4.0.

**CANARY-ZS-TS-20260910-4F7A2C91** — this document embeds a unique canary
token. Authorized derivative deliverables embed per-partner canaries (§6.2).

---

## 1. One-line positioning

> Trending lists tell you what is hot. They do not tell you whether it is real,
> or whether it matters *to you*. trending-scout adversarially verifies every
> listed repository and grades it against a configurable business profile,
> producing a decision-ready daily review.

It is deliberately **not** a general-purpose SaaS and not a venture-funded
play. Small surface, honest degradation, calibrated signals.

## 2. Verified capabilities (evidence, not claims)

All numbers below come from real production runs (GitHub REST API, 2026-09-10):

| Capability | Evidence |
|---|---|
| Adversarial per-repo verification | 13/13 repos verified via single-request REST API (star / license / pushed_at / archived / forks) |
| Transcription-error detection | Caught a wrong repo name propagated by aggregator/OCR channels (`cathrynslavery` → `cathrynlavery`), 4th consecutive run with a caught error |
| License tri-state classifier | Permissive / review-required / high-risk, deliberately favors low false-positive rate |
| Maintenance signal (not "staleness") | Distinguishes "likely abandoned" from "possibly feature-complete" via issue-pressure heuristic |
| Category signal detection | Same-vertical ≥3 repos on one board → sector-level bet signal, output with an explicit maturity gate |
| Signal maturity & calibration | `experimental → validated (4 periods) → production (12 periods)`; unvalidated signals are flagged "not for business decisions" |
| Degradation honesty | Fetch/verify failures produce an explicit `DEGRADED` report and exit code 2 — never fabricated data |

## 3. Architecture (public layer)

```
Stage 1   Collect      github.com/trending parse (owner/repo, desc, stars, daily delta, lang)
Stage 2   Verify       API-first per-repo attestation; HTML parsing kept as rate-limit fallback
Stage 2.5 Risk flags    license tri-state + maintenance signal (abandoned vs stable-complete)
Stage 3   Grade        business-profile keyword scoring with weights → P0/P1/P2 + risk terms
Stage 3.5 Category      cross-repo signal aggregation with sample-size disclosure + maturity gate
Stage 4   Render       dark HTML daily review; explicit DEGRADED state; calibration history appended
```

Engineering discipline: **zero dependencies** (Python stdlib only, single file,
3.8+), polite rate limiting, idempotent runs, plain-JSON calibration ledger.

### 3.1 Maturity roadmap (where partners come in)

Signals earn trust on a fixed ladder, and the ladder is enforced in code, not
in marketing copy:

```
experimental  (periods 1–3)   signals displayed, gated "not for business decisions"
validated     (periods 4–11)  gates relaxed for partner-facing vertical reports
production    (periods 12+)   calibrated scoring API eligibility
```

The calibration ledger is append-only and auditable. **Design partners who
join during `experimental` directly shape which signal families get calibrated
next** — this is the cheapest and most influential time to collaborate.

## 4. Recent hardening: v2.1 (September 2026)

The engine was put through a five-round adversarial red-team/blue-team review
(hundreds of raised issues, 180 tracked patches, distilled down to what
survives falsification). Five patches are now merged into production code:

| Patch | What changed |
|---|---|
| License tri-state output | Binary "risky/safe" replaced by compliant / review-required / high-risk, biased toward low false-positives |
| Maintenance signal | "Stale" no longer equals "abandoned" — issue-pressure heuristic separates abandonment from feature-complete |
| Signal maturity gate | Unvalidated signals are machine-flagged as unfit for business decisions |
| Calibration ledger | Every run appends to an append-only JSON history — the seed of the long-term moat |
| Closed historical assets | The **production** calibration ledger is excluded from the public repo by design; the public repo instead runs a scheduled daily job (18:00 UTC+8) on the sanitized example profile, committing reports to `reports/` as a live, verifiable demo |

What the review **falsified and removed** is as instructive as what shipped:
a mass-market self-serve tier, "staleness = risk" scoring, and compliance-
tool positioning all failed adversarial testing and were cut. We ship
less, verified.

## 5. What collaboration unlocks (partner layer)

The public repository ships the engine. The following exist and run in
production, and are delivered under a collaboration agreement only:

1. **Profile tuning recipes** — industry-specific business-line keyword
   matrices and weight configurations (verticals covered: agent tooling,
   media/rendering pipelines, growth/martech, data acquisition).
2. **LLM deep-audit prompt library** — the adversarial per-repo interrogation
   templates behind the P0/P1/P2 narrative layer ("what to learn / how to
   surpass / compliance exposure").
3. **Calibration ledger access** — the historical signal dataset backing the
   maturity model, plus the upgrade path to a calibrated scoring API.
4. **Vertical report templates** — the paid pilot-report format used to
   validate willingness-to-pay in a target niche.
5. **Multi-source roadmap review** — architecture walkthrough for HN /
   ProductHunt / RSS connectors and the scan-budget scheduler design.

### 5.1 Engagement tiers

| Tier | Shape | What you get | What we ask |
|---|---|---|---|
| **Design Partner** | Free, feedback-for-access | Early vertical profile shaping; your niche calibrated first; direct line to the maintainer | A real use case, monthly feedback, honest "we stopped using it" if so |
| **Pilot Report** | $2K–5K per report | A decision-ready adversarial review of a vertical/space, delivered in ≤15 working hours | Payment upfront, one round of feedback |
| **Signal API** | Design-stage | Embedded pre-selection signal for CI / dependency tooling | Co-design conversation, integration case study rights |

We deliberately do not run a self-serve subscription tier. It was tested
adversarially and cut (see §4).

## 6. Anti-distillation & disclosure policy

This project publishes an engine, not a recipe. Five concrete measures:

### 6.1 Tiered disclosure
- **L1 public**: architecture, stage contracts, engineering discipline (this repo).
- **L2 evidence**: verified run results and sample outputs (this document, §2).
- **L3 partner-only**: weight matrices, thresholds, prompt library, calibration
  data, vertical templates. **Never published, never committed.**

### 6.2 Canary watermarks
Every authorized deliverable embeds a unique partner canary
(`CANARY-ZS-TS-<date>-<id>`). Public sample documents carry the generic token
above. If a distilled/derived model or document reproduces a canary, the
originating partner is identifiable — this is deterrence by traceability, not
DRM theater.

### 6.3 Non-production example parameters
All parameter values visible in public code and examples are demonstration
values. Production scoring profiles are structurally different (different
granularity, different thresholds) and are excluded from the repository by
design — there is nothing to distill from the public layer.

### 6.4 Contract-level output shape
Public docs describe **input → output contracts** (what a stage consumes and
emits), never the intermediate scoring internals. A distiller of this repo
can rebuild a worse clone of the skeleton; the calibration advantage is not
in the repository.

### 6.5 License terms
- Code: MIT (attribution required, nothing hidden).
- Documents (including this one): CC BY-NC-ND 4.0 **plus** an explicit clause
  prohibiting use of the content for training, fine-tuning, or distillation of
  machine-learning systems without written permission.

## 7. Who we are looking for, and why now

- **Vertical intelligence partners**: teams in security/SCA, DevRel, VC
  technical diligence, or OSS governance who want a verified trending-signal
  feed in their niche.
- **Pilot report clients**: organizations willing to commission 1–3 paid pilot
  reports ($2K–5K each) to validate fit before any larger commitment.
- **Integration partners**: CI / dependency-tooling vendors interested in an
  embedded pre-selection signal (design-partner stage).

**Why now:** the calibration ledger has just started accumulating (period 1).
Signal families that matter to the first design partners get calibrated
first; later entrants inherit a moat tuned to someone else's niche.

## 8. Operating commitments

- Maintainer time on open-source upkeep is capped (a few hours weekly) —
  issues get honest answers, not instant ones.
- Critical upstream outages (e.g., data-source API changes) target basic
  service recovery within 48 hours via caching and multi-source fallbacks.
- If this project ever shuts down, the public repo stays up and partners get
  3 months' notice. No dark landings.

## 9. Contact

hcac4735@agent.qq.com ｜ or open an Issue.

---

*Engineered and running in daily production use. If you fork or cite, keep
this notice and the canary token intact.*
