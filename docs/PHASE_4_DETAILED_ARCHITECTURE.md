# Phase 4 — Detailed Architecture

**Status:** Approved architecture baseline — resource profile revision 2026-10-09  
**Runtime profile note:** `RESOURCE_PROFILES.md` supersedes PostgreSQL/RabbitMQ-only topology and Windows process assumptions for the first 4 GB deployment.
**Scope:** Detailed design only. No implementation code, provider installation, paid API use, or production model assignment is authorized by this document.

## 1. Architecture objectives and invariants

The system is a local-first Windows production control system. The selected profile's database is authoritative for all business state; its transport only schedules eligible work. Local artifact storage holds files; workers may run while the dashboard is closed.

The following are non-negotiable:

1. No provider/model name is embedded in creative workflow logic.
2. Every external call is checked by Cloud Boundary, provider allowlist, budget, rate-limit, and assignment policy before it is made.
3. A package cannot become `production_ready` without all required gates, artifact integrity checks, and an audit trail.
4. Production, approval, and publishing KPIs remain separate.
5. Restart recovery requires explicit human confirmation before production resumes.
6. Reference material yields abstract DNA only; it must never be used to reproduce a source work.

## 2. Logical topology

```text
Vietnamese dashboard
        │ HTTPS/localhost + WebSocket updates
        ▼
FastAPI control plane ───────────── PostgreSQL (authoritative state)
        │                                      │
        │ validate command / create task        │ policies, audit, leases,
        ▼                                      │ costs, QC, approvals
RabbitMQ ──────────────── Dramatiq worker fleet ┘
        │
        ├─ intake/reference worker
        ├─ creative/story worker
        ├─ hook/media mock worker
        ├─ QC/originality worker
        └─ maintenance/export worker

Local storage abstraction: temporary media | cache | final packages | trash | backup
Provider adapters: OpenAI API | Gemini API | Ollama local | future adapters
```

The control plane owns commands, policy decisions, state transitions, review APIs, and dashboard projections. Workers never invent state transitions: they claim a durable task lease, execute one bounded task, persist a result, and request the next permitted transition.

## 3. Module boundaries

| Module | Responsibility | Must not own |
|---|---|---|
| Campaign service | Presets, intake, daily target, admission/backpressure | Provider-specific prompts or credentials |
| Workflow service | State machine, task creation, leases, retry/failure routing | Queue delivery guarantees |
| Policy engine | Budget, Cloud Boundary, safety, provider allowlist, approval limits | Creative prose generation |
| Provider registry | Registered adapters, capabilities, health and availability | Assignment authority |
| Assignment policy | Versioned workload → primary/fallback/escalation choice | Secrets or mutable job history |
| Story service | Concept, Bible, plan, sequential chapters, continuity state | Direct network/provider calls |
| Reference service | Ingest, provenance, normalization, DNA/pattern reports | Storage retention decisions outside policy |
| QC/originality service | Reports, critical gates, fingerprints, diversity comparison | Final human approval |
| Artifact/export service | Immutable artifact records, checksums, Output Profile export | Business workflow authority |
| Review/publishing service | Human decisions, manual publishing record | Automatic external posting |
| Cleanup/backup service | Retention, trash/restore, non-secret export | Deleting protected artifacts without policy |

## 4. Provider and model portability

### 4.1 Stable internal contracts

Every adapter converts a provider-specific request/result into a canonical internal contract:

| Contract | Required result |
|---|---|
| `TextGeneration` | text, structured object when requested, usage, latency, provider/model identity |
| `MultimodalAnalysis` | evidence, timestamps where available, confidence, normalized analysis object |
| `Embedding` | vector(s), embedding model/version, dimensions, usage |
| `VideoGeneration` / `VoiceGeneration` / `AudioAsset` | deferred in MVP; output manifest, provenance, checksum, timing/asset metadata |

No downstream service consumes a raw provider response. Canonical schemas are versioned; new provider-only features are optional capabilities, not implicit assumptions.

