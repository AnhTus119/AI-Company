# Phase 6 — Implementation Status

**Status:** In progress, started 2026-10-09. Phase 5 approved by user.

## Implemented in this increment

- Pure domain rules for story stages, sequential chapters, final review, and the production KPI clock (`Asia/Ho_Chi_Minh`).
- Fail-closed mandatory gate/artifact checks. Mock artifacts are excluded from production KPI.
- Admission checks for daily target, pending final reviews, budget, pause/recovery status, and safe concurrency.
- Provider assignment/fallback and category-based Cloud Boundary checks.
- Initial SQLAlchemy tables for campaigns, stories, chapters, gate decisions, artifacts, and audit events.
- Immutable approval records for policy and model-assignment versions, plus provider-call and cost ledgers tied to a durable task attempt. A provider call cannot start until both snapshots are approved/active; completion is one-way, uses redacted error codes, records usage/latency, and rejects credential-shaped ledger fields.
- Daily budget policy/reservation/settlement is enforced before external work. The bounded OpenAI Responses and Gemini REST adapters remain disabled by default. An explicitly approved `story_architect` route can use either as primary/fallback, recording every attempt, model, fallback reason, usage, latency and cost. A completed real blueprint can materialize into an auth-free native local Novel Workspace with characters, 20 outlines, chapter drafts, continuity/open loops and foreshadow tracking. Optional MuMuAINovel export/push remains isolated. This does not yet generate the 20 chapter bodies inside AI Company.
- Durable task and task-attempt records with idempotent creation, one active worker lease, safe completion, and recovery hold requiring confirmation.
- Lite profile configuration, SQLite WAL/foreign-key/durability settings, local application-data default, atomic task claim, startup recovery queue, a single-worker database poller, and resource-based worker cap. The Standard profile remains a configuration target pending service integration.
- Offline, deterministic mock path: draft story → idempotent blueprint task with a synthetic Story Bible, 20 objectives and hook contract → sequential 20-chapter fixture task. Both results survive database reopen and remain separate from accepted story state and Production KPI.
- The mock CLI can process one task or keep polling with `--loop`. Concurrent task creation with the same idempotency key resolves to one task; reusing a key for another story or operation is rejected.
- A manual Lite SQLite snapshot command uses SQLite's online backup API, validates schema/integrity, and refuses to overwrite an existing backup file. This is a database snapshot only; full artifact/config backup is still pending.
- Mock text assets render `story.txt`, `hook.srt`, `caption.txt`, and `comment.txt` from the two validated checkpoints. The optional media path renders a valid 15-second 720×1280 `hook.mp4` with burned mock captions and synthetic tones, then checks duration, frame count, and dimensions. The package task exports exactly five files under `MOCK_OUTPUT`, checks copied checksums, and refuses to overwrite or silently replace an existing export. A retry after folder publication revalidates and reuses that folder. This is a technical workflow fixture, not production-ready creative media or real voice.
- A failed mock-package task may now be retried only by an explicit local API command, only while its frozen attempt limit has room. The retry is audited, keeps earlier attempt history, and cannot be applied to other task types or completed packages. This is not an automatic retry policy for production tasks.
- Initial Vietnamese Lite operator page at `/`: create a user-idea mock draft, inspect recent database-backed stories/task states, queue the next mock step, and request a bounded package retry. The separate Lite worker remains responsible for work after the browser closes. After package completion, the page can open/preview or download each of the five mock files through a story-scoped, checksum-verifying route; unknown names, out-of-root paths and tampered files fail closed. Full recovery controls are not yet in the UI.
- A one-click Windows local launcher uses `sys.executable` for both API and worker, can install missing Lite media dependencies, opens localhost, and stops owned child processes together. It requires Python 3.12+ on PATH, but not VS Code or an API key. Authentication and the Render/Vercel demo were removed per the owner's latest direction. The API rejects non-local Host headers and cloud startup. See `LOCAL_INSTALL.md`.
- The localhost dashboard has no login screen. This is a convenience choice for personal-machine use, not a security boundary: anyone with access to the running machine/localhost API can use it. Do not expose port 8000 to the LAN or Internet.
- API restart now holds expired task leases only, so restarting the API does not interrupt a worker whose lease is still valid. Recovery confirmation remains explicit.
- Frozen Alembic migration for those initial tables.
- Local API for health, draft campaign/story creation, story view, and guarded final review.
- Automated tests cover dashboard state, file integrity, cloud-startup guard, mock package construction/retry, Lite schema upgrades, budget enforcement, provider contract, real-blueprint orchestration, and governance/provider-cost ledgers. On 2026-10-09 the current revision passed **52 default tests, with 1 opt-in HTTP test skipped**; `launch_local.py --check` and the no-network provider-setup smoke test also passed. A separate opt-in HTTP rerun was skipped because the test process saw less than 768 MB RAM available. The user's real double-click and first authorized Gemini call still need confirmation. PostgreSQL, RabbitMQ, and Windows startup on a fresh PC remain unverified.

## Remaining before Phase 7 one-story test

1. Complete the remaining Phase 5 records: reference library, quality/fingerprint, output profile, and human operation tables. Extend the new policy/assignment/provider-cost slice with operator commands and per-workload budget enforcement, then extend tasks with stage-specific failure/retry policy and auditable lease history.
2. Supervise the optional looping Lite worker with restart/recovery controls; implement Standard RabbitMQ transport with PostgreSQL authoritative state later and test both with the same task contract.
3. Complete provider interfaces and production-grade video, voice, and audio paths; bounded Gemini prototype adapter under the approved non-sensitive Cloud Boundary. The current mock MP4 contains synthetic tones only.
4. Story Bible, chapter plan, continuity state, sequential generation, Hook–Story Contract, QC/originality gates, and artifact integrity checks.
5. Expand the Vietnamese dashboard with review/backpressure, manual publishing record, storage/backup/recovery controls, and a short operator guide.
6. Turn the successful one-story Lite dry run into an operator-supported workflow with bounded retries, recovery, full backup, and acceptance checks. Test PostgreSQL/RabbitMQ and verified data migration before Standard/public release.

No production model, paid provider, real media provider, automatic publishing, or daily budget cap has been approved.

See `PHASE_6_SAFE_CODE_CHECKLIST.md` for the pre-merge safety gates used for each increment.
