# Phase 6 — Implementation Status

**Status:** In progress, started 2026-10-09. Phase 5 approved by user.

## Implemented in this increment

- Pure domain rules for story stages, sequential chapters, final review, and the production KPI clock (`Asia/Ho_Chi_Minh`).
- Fail-closed mandatory gate/artifact checks. Mock artifacts are excluded from production KPI.
- Admission checks for daily target, pending final reviews, budget, pause/recovery status, and safe concurrency.
- Provider assignment/fallback and category-based Cloud Boundary checks.
- Initial SQLAlchemy tables for campaigns, stories, chapters, gate decisions, artifacts, and audit events.
- Durable task and task-attempt records with idempotent creation, one active worker lease, safe completion, and recovery hold requiring confirmation.
- Lite profile configuration, SQLite WAL/foreign-key/durability settings, local application-data default, atomic task claim, startup recovery queue, a single-worker database poller, and resource-based worker cap. The Standard profile remains a configuration target pending service integration.
- Offline, deterministic mock path: draft story → idempotent blueprint task with a synthetic Story Bible, 20 objectives and hook contract → sequential 20-chapter fixture task. Both results survive database reopen and remain separate from accepted story state and Production KPI.
- The mock CLI can process one task or keep polling with `--loop`. Concurrent task creation with the same idempotency key resolves to one task; reusing a key for another story or operation is rejected.
- A manual Lite SQLite snapshot command uses SQLite's online backup API, validates schema/integrity, and refuses to overwrite an existing backup file. This is a database snapshot only; full artifact/config backup is still pending.
- Mock text assets render `story.txt`, `hook.srt`, `caption.txt`, and `comment.txt` from the two validated checkpoints. The optional media path renders a valid 15-second 720×1280 `hook.mp4` with burned mock captions and synthetic tones, then checks duration, frame count, and dimensions. The package task exports exactly five files under `MOCK_OUTPUT`, checks copied checksums, and refuses to overwrite or silently replace an existing export. A retry after folder publication revalidates and reuses that folder. This is a technical workflow fixture, not production-ready creative media or real voice.
- A failed mock-package task may now be retried only by an explicit local API command, only while its frozen attempt limit has room. The retry is audited, keeps earlier attempt history, and cannot be applied to other task types or completed packages. This is not an automatic retry policy for production tasks.
- Initial Vietnamese Lite operator page at `/`: create a user-idea mock draft, inspect recent database-backed stories/task states, queue the next mock step, and request a bounded package retry. The separate Lite worker remains responsible for work after the browser closes. After package completion, the page can open/preview or download each of the five mock files through a story-scoped, checksum-verifying route; unknown names, out-of-root paths and tampered files fail closed. Full recovery controls are not yet in the UI.
- A one-click Windows local launcher now uses `sys.executable` for both API and worker, avoiding the machine's `uvicorn.exe` Python 3.11 versus `pip` Python 3.14 mismatch. It can bootstrap missing Lite media dependencies, opens localhost, and stops owned child processes together. The local API/worker and `/health`/dashboard were started successfully on the current PC. The prototype rejects non-local Host headers (observed 400 for a foreign host) and refuses startup when Render/Vercel environment flags are present; this is deliberate until authentication and persistent storage exist. Public-domain direction is Vercel frontend + Render API/worker, but deployment is not configured or safe yet; see `INSTALL_AND_PUBLIC_DEPLOYMENT.md`.
- Local-only sign-in now requires one of exactly two owner accounts, `Tou` or `Chibun`. The launcher reads their shared demo password from an ignored local `.env` file and creates salted hashes plus a random session signing secret in the local application-data directory. An older `Atus` auth file is moved to a uniquely named backup before replacement; no story database is changed. Dashboard and API commands require a signed session; there is a logout action and a basic per-process login-attempt limit. The shared three-digit demo password explicitly requested by the user is **trivially guessable**; the user has asked to retain it even for public access, but the app remains localhost-only and public deployment has not happened. HTTPS cookie handling, durable throttling, persistent storage, and hosting setup remain unresolved.
- API restart now holds expired task leases only, so restarting the API does not interrupt a worker whose lease is still valid. Recovery confirmation remains explicit.
- Frozen Alembic migration for those initial tables.
- Local API for health, draft campaign/story creation, story view, and guarded final review.
- 43 default tests pass (one opt-in HTTP test skipped), including local app-factory startup with owner auth, credential hashing and migration, the dashboard's database-backed story/task projection, checksum-gated file access, cloud-startup guard, complete five-file package construction, simulated failure after folder publication, explicit audited retry, and exhausted-attempt rejection. The opt-in separate-process HTTP test passed on the current 4 GB PC on 2026-10-09 with more than 1 GB RAM available **before** the new login increment; it now includes a login step but has not yet been rerun. A launcher attempt inside the tool sandbox on 2026-10-09 did not reach `/health` in 25 seconds; do not infer that the user-facing web was verified after this change. PostgreSQL, Alembic, RabbitMQ, and Windows boot startup remain unverified.

## Remaining before Phase 7 one-story test

1. Complete Phase 5 records: policy and assignment snapshots, provider/cost ledger, reference library, quality/fingerprint, output profile, and human operation tables. Extend tasks with stage-specific failure/retry policy and auditable lease history.
2. Supervise the optional looping Lite worker with restart/recovery controls; implement Standard RabbitMQ transport with PostgreSQL authoritative state later and test both with the same task contract.
3. Complete provider interfaces and production-grade video, voice, and audio paths; bounded Gemini prototype adapter under the approved non-sensitive Cloud Boundary. The current mock MP4 contains synthetic tones only.
4. Story Bible, chapter plan, continuity state, sequential generation, Hook–Story Contract, QC/originality gates, and artifact integrity checks.
5. Expand the Vietnamese dashboard with review/backpressure, manual publishing record, storage/backup/recovery controls, and a short operator guide.
6. Turn the successful one-story Lite dry run into an operator-supported workflow with bounded retries, recovery, full backup, and acceptance checks. Test PostgreSQL/RabbitMQ and verified data migration before Standard/public release.

No production model, paid provider, real media provider, automatic publishing, or daily budget cap has been approved.

See `PHASE_6_SAFE_CODE_CHECKLIST.md` for the pre-merge safety gates used for each increment.