### 4.2 Assignment lifecycle

```text
candidate registered
  → bounded one-story trial
  → evidence recorded
  → user approval
  → assignment version activated for new jobs
  → retired when replaced (old job history remains immutable)
```

An assignment has: workload, primary, allowed fallbacks, optional escalation path, capability requirements, effective date, approval record, and policy version. A job snapshots this data at admission. Changing an assignment never rewrites previous jobs.

### 4.3 Prototype classifications

- ChatGPT Free: manual comparison only; never a browser-automated provider.
- Gemini API Free: quota-limited cloud candidate, only after Cloud Boundary approval.
- Ollama + Qwen3: local candidate. On the current prototype PC, only a very small model is suitable for adapter smoke tests; 4B/8B are deferred until hardware is upgraded or a different machine is available.
- Muse.ai: external personal agent/product reference, not a pipeline model provider.
- MuMuAINovel: source-code review candidate, not a provider; no import before license/dependency review.

## 5. Core durable records

| Aggregate | Essential records |
|---|---|
| Campaign | campaign, source mode, target, constraints, admission status, KPI-day timezone |
| Story | StoryRequest, concept, Story Bible, chapter plan, Hook–Story Contract, accepted state, version lineage |
| Workflow | job, task, task lease, attempt, checkpoint, failure classification, pause/stop/recovery decision |
| Reference | reference asset, provenance, normalized temporary asset, Unified DNA, per-reference pattern report |
| Governance | policy snapshot, model assignment snapshot, provider call ledger, cost ledger, Cloud Boundary decision |
| Quality | QC report, gate decision, originality report, StoryFingerprint, diversity comparison |
| Artifact | artifact record, checksum, classification, retention/pin/trash status, export-profile version |
| Human operation | hook review, final approval, publishing record, operator action, audit event |

Every mutable record has timestamps, actor (`operator`, `system`, or `worker`), correlation ID, and optimistic version/lease safeguards. Draft prose and temporary raw media follow retention policy; final outputs and historical reports do not.

## 6. Story workflow state machine

```text
draft → admitted → reference_analysis? → concept → story_bible → chapter_plan
      → hook_contract → chapters_sequential → hook_media → metadata
      → automated_gates → final_package_ready → production_ready
      → awaiting_final_review → approved | human_rejected
```

`reference_analysis?` is mandatory only for reference-bearing source modes. `production_ready` is assigned once, immediately after required automated gates pass; later final review does not change it.

Terminal or hold states include `paused`, `stopped`, `awaiting_recovery_confirmation`, `technical_failure`, `quality_failure`, `originality_failure`, `policy_failure`, and `needs_review`. A replacement story is a distinct StoryRequest with its own fingerprint and lineage reason.

### Admission rules

Admission is denied when the campaign is stopped/paused, its daily target is reached unless Continue is selected, `max_pending_approval` is full, or policy/budget conditions prevent safe work. In-flight tasks finish only to their safe checkpoint when pause/stop/backpressure begins.

### Sequential chapter rule

For each chapter, the worker reads the approved Bible, chapter objective, prior accepted chapter state, unresolved-thread list, and foreshadowing ledger. It writes the new chapter plus a proposed state delta. Only accepted deltas update Continuity Memory and permit the next chapter.

## 7. Gates and policy decision order

Before an external provider call:

1. Confirm job/task lease and permitted workflow state.
2. Load the immutable assignment snapshot and verify required capabilities.
3. Apply provider/category Cloud Boundary rules and minimum-data reduction.
4. Check allowlist, provider availability, rate limit, and estimated remaining budget.
5. Persist an intent/audit event, then invoke the adapter.
6. Persist usage/cost/result metadata, redact secrets, and evaluate the task gate.

Critical gates are deterministic decisions over structured reports: safety, originality/reference boundary, Hook–Story–Chapter 1 continuity, severe contradiction, budget/policy, and final artifact integrity. LLM evaluators may supply evidence and scores but cannot override a hard failure.

