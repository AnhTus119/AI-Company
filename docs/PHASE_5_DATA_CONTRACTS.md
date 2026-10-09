# Phase 5 — Data Contracts and Persistence Detail

**Status:** Approved design baseline — 2026-10-09  
**Companion:** `PHASE_5_REPOSITORY_DATABASE_DESIGN.md`
**Profile mapping:** PostgreSQL uses UUID/TIMESTAMPTZ/JSONB. The Lite SQLite schema maps these to portable UUID, UTC datetime, and JSON representations; invariants are enforced by shared domain rules and compatible database constraints.

## 1. Common columns

Every durable primary record has `id UUID`, `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ`, `created_by`, `correlation_id UUID`, and `row_version INTEGER`. Business records additionally use `deleted_at` only where soft deletion is permitted. Times are stored in UTC; a campaign stores its KPI timezone separately.

No table may contain an API key, OAuth token, credential value, raw secret, or unredacted provider authorization header.

## 2. Intake and story records

| Table | Essential fields | Key constraints |
|---|---|---|
| `campaigns` | name, source_type, target_count, kpi_timezone, status, requested_concurrency, safe_concurrency_snapshot, policy_version_id | target > 0; source type is `reference`, `user_idea`, `reference_user_idea`, or `autonomous` |
| `story_requests` | campaign_id, source_type, idea_payload JSONB, constraint_payload JSONB, requested_at, admission_status | source-specific required data validated before admission |
| `stories` | story_request_id, campaign_id, current_version_id, workflow_state, production_ready_at, replacement_of_story_id | one story per request; production-ready timestamp immutable once set |
| `story_versions` | story_id, version_no, lineage_reason, status, title, accepted_at | unique `(story_id, version_no)`; only one current accepted version |
| `story_bibles` | story_version_id, schema_version, payload JSONB, validation_status, accepted_at | one accepted Bible per story version |
| `chapter_plans` | story_version_id, chapter_no, objective, planned_reveal, planned_open_loop, payload JSONB | unique `(story_version_id, chapter_no)`; 1–20 only |
| `chapters` | story_version_id, chapter_no, title, recap, content_artifact_id, accepted_state_version, status | chapter 1 recap is null; chapter 2–20 recap is required; unique slot 1–20 |
| `continuity_states` | story_version_id, state_version, payload JSONB, accepted_through_chapter | unique `(story_version_id, state_version)`; accepted chapter never decreases |
| `foreshadowing_entries` | story_version_id, identifier, planted_chapter, planned_payoff_chapter, actual_payoff_chapter, status | planted/payoff chapters must be 1–20 |
| `hook_contracts` | story_version_id, event, facts JSONB, stakes, open_loop, chapter_1_handoff, payoff_plan, status | one active contract per accepted story version |

## 3. Workflow records

| Table | Essential fields | Key constraints |
|---|---|---|
| `jobs` | story_id, job_type, status, policy_snapshot_id, assignment_snapshot_id, started_at, completed_at | state transitions validated by domain state machine |
| `tasks` | job_id, task_type, status, idempotency_key, eligible_at, attempt_limit, checkpoint_id, payload_ref | unique idempotency key; queue payload only carries task ID/correlation ID |
| `task_attempts` | task_id, attempt_no, started_at, ended_at, outcome, error_class, result_ref | unique `(task_id, attempt_no)` |
| `task_leases` | task_id, worker_id, claimed_at, expires_at, released_at | partial unique active lease per task; only unexpired lease can write task completion |
| `checkpoints` | task_id, sequence_no, checkpoint_type, state_ref, safe_to_pause | unique `(task_id, sequence_no)` |
| `failure_records` | job_id, task_id, classification, reason_code, details_redacted JSONB, resolved_at | classification is technical, quality, originality, policy, or needs_review |

## 4. Governance and provider ledger

| Table | Essential fields | Key constraints |
|---|---|---|
| `policy_versions` | version, status, approved_at, approved_by, policy JSONB | immutable after approval |
| `policy_decisions` | policy_version_id, subject_type/id, decision_type, outcome, reason_codes, evidence_ref | append-only audit evidence |
| `model_assignment_versions` | version, status, effective_at, approved_at, assignments JSONB | immutable after activation; only explicit user approval activates |
| `model_assignments` | assignment_version_id, workload, provider_key, model_key, role, capability_requirements JSONB | role is primary, fallback, or escalation; no provider/model IDs in domain logic |
| `provider_call_ledger` | task_attempt_id, assignment_version_id, policy_version_id, provider_key, model_key, workload, status, requested_at, completed_at, latency_ms, usage JSONB, redacted_error | append-only; records fallback/escalation rationale |
| `cost_ledger` | provider_call_id, currency, estimated_minor, actual_minor, rate_card_version, budget_decision_id | integer minor currency units only |

