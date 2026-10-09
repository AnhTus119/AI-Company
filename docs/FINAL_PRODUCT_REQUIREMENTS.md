# AI Content Company — Final Product Requirements

**Status:** Phase 2 draft for user approval  
**Project mode:** local-first orchestration with controlled cloud AI compute  
**Out of scope here:** technology selection, implementation planning, code, provider selection, and license selection.

## 1. Final Product Requirements

### 1.1 Product purpose

The product is an autonomous AI content-production system for English-language drama content. It turns local reference video files, user ideas, or autonomous campaign briefs into original, quality-controlled production packages. It is not a general chatbot and it must not copy reference material.

Each completed MVP package is represented internally as structured artifacts and exported through a versioned Output Profile. The initial output profile exports:

- `hook.mp4` — vertical hook video with burned-in English captions.
- `hook.srt` — separate English subtitle file.
- `story.txt` — reader-facing story.
- `caption.txt` — Facebook post caption.
- `comment.txt` — first-comment CTA.

The default delivery layout is human-readable, for example:

```text
OUTPUT/
  2026-10-05__STORY-0001__the-last-promise/
    hook.mp4
    hook.srt
    story.txt
    caption.txt
    comment.txt
```

This layout is an Output Profile v1, not a permanent assumption of the production pipeline.

### 1.2 Core content requirements

- All creative content is English-only: story, chapters, hook dialogue, transcripts, subtitles, captions, comments, and creative AI feedback.
- The niche is drama for a general English-speaking adult Facebook audience, primarily 18+, without country-specific targeting in MVP.
- A story has exactly 20 text-only chapters.
- Each chapter targets 500–700 words, with balanced reading experience and mobile-friendly pacing.
- Prose is easy to read, emotionally strong, uses medium-length sentences, and is suitable for phone reading.
- A chapter has a title, a short recap, and chapter text. Chapter 1 has no recap; Chapters 2–20 have spoiler-safe recaps of prior known state only.
- `story.txt` contains only the story title, optional table of contents, chapter titles, recaps where applicable, and chapter text. It must not expose internal metadata, prompts, QC scores, cost, provider/model information, or fingerprints.
- The normal cast guideline is at most 3–4 main characters and 3–4 supporting characters. The system may exceed it only when justified by the story and without confusing readers.
- Endings rotate under diversity controls among satisfying/justice payoff, bittersweet closure, and twist/shocking endings. The core conflict must receive closure.

### 1.3 Safety and content policy

- Characters and stories are fictional/AI-generated.
- Child-centered drama involving children aged roughly 3–8 is a primary pattern, but not mandatory for every story or hook.
- Non-graphic physical abuse may be depicted; minor scratches/trails of blood are allowed. Gore and detailed injury depiction are not allowed.
- No sexual content, sexualization, or exploitation of minors.
- Limit profanity, self-harm, politics, religion, hate content, and other moderation-risk content.
- Drama, suspense, relationship conflict, betrayal, mystery, and emotional conflict must not rely on graphic violence, explicit sexual content, or hate to make hooks effective.
- Audio must not use recognizable reference music, unauthorized commercial music, clipping/excessively loud sound, dialogue-obscuring music, or gratuitous jump-scare audio.

### 1.4 Story creation modes

`StoryRequest.source_type` supports:

| Source type | Required input | Reference DNA use |
|---|---|---|
| `reference` | One or more local reference files | Required/generated |
| `user_idea` | User idea | Optional |
| `reference_user_idea` | Local references and user idea | Required/generated |
| `autonomous` | Policy/diversity history and optional campaign brief | Optional |

The user-idea form supports a free-text premise plus optional theme, protagonist, antagonist, child character/age, setting, desired hook event, ending preference, drama intensity, forbidden elements, reference files, and visual-style preference. It will also support lightweight idea-list import: one seed per line, with validation. A campaign may create one story per seed or diversify a smaller set of seeds to reach a larger target.

### 1.5 Reference workflow