## 8. Reference, originality, and diversity design

Raw references are copied to managed temporary storage, normalized, checksummed, and linked to provenance. Analysis produces two durable products: per-reference pattern reports and a Unified Reference DNA. Both describe abstract principles and evidence, never source-specific creative material for regeneration.

The originality service compares a candidate's structured fingerprint and semantic similarity data against Reference DNA constraints and historical StoryFingerprints. It returns `pass`, `warning`, `critical_fail`, or `needs_review`, with evidence and policy version. It must not depend on retaining full prior chapters or raw reference media solely for diversity.

## 9. Artifacts, export, and storage lifecycle

Artifact identities are independent of their paths. Output Profile v1 renders the five required files: `hook.mp4`, `hook.srt`, `story.txt`, `caption.txt`, and `comment.txt`. A profile change creates a new export rendition and does not invalidate the canonical story or prior package.

Each artifact has a checksum, content classification, source task, retention class, pin/protection state, and storage location. Cleanup moves eligible items to trash first where practical. Final/pinned outputs require an explicit protected-data policy decision before removal. Backup exports include database and non-secret configuration/history/manifests, but exclude keys, `.env`, credentials, and raw references.

## 10. Windows runtime and recovery

The design has separate Windows-started processes for the control plane, worker pool, PostgreSQL, and RabbitMQ, with health checks collected by the dashboard. A browser is only a client.

At startup, the recovery coordinator finds expired task leases and unfinished checkpoints, marks affected jobs `awaiting_recovery_confirmation`, and presents a concise operator decision. No campaign resumes automatically. After confirmation, idempotent tasks either retry from a checkpoint or are classified for review; export writes use staging plus atomic finalization/checksum verification to avoid partial packages.

## 11. Operator-facing projections

The Vietnamese dashboard exposes:

- daily Production/Approval/Publishing KPI cards with their different definitions;
- campaign start, pause, stop, Continue, and safe-concurrency status;
- a final-review queue capped at ten;
- per-story timeline, QC/originality summaries, cost/provider/fallback history, and artifact controls;
- manual Facebook assistance only: open output, copy caption/comment, mark publishing status;
- storage/cleanup, pin/restore/trash, and non-secret backup export;
- recovery prompt and worker/provider health without exposing secrets.

## 12. Prototype test protocol

Before any production assignment, run one StoryRequest per candidate with mock media providers. The test records model/provider/version, schema-validity rate, prose quality, continuity and QC outcome, latency, local CPU/RAM observations or cloud quotas, token/usage data where available, and Cloud Boundary/data-handling notes.

The current PC is an Intel Core i3-1115G4 (2 cores/4 logical processors), 4 GB RAM, Intel UHD integrated graphics, and approximately 72 GB free SSD storage. RAM was already 97% used during the supplied check. Therefore the initial local trial is limited to Ollama + Qwen3 0.6B (or equivalently small model) as an adapter/structured-output smoke test only; it is not a candidate for full 20-chapter production quality. Qwen3 4B/8B are deferred until there is materially more available RAM or a different machine. Gemini Free is the preferred quality-evaluation candidate, subject to Cloud Boundary approval. A failed candidate is retained as trial evidence, not silently used as fallback.

## 13. Phase 5 handoff

Phase 5 will turn these aggregates into a repository layout, database schema/migrations, message/task envelope, API contracts, configuration hierarchy, and test-fixture plan. It must preserve this document's invariants and must not introduce implementation code until the implementation phase is authorized.

## 14. Decisions still needed

1. Whether Gemini Free-tier data handling is acceptable for non-sensitive prototype inputs.
2. MuMuAINovel source/ZIP location and license, if it is to be evaluated.
3. Whether the prototype PC can be upgraded to at least 16 GB RAM, or whether a stronger machine will be used for later local-model trials.
4. Later: exact provider/model approvals, QC thresholds, retry counts, budget cap, real media providers, and production scaling benchmarks.