## 5. Quality and reference records

| Table | Essential fields | Key constraints |
|---|---|---|
| `reference_assets` | managed_artifact_id, format, source_status, analysis_status, checksum, imported_at | raw reference defaults to temporary retention |
| `reference_provenance` | reference_asset_id, platform, original_url, creator_note, rights_note, local_source_locator_redacted | source data not used as creative material |
| `reference_dna` | reference_set_id, scope, schema_version, payload JSONB, created_from_analysis_id | scope is unified or per-reference; abstract principles only |
| `reference_patterns` | reference_asset_id, category, evidence JSONB, abstraction JSONB | cannot store reusable source dialogue/sequence as generation input |
| `qc_reports` | story_id, story_version_id, scope, rubric_version, severity, report JSONB, generated_at | scope includes Bible, chapter, hook, final_story, overall |
| `gate_decisions` | story_id, gate_name, outcome, policy_version_id, evidence_refs JSONB, decided_at | mandatory gate failures prevent production-ready transition |
| `story_fingerprints` | story_id, story_version_id, schema_version, fields JSONB, embedding_ref, created_at | no full chapter content solely for diversity |
| `similarity_results` | subject_fingerprint_id, comparison_type, comparison_ref, score, outcome, evidence JSONB | retains similarity evidence and versions |

## 6. Artifact and human-operation records

| Table | Essential fields | Key constraints |
|---|---|---|
| `storage_objects` | storage_uri, checksum, byte_size, media_type, retention_class, trash_at, pinned_at | URI is an implementation-neutral storage URI, not a hard-coded user path |
| `artifacts` | story_id, artifact_type, canonical_version, storage_object_id, source_task_id, checksum | one active canonical artifact per type/version |
| `artifact_renditions` | artifact_id, export_profile_version, storage_object_id, format, integrity_status | required Output Profile v1 set is hook MP4/SRT, story TXT, caption TXT, comment TXT |
| `export_profiles` | profile_key, version, status, definition JSONB | versioned; never changes completed rendition meaning |
| `cleanup_actions` | storage_object_id, action, reason, requested_by, executed_at, restore_until | protected/pinned items need an explicit policy decision |
| `backup_exports` | requested_at, completed_at, storage_object_id, manifest_artifact_id, status | manifest excludes secrets and raw references |
| `hook_reviews` | story_id, status, opened_at, countdown_started_at, decision_at, feedback | opening/rejecting/pausing stops automatic countdown |
| `final_reviews` | story_id, decision, feedback, reviewer, decision_at | does not modify production KPI history |
| `publishing_records` | story_id, platform, status, published_at, external_id_or_url, caption_version, notes | manual entry only in MVP |
| `audit_events` | actor_type, action, entity_type/id, before_ref, after_ref, outcome, details_redacted | append-only; no secrets |

## 7. Task message envelope

RabbitMQ transports a compact, versioned envelope—not workflow state or creative material:

```json
{
  "schema_version": 1,
  "task_id": "UUID",
  "job_id": "UUID",
  "correlation_id": "UUID",
  "task_type": "generate_chapter",
  "not_before": "UTC timestamp",
  "delivery_attempt": 1
}
```

On receipt, the worker loads state from PostgreSQL, claims the task lease, re-runs policy checks, and only then reads permitted artifacts. Duplicate or late delivery is acknowledged without duplicate work when a task is completed, held, cancelled, or actively leased.

## 8. Required indexes and projections

- Admission: campaign status, KPI timezone/date, pending-final-review count, eligible story requests.
- Worker claims: `tasks(status, eligible_at)` with an active-lease exclusion check.
- Review queue: `stories(workflow_state, production_ready_at)` and undecided `final_reviews`.
- Audit/provider history: `provider_call_ledger(task_attempt_id)`, `audit_events(entity_type, entity_id, created_at)`.
- Cleanup: `storage_objects(retention_class, pinned_at, trash_at)`.
- Similarity: explicit fingerprint dimensions and model-version fields before selecting a vector index implementation.

## 9. Implementation guardrails for Phase 6

1. Migrations must create constraints before worker functionality that relies on them.
2. Provider adapters return canonical contracts; raw responses are stored only as redacted, retention-governed diagnostics if explicitly allowed.
3. `production_ready` is a transactionally guarded state transition that verifies gates and rendition checksums.
4. No migration or fixture may contain a real secret, raw reference media, or a copied reference transcript.