- MVP accepts user-provided local MP4, MOV, and WebM files; it does not automatically download Facebook, TikTok, or Instagram URLs.
- Files are copied temporarily to managed storage and normalized before analysis.
- Configurable safety/resource defaults are 500 MB per video, 10 minutes per video, and five videos per reference set.
- A Reference Library stores provenance and long-term Reference DNA/analysis metadata, not raw reference media by default.
- Provenance includes platform, original URL, creator/source note, rights/use note, local file path/ID, import time, and analysis status.
- A multi-video reference set yields both a Unified Reference DNA and a per-reference pattern library.
- The Unified DNA covers visual and audio patterns plus narrative mechanics, hook mechanics, emotional progression, pacing, curiosity gaps, open loops, and retention mechanisms.
- Reference analysis extracts abstract reusable principles; it must not reproduce reference-specific characters, dialogue, visual identity, sequence, setting, or distinctive structure.
- When rights/use status is unclear, the system may perform abstract analysis, stores a warning, and applies stricter originality constraints.

### 1.6 Story Bible, hook, and continuity

Before chapters are generated, every story must have a Story Bible and 20-chapter arc/plan containing characters, relationships, timeline, conflicts, secrets, foreshadowing, reveals, emotional arcs, ending, and chapter objectives.

The 13–17 second hook is **Chapter 0**. It must be built with a Hook–Story Contract containing the hook event, facts, stakes, open loop, Chapter 1 handoff, and planned payoff. A Hook → Story Continuity Gate must pass before the package can become production-ready.

Chapter generation is sequential, not 20 independent jobs. Each chapter uses the Story Bible, chapter objective, approved prior state, continuity memory, unresolved threads, and foreshadowing ledger.

### 1.7 Hook requirements

- Duration: 13–17 seconds.
- Default format: 9:16 vertical, 720×1280.
- The first three seconds must create a compelling question, curiosity, or tension signal, but no single rigid formula is imposed. The AI may choose immediate conflict, dialogue, reveal, mystery, emotional reaction, unexplained event, or another approved pattern.
- Hook content uses character dialogue only, with a maximum of three speaking voices.
- Voice characteristics come from the Story Bible. Approved default voice profiles may be used when no special profile is needed.
- Character face, body, age, clothing, environment, important props, lighting, and context must remain consistent within the hook except for intentional transitions.
- Visual Style Profiles may use abstract Reference DNA principles while avoiding distinctive reference identity.
- English burned-in captions and a separate SRT file are required. Captions use vertical safe areas, high contrast, mobile-readable timing, and at most two lines. Font/color/animation remain configurable.
- Music/SFX are optional and used only when they improve storytelling. Silence is permitted.

### 1.8 Provider and cloud boundaries

The system uses provider abstractions for LLM, video, voice, audio assets, and composition/rendering. Mock Video, Voice, and Audio Asset providers are required for MVP pipeline testing. Remotion is only a future candidate for composition/rendering after raw media assets exist; it is not an AI video generator.

Hybrid-cloud policy:

- Text prompts, stories, and task-relevant metadata may use approved cloud AI.
- Raw reference video may be sent only to designated multimodal providers when needed for analysis; it must not be repeatedly uploaded without need.
- Raw/final media assets may be sent only to scoped TTS, video, or render providers that require them.
- API keys, credentials, job database/state, internal configuration, cost/account data, and system controls remain local-only.
- A Data Classification / Cloud Boundary policy layer enforces category- and provider-level permissions before any provider call and applies least-necessary-data rules.
- Users can disable cloud processing by category or provider in the future.

### 1.9 Operations, KPI, approval, and publishing

The system uses persistent local orchestration, queue/state/storage/control. It runs while the Windows PC is on even if the browser/dashboard is closed.

Production KPI and approval/publishing metrics are intentionally separate:

