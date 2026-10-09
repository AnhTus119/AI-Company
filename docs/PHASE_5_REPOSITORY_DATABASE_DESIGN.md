# Phase 5 — Repository and Database Design

**Status:** Approved design baseline — 2026-10-09  
**Scope:** Repository/database design only; no schema migration, service code, model installation, or provider call is authorized.

**Persistence detail:** `PHASE_5_DATA_CONTRACTS.md` defines the table-level fields, constraints, task envelope, and required indexes for this baseline.
**Runtime profile revision:** `RESOURCE_PROFILES.md` adds SQLite WAL plus database polling for the 4 GB Lite profile. PostgreSQL/RabbitMQ remain the Standard profile. The logical records and business rules in this design apply to both.

## 1. Repository layout

```text
ai-content-company/
  apps/
    api/                 # FastAPI control plane
    worker/              # Dramatiq task entry points
    dashboard/           # React/Vite Vietnamese UI
  packages/
    domain/              # entities, state machine, canonical contracts
    application/         # commands, use cases, policy orchestration
    adapters/            # PostgreSQL, RabbitMQ, storage, provider adapters
    providers/           # OpenAI, Gemini, Ollama, mock media adapters
    policy/              # Cloud Boundary, budget, allowlists, safety gates
    export_profiles/     # versioned output renderers
  tests/
    unit/ integration/ contract/ e2e/ fixtures/
  docs/
  ops/                   # Windows service/health/backup design assets
  .env.example           # names only; never real keys
```

`domain` must not import FastAPI, database, queue, SDK, path, or provider code. Provider-specific code lives only in `providers` and implements contracts defined in `domain`.

## 2. Database conventions

- The selected database is authoritative. Transport messages or polling hints contain only identifiers/task metadata, never the sole workflow state.
- All primary records use UUIDs, UTC timestamps, and an optimistic version or lease/version where concurrent work matters.
- Store money in integer minor units with currency; durations in milliseconds; structured reports/config snapshots in versioned JSONB plus explicit searchable columns.
- Application state uses enumerated values controlled by the domain state machine. Delete is normally soft-delete/trash, never a hidden hard delete.
- Secrets never enter tables, task payloads, artifacts, reports, prompts, or audit-event metadata.

## 3. Core relational aggregates

| Aggregate | Primary tables | Notes |
|---|---|---|
| Campaign/intake | `campaigns`, `story_requests`, `campaign_constraints` | source type, target, daily timezone, admission status |
| Story creative state | `stories`, `story_versions`, `story_bibles`, `chapter_plans`, `chapters`, `continuity_states`, `foreshadowing_entries`, `hook_contracts` | accepted state/version lineage, sequential chapter rule |
| Workflow | `jobs`, `tasks`, `task_attempts`, `task_leases`, `checkpoints`, `failure_records` | durable state; tasks claim leases before work |
| Reference library | `reference_assets`, `reference_provenance`, `reference_analyses`, `reference_dna`, `reference_patterns` | raw media temporary by default |
| Governance | `policy_versions`, `policy_decisions`, `model_assignment_versions`, `model_assignments`, `provider_call_ledger`, `cost_ledger` | immutable snapshots/reasons per call |
| Quality/diversity | `qc_reports`, `gate_decisions`, `story_fingerprints`, `similarity_results` | no full text retained solely for diversity |
| Files/export | `artifacts`, `artifact_renditions`, `export_profiles`, `storage_objects`, `cleanup_actions`, `backup_exports` | logical identity separate from filesystem path |
| Human operations | `hook_reviews`, `final_reviews`, `publishing_records`, `operator_actions`, `audit_events` | final approval/publishing remain separate |

## 4. Key relationships and integrity rules

```text
campaign 1─* story_request 1─1 story 1─* story_version
story 1─1 story_bible; story 1─20 chapter_plan; story 1─20 chapter
story 1─1 hook_contract; story 1─* artifact; story 1─* qc_report
job 1─* task 1─* task_attempt; task 0..1─1 active lease
reference_asset 1─* analysis/pattern; story 0..*─* reference_dna
model_assignment_version 1─* provider_call_ledger; policy_version 1─* policy_decision
```

- A chapter cannot be accepted unless its plan belongs to the same story version and the preceding accepted chapter exists (except Chapter 1).
- Exactly 20 accepted chapter slots are required before final story QC.
- `production_ready` requires successful mandatory gate decisions and a checksum-valid required rendition set.
- A final review cannot alter the original `production_ready_at` or production-KPI event.
- A provider call ledger row references the frozen model-assignment and policy snapshots used at that moment.

## 5. Workflow persistence pattern

Each task has `status`, `eligible_at`, `attempt_no`, `max_attempts_snapshot`, `lease_owner`, `lease_expires_at`, input/output references, and correlation ID. A worker transactionally claims an eligible task. After work, it writes result/checkpoint/gate evidence first, then schedules any next task. Re-delivered RabbitMQ messages are harmless because the claim is idempotent.

Pause/stop/recovery are command events, not queue deletion. Backpressure is enforced during admission and before final-package creation, with running work allowed to reach a defined safe checkpoint.

## 6. Configuration hierarchy

```text
compiled safe defaults
  → versioned database policy/profile
  → campaign-specific allowed overrides
  → immutable job snapshot
```

Configuration includes storage roots, output profile, retention, safe concurrency, pending-review cap, provider allowlist, Cloud Boundary, budget cap, model assignments, and retry policy. Environment variables contain only deployment-specific connection/secrets values and override none of the historical policy snapshots.

## 7. Initial API surface

| Area | Commands/read models |
|---|---|
| Campaign | create/validate/start/pause/stop/continue; campaign summary and KPI projection |
| Reference | import/inspect/retention action; provenance and DNA views |
| Story/review | story timeline, artifact access, review/approve/reject/revise/stop |
| Operations | worker health, recovery decision, storage/trash/restore/pin, backup export |
| Configuration | draft/approve policy or assignment version; no secret readback |

All mutating commands create an audit event and return a command/result identity. The dashboard receives projections/events, never direct table ownership.

## 8. Test-fixture design

- Synthetic StoryRequest and reference-free Story Bible/plan/chapter fixtures.
- Mock providers with deterministic success, timeout, malformed-schema, quota, and policy-denied responses.
- Temporary local artifact store for checksum/export/corruption cases.
- Isolated PostgreSQL and RabbitMQ integration environment; no real provider key in automated tests.
- Contract fixtures validate canonical provider results against each adapter and preserve original failure classification.

## 9. Phase 5 exit criteria

Before implementation, approve: final module names, schema/migration plan, task/message envelope, configuration schema, local storage URI conventions, API/OpenAPI contract draft, and test-fixture strategy. Exact provider/model assignments, production budget, real media services, and final QC thresholds remain intentionally open.