| Metric | Definition |
|---|---|
| Production KPI | Packages that first become `production_ready` during the 00:00–23:59 Asia/Ho_Chi_Minh calendar day |
| Approval KPI | Packages human-approved/rejected during the relevant period |
| Publishing KPI | Packages manually marked published during the relevant period |

The daily production target is 60 production-ready packages. A package is production-ready after Concept → Story Bible → 20 Chapters → Hook → Caption/metadata → Automated QC → Final Package Ready. A later human rejection does not remove it from the Production KPI or generate a replacement by default.

The dashboard shows Production KPI, Ready for Approval, Approved, Rejected, and Regenerated separately. The system stops by default after 60 production-ready packages and offers the user a Continue action.

Final human approval is always required as a separate operational/quality workflow. Hook QC may auto-approve after a 10-second wait if it passes; the user may inspect/review it instead.

At most 10 final packages may wait for human approval by default. On reaching the limit, the system does not admit new stories into production or create additional final packages; running jobs may safely complete their current stage. A decision frees a slot. This maximum will be configurable later.

Manual Facebook publishing is MVP scope. Dashboard convenience actions include open output folder/video, copy caption/comment, and mark as published. A publishing record stores status, timestamp, platform, optional post URL/ID, caption version, and notes. No automatic social posting or verification is included.

### 1.10 Quality, originality, cost, and retry policy

Quality reports/scores exist for Story Bible, originality, chapters/retention, hook, final story, and overall result. Thresholds are provisional/configurable and calibrated with real test data; they must not be aggressively hard-coded before calibration.

Chapter scores are primarily diagnostic. Minor weaknesses create warnings, not automatic regeneration. Critical failures include:

- Safety/content-policy violation.
- Near-copy/reference-boundary violation.
- Hook/Story Bible/Chapter 1 discontinuity.
- Severe plot, timeline, or character contradiction.
- Missing/corrupted required final artifact.
- Budget/policy violation.
- Story-level narrative failure that breaks the core arc.

The system retains long-term lightweight StoryFingerprint metadata for diversity: theme, conflict, cast archetypes, relationships, setting, escalation, twist, ending, emotional arc, hook pattern, similarity metadata/embeddings, and timestamps. It does not retain raw media, drafts, or full chapters solely for diversity.

Retry limits are provisional, configurable per stage, and later calibrated from actual quality/cost data. On exhausted retries, a story is marked with a specific failure type/reason and, when needed to meet a production target, a diversity-safe replacement story is created. A replacement is not a near-identical rerun. Human rejection is distinct from technical, quality, originality, and policy failures.

Cost Manager must estimate and report cost/story, cost/60 stories, expected retry cost, upper-bound cost where possible, and provider rate limits after Phase 3. A user-approved temporary daily budget cap is required before external production. The system must never silently exceed it. Provider selection favors quality/cost balance.

### 1.11 Local operation, recovery, storage, and backup

- MVP must work on CPU-only Windows machines; local models/GPU are optional future optimizations.
- Service/workers start on Windows boot, detect interrupted work, validate recovery/state consistency, show recovery information, and require explicit user confirmation before resuming production.
- Crash/power-loss recovery must never silently restart production.
- A Storage/Cleanup dashboard shows size, age, related story, status, cleanup reason, preview where applicable, restore, pin/unpin, and delete.
- Soft-delete/trash is preferred when practical. Final outputs and pinned items are protected.
- Final outputs, Reference DNA, StoryFingerprint, cost records, QC reports, and approval history are long-term by default. Verbose/debug logs are short-term/configurable; temporary caches/files follow configurable cleanup policies.
- MVP supports manual backup/export of database, non-secret configuration, diversity metadata, job/approval/QC/cost history, output-profile configuration/version, and a manifest of packages/artifacts. It excludes `.env`, keys, credentials, and raw references.

### 1.12 Operator experience and future extensibility

- Dashboard and operator guide are Vietnamese; technical/internal logs may use English.
- The guide must be understandable to a daily operator in about three minutes, with plain Vietnamese, minimal jargon, and task-oriented steps.
- Quick Start presets: 60 Autonomous Stories, 60 From Reference Set, 60 From My Ideas, 60 Reference + My Ideas. Advanced mode exposes manual source-type selection.
- MVP has one local operator and no account/RBAC system. The design must not prevent future Owner, Reviewer, and Operator roles.
- A future spreadsheet/publishing adapter may map completed artifacts to user-defined fields. It must not be hard-coded into core generation or require a Facebook URL column today.
- Output Profiles are versioned. Changing an output layout must not invalidate completed stories; existing packages should be re-exportable to newer profiles when possible.

## 2. Confirmed System Requirements

1. Local Windows orchestration remains the source of truth for job state, storage, policies, cost records, and controls.
2. Browser/dashboard closure must not stop workers.
3. CPU-only operation is a portability baseline.
4. Cloud AI compute is allowed only through approved, policy-scoped providers.
5. All provider calls pass Cloud Boundary and budget/rate-limit checks.
6. Persistent jobs have safe checkpoints, recovery state, retries, explicit failure classes, and audit history.
7. Actual concurrency never exceeds the lower of user-requested concurrency and the calculated safe maximum.
8. Safe concurrency considers provider limits, budget, queue state, PC resources, and current workload.
9. AI CEO autonomously handles normal creative/production decisions, chooses approved providers/fallbacks, schedules work, retries/replaces within policy, and logs concise rationale for creative ambiguity.
10. Deterministic layers prohibit AI CEO from violating policy, budget, originality, cloud boundary, explicit campaign constraints, credentials, security settings, or final approval.
11. No automatic Facebook publishing in MVP.
12. `.env`/local settings are manual-only, gitignored, and never exposed through prompts, ordinary logs, generated output, or committed source.
13. Reference input, final delivery, artifact storage, and export destination must use abstractions rather than hard-coded paths or layouts.

## 3. Non-functional Requirements

| Area | Requirement |
|---|---|
| Reliability | Persistent jobs survive dashboard closure and support user-confirmed recovery after restart/power loss. |
| Scalability | Schedule work incrementally; never launch 60 stories/1,200 chapters simultaneously. |
| Cost safety | Enforce approved caps, estimate cost, track actual use, and throttle by safe concurrency/rate limits. |
| Quality | Multi-layer QC, severity-aware handling, retention scoring, Hook–Story continuity, and originality gates are mandatory. |
| Security | Local-only secrets/control data, provider-scoped data permissions, least-necessary-data principle, no secrets in Git. |
| Privacy | Raw reference/media upload only to designated providers when required; local system remains source of truth. |
| Portability | No required local GPU/model; no hard-coded user paths, keys, provider, or output structure. |
| Usability | Vietnamese operator UI/guide, clear review state, simple presets, manual publishing assistance. |
| Auditability | Store decisions, approvals, failures, cost/QC history, provenance, provider/fallback history, and output-profile version. |
| Storage | Retention by data class, pin/protect final artifacts, recoverable cleanup where practical, manual backup/export. |

## 4. Open Decisions

These are deliberately deferred, not unspecified MVP behavior:

1. Provider/model selection, pricing comparison, rate-limit details, and temporary daily budget cap — Phase 3.
2. Exact provisional QC thresholds and per-stage retry counts — calibrate after real test stories, then approve.
3. Technology stack, database, queue, storage implementation, framework, and rendering implementation — Phase 3–5.
4. Current/company-PC hardware capacity and final performance benchmarks — assess before scaling beyond test phases.
5. MuMuAINovel component reuse — review source architecture, functions, license, and dependencies after this requirements phase.
6. Project license — Phase 13 after dependency/license inventory.
7. Optional Table of Contents display — per story/campaign preference.
8. Stricter campaign-specific deadlines beyond the calendar-day target — future scope.
9. Automated social publishing, spreadsheet schema, and cloud backup — future scope.

## 5. Assumptions

1. References are supplied by the user as local files and must be legal for the intended analysis use.
2. Local output storage is available and configurable; campaigns may override a configured default root.
3. Final human review is a separate quality/operations process and may lag production without changing Production KPI history.
4. Hook auto-approval countdown stops if the user opens review, pauses, or rejects.
5. Story-specific visual continuity is required for the hook; text-only chapters do not require future video rendering in MVP.
6. The default output profile starts with the five agreed files and may evolve through versioned export adapters.
7. Desktop notifications exclude secrets and unnecessary sensitive detail.

## 6. Acceptance Criteria

### MVP production flow

- A user can start a single-story or custom campaign from a reference, idea, combined input, or autonomous brief.
- A local MP4/MOV/WebM reference set within configured limits is temporarily copied, normalized, analyzed, and represented by provenance plus Unified DNA/per-reference patterns.
- The system creates a Story Bible, 20-chapter plan, Hook–Story Contract, originality report, and required approval/review states before production.
- The system produces a 13–17 second 9:16 720×1280 hook with character dialogue, burned-in captions, and SRT; mock providers make end-to-end testing possible without real video/TTS providers.
- The system produces 20 sequential chapters of approximately 500–700 words, with accepted-state continuity, titles, and spoiler-safe recaps for Chapters 2–20.
- A package cannot become `production_ready` without passing required automated QC, originality/reference boundary, budget/policy, Hook–Story continuity, and artifact-integrity gates.
- The default export profile creates a local package with the five agreed files, according to the selected output destination and naming rules.

### MVP operations

- Production KPI, approval metrics, and publishing metrics display separately with the agreed semantics.
- Reaching 60 production-ready packages stops default admission and exposes a Continue control.
- The pending final-review limit of 10 applies backpressure without killing in-flight work.
- Actual concurrency is safely capped even when a user requests a higher number.
- On restart, the service shows interrupted work and requires user confirmation before production resumes.
- Retry exhaustion records a classified failure reason and can trigger a diversity-safe replacement for production pipeline failure.
- Human rejection remains independently recorded and does not retroactively alter Production KPI.
- A user can open artifacts, copy caption/comment, mark manual publishing status, view storage status, pin/unpin cleanup candidates, and make a manual non-secret backup export.

### MVP governance

- No external provider receives data unless allowed by category/provider Cloud Boundary policy.
- The system never silently exceeds approved budget or uses an unapproved provider.
- Secrets are absent from tracked source, output packages, prompts, and normal logs.
- The system has a plain-Vietnamese operator guide describing the normal daily flow in about three minutes of reading.

## 7. MVP Scope

- One local Windows operator; Vietnamese dashboard/operator guide.
- CPU-only local-first orchestration with approved cloud compute.
- Persistent queue/state, safe concurrency, recovery prompt, budgets, retries, failure classification, and 60/day workflow controls.
- Reference Library with local file ingest, provenance, normalized temporary media, Unified DNA, and per-reference pattern library.
- Idea form plus lightweight multi-line idea import; campaign presets and advanced custom campaigns.
- Story Bible, 20-chapter sequential generation, continuity memory, diversity metadata, originality gate, and QC reports.
- Mock video/voice/audio providers and a default Output Profile v1.
- Manual final approval, manual Facebook publishing assistance, local publishing record, Storage/Cleanup dashboard, and manual backup export.
- No automatic social posting, cloud backup, local-model requirement, accounts/RBAC, or fixed provider selection.

## 8. Future Scope

- Provider selection/fallback portfolios, real video generation/TTS integrations, and possible composition rendering integration such as Remotion.
- Calibrated thresholds/retries/cost caps based on test data.
- GPU/local-model acceleration.
- Multi-user roles and authentication.
- Automated Facebook/social posting and verification, subject to explicit future approval.
- Spreadsheet/export/publishing adapters after a user-provided sample/template.
- Cloud backup and multi-machine deployment.
- Campaign-specific deadlines, richer analytics, and more Output Profiles.
- License finalization and public packaging after dependency/license inventory.

