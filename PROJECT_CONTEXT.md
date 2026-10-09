# AI Content Company — Project Context & Continuation Guide

> **Latest implementation handoff (2026-10-09):** Read `handoff.md` for the current launcher/login changes, test evidence, and honest public-deployment status. This older context remains useful for approved product decisions but does not reflect every later implementation update.

> **Purpose:** Read this file at the start of a new chat before making plans, choosing technology, or writing code. It is the concise handoff for this project.
>
> **Truth rule:** This file summarizes decisions confirmed by the user. If a detail conflicts with a confirmed project document, follow `docs/FINAL_PRODUCT_REQUIREMENTS.md`. Do not silently reinterpret confirmed requirements.

## 1. What this project is

This project will become a **local-first, autonomous AI content-production system** for English drama content. It behaves like a small AI-powered production company, not a simple story-writing chatbot.

It takes one or more local reference videos, a user idea, both, or an autonomous campaign brief. It produces original story packages with a short video hook, a complete 20-chapter text story, Facebook copy, quality control, provenance, and operational history.

The system must learn abstract creative principles from reference material, never create a renamed/reworded copy of a reference.

## 2. Current status — do not skip phases

The project workflow is in `Project's Workflow.md`:

```text
Phase 1  Requirements Interview       COMPLETE
Phase 2  Final PRD                    COMPLETE and user-approved
Phase 3  Technology Selection         COMPLETE; revised for Lite/Standard resource profiles on 2026-10-09
Phase 4  Detailed Architecture         COMPLETE and user-approved
Phase 5  Repository / Database Design  COMPLETE and user-approved
Phase 6  MVP Implementation            IN PROGRESS — initial domain, persistence, migration, and API slice
Phase 7–13  Testing, scale, real media providers, GitHub production
```

Phase 6 implementation is authorized. The initial code slice is documented in `docs/PHASE_6_IMPLEMENTATION_STATUS.md`. Provider/model assignments remain prototypes until bounded trials and explicit later approval.

## 3. Authoritative project documents

1. `docs/FINAL_PRODUCT_REQUIREMENTS.md` — user-approved PRD and primary source of truth.
2. `docs/PHASE_3_TECHNOLOGY_SELECTION.md` — approved experimental, provider-agnostic technology direction.
3. `docs/MODEL_ASSIGNMENT_MATRIX.md` — user-editable provider/model selection template. Models are deliberately unselected.
4. `Project's Workflow.md` — required phase order.
5. `docs/PHASE_4_DETAILED_ARCHITECTURE.md` and `docs/PHASE_5_REPOSITORY_DATABASE_DESIGN.md` — approved design baselines.
6. `docs/PHASE_6_IMPLEMENTATION_STATUS.md` — current implementation progress and remaining work.
7. `docs/RESOURCE_PROFILES.md` — current Lite/Standard runtime decision; supersedes older single-stack assumptions.

## 4. Product goal and output

### Goal

Generate original English drama content at scale while preserving quality, continuity, originality, auditability, budget control, and human control.

### Daily target

- Target: 60 **production-ready** packages per Asia/Ho_Chi_Minh calendar day (00:00–23:59).
- A package counts when it has passed required automated gates and is `production_ready`.
- Human approval/rejection and manual publishing are separate metrics; they do not retroactively change Production KPI.
- Default behavior after 60 production-ready packages: stop admitting work; user can choose Continue.

### Default MVP output profile (v1)

The core pipeline produces structured artifacts. The default export profile currently writes a local package like:

```text
OUTPUT/
  YYYY-MM-DD__STORY-0001__title-slug/
    hook.mp4
    hook.srt
    story.txt
    caption.txt
    comment.txt
```

- `hook.mp4`: vertical hook, burned-in English captions.
- `hook.srt`: separate English subtitles.
- `story.txt`: reader-facing only; no internal metadata.
- `caption.txt`: Facebook post caption.
- `comment.txt`: first-comment CTA.

The layout is not permanent business logic. Output Profiles/Export Adapters must remain versioned and extensible for later spreadsheet, publishing, or destination formats.

## 5. Content requirements already confirmed

### Story

- Drama niche; English creative content only.
- Exactly 20 text-only chapters.
- Roughly 500–700 words/chapter; mobile-friendly, emotionally strong, medium-length sentences.
- Each chapter has title, recap, and content. Chapter 1 has no recap. Chapters 2–20 have short spoiler-safe recaps of prior known state only.
- `story.txt` contains title, optional TOC, chapter titles, recaps, and chapter content only.
- Default cast: maximum 3–4 main and 3–4 supporting characters. Exceed only when truly needed and without reader confusion.
- Endings rotate under diversity control among satisfying/justice payoff, bittersweet closure, and twists; the core conflict must close.

### Hook = Chapter 0

- Duration 13–17 seconds; default 9:16 vertical, 720×1280.
- The first three seconds must create a strong curiosity/tension question, but there is no mandatory single “shock” formula.
- The AI may select immediate conflict, dialogue, reveal, mystery, emotional reaction, unexplained event, or pattern interrupt when it passes Hook QC.
- Hook contains character dialogue only, maximum three speaking voices.
- Character/prop/environment/lighting continuity is required within a hook except intentional transitions.
- Hook has English burned-in captions plus `hook.srt`; captions are high-contrast, mobile-readable, in vertical safe areas, maximum two lines. Styling is configurable, not fixed.
- Music/SFX only when they improve storytelling; silence is allowed. Use royalty-safe/AI-generated/licensed assets; never use recognizable reference music, unauthorized commercial music, dialogue-obscuring audio, clipping, or gratuitous jump-scare audio.
- A Hook–Story Contract and Hook → Story Continuity Gate are mandatory. The hook must connect coherently to Story Bible and Chapter 1, with a tracked open loop/payoff.

### Content boundaries

- Characters/stories are fictional or AI-generated.
- Child-centered drama involving ages roughly 3–8 is a primary pattern, but not mandatory for every story.
- Limited non-graphic physical abuse may appear: minor scratches/trails of blood only; no gore or detailed injuries.
- No sexual content, sexualization, or exploitation of minors.
- Limit profanity, self-harm, politics, religion, hate content, and other moderation-risk content.
- Target: English-speaking general adult Facebook audience, primarily 18+, no country-specific target in MVP.

## 6. Inputs and Reference DNA

### Story sources

`StoryRequest.source_type`:

- `reference`
- `user_idea`
- `reference_user_idea`
- `autonomous`

Autonomous mode uses content policy + diversity history and optional campaign brief. It does not require human concept approval by default, but campaign-level concept approval may be enabled later.

### User idea input

Provide a structured form: free-text premise plus optional theme, protagonist, antagonist, child character/age, setting, desired hook event, ending preference, drama intensity, forbidden elements, reference files, and visual-style preference. Support lightweight multi-line idea import (one seed/line).

### References

- MVP only accepts user-provided local files; it does not auto-download Facebook/TikTok/Instagram URLs.
- Support MP4, MOV, WebM.
- Configurable defaults: 500 MB/video, 10 minutes/video, max 5 videos/reference set.
- Copy raw references temporarily, normalize them for analysis, then clean temporary media according to retention policy.
- Store long-term Reference DNA, analysis metadata, and provenance—not raw video by default.
- Provenance includes source platform, original URL, creator/source note, rights/use note, local file path/ID, import time, analysis status.
- Multi-reference analysis must create both Unified/common Reference DNA and per-reference pattern library.
- Reference DNA must include visual/audio style **and** narrative mechanics, hook mechanics, emotional progression, pacing, curiosity gaps, open loops, and retention mechanisms.
- Unknown/unclear rights: allow abstract analysis, show warning, apply stricter originality rules. Do not reproduce specific reference characters, dialogue, sequence, visual identity, setting, or distinctive structure.

### Existing video references

Two local MP4 files were provided previously in `C:\Users\CanhN\Downloads\`:

- `snapsave.vn_facebook_6ac35c98d99f2.mp4` — 27 seconds.
- `snapsave.vn_facebook_6ac35cb219dd1.mp4` — 30 seconds.

Their creative content has **not** been analyzed. Do not infer it from filenames.

## 7. Mandatory planning, QC, originality, and memory

### Before writing chapters

Every story needs a Story Bible and 20-chapter plan before generation. Story Bible covers characters, relationships, timeline, conflicts, secrets, foreshadowing, reveals, emotional arcs, ending, and per-chapter objectives.

Do not generate 20 independent chapter tasks. Generate sequentially with Story Bible + accepted prior state + Continuity Memory + unresolved threads + foreshadowing ledger.

### QC

Score/report layers: Story Bible, Originality, chapter quality/retention signals, Hook, Final Story QC, Overall Result.

Chapter retention checks curiosity, tension, emotional engagement, progression, and pull to the next chapter. Minor chapter issues are diagnostics/warnings, not automatic regeneration.

Critical failures:

- Safety/content policy violation.
- Near-copy/reference-boundary violation.
- Hook/Story Bible/Chapter 1 discontinuity.
- Severe plot, timeline, or character contradiction.
- Missing/corrupt required final artifact.
- Budget/policy violation.
- Story-level core-arc narrative failure.

### Diversity and originality

The system retains lightweight StoryFingerprint metadata long term: theme, conflict, cast archetypes, relationships, setting, escalation, twist, ending, emotional arc, hook pattern, similarity metadata/embeddings, timestamps.

It must not retain drafts/raw references/full chapters solely for Diversity Engine purposes. The Originality / Reference Boundary Gate checks combined semantic and structural similarity to references and prior stories.

## 8. Approval, campaign, queue, and failure behavior

### Human approval

- Hook may auto-approve after it passes QC and waits 10 seconds; user can review instead.
- Final packages always require human approval as a separate workflow/metric.
- Final review shows primary review (player/title/overall QC/originality/critical issues/warnings), story review (story navigation/recaps/transcript/caption/comment), and collapsible production metadata (detailed reports/cost/providers/fallback/publishing).
- Reject action offers targeted revision, regeneration, or stop. Feedback is optional. Old versions are not retained as final artifacts.

### Pending final review backpressure

- Default maximum `max_pending_approval = 10`.
- When full: do not admit new stories into production or create more final packages. Do not kill running jobs; let them finish safe current stage.
- A human decision frees a slot. The limit should later be configurable.

### Retries and replacements

- Retry policy is provisional/configurable per stage; exact limits/thresholds will be calibrated after test runs.
- Exhausted retries result in classified `technical_failure`, `quality_failure`, `originality_failure`, `policy_failure`, or `needs_review`, with reason.
- A replacement is created when a production pipeline failure prevents reaching `production_ready` and is needed to meet target. It must pass diversity checks and is a new story.
- `human_rejected` is separate. A later human rejection does not alter Production KPI and does not automatically create a replacement.

### Pause, stop, recovery

- Pause: stop work as soon as safely possible.
- Stop: stop scheduling; preserve accepted work/artifacts.
- Windows boot: service starts, checks interrupted jobs/state, then requires explicit user confirmation before resuming production. Never silently resume after crash/power loss.

### Concurrency and provider fallback

- Actual concurrency = lower of user setting and system-calculated safe maximum.
- Safe maximum considers provider rate limits, budget, queue state, PC resources, and workload.
- Providers may fall back only to user-approved fallback assignments. Record the change in dashboard/audit history.

## 9. Cost, cloud boundary, security, and storage

### Cost policy

- Quality/cost priority: balanced.
- Before real providers are chosen, do not allow unrestricted external production.
- Phase 3 must later provide estimated cost/story, cost/60, retry cost, upper-bound estimate where possible, and rate limits.
- User approves temporary daily cap before external runs. Never silently exceed it.

### Hybrid-cloud boundary

- Local system is source of truth for orchestration, state, policies, controls, artifacts, and internal records.
- Cloud AI is allowed for text/story/metadata, approved reference analysis, and scoped TTS/video/render compute.
- Send only necessary context/artifacts to the specific provider.
- Secrets, credentials, job database/state, internal config, cost/account data, and system controls are local only and never sent to models.
- Cloud Boundary policy is category-level **and** provider-level, with least-necessary-data default and future disable controls.

### Secrets

- MVP API keys/manual credentials are in local `.env` / local settings only.
- `.env` is gitignored.
- Never expose keys in prompts, model context unless technically required, normal logs, outputs, unnecessary DB records, or GitHub.

### Storage and backup

- Retain final outputs, Reference DNA, StoryFingerprint, cost/QC/approval history long-term by default.
- Raw temporary references, caches, verbose/debug logs follow configurable cleanup policies.
- Storage/Cleanup dashboard: list, size, age, related story, reason/status, preview where practical, restore, pin/unpin, delete. Prefer soft-delete/trash when practical; protect final/pinned data.
- MVP manual backup/export includes DB, non-secret config, diversity/job/approval/QC/cost history, output-profile configuration/version, and package-artifact manifest. Excludes `.env`, credentials, API keys, and raw reference media.

## 10. AI CEO boundaries

The AI CEO has broad autonomy for normal creative and operations work: concept selection in autonomous mode, Story Bible, chapter structure, hook creative choices, approved voice/provider/fallback selection, retries/replacements, queue scheduling, safe concurrency, and minor QC corrections. It logs concise rationale for valid creative ambiguity.

The AI CEO must never:

- Break safety, originality/reference, Cloud Boundary, budget/rate, or explicit campaign constraints.
- Use unapproved providers/models, change user-selected assignments, access/change credentials, or bypass provider allowlists.
- Delete important user data, modify source code, redesign architecture, change global security/quality/safety thresholds, final-approve, or automatically publish in MVP.

Hard boundaries must be deterministic system/policy layers, not trust in an LLM.

## 11. Technical decisions and their status

### Phase 3 selection — approved prototype direction

The approved technology direction, revised for the current 4 GB PC, is:

- Python + FastAPI as control plane.
- React + TypeScript + Vite Vietnamese dashboard.
- SQLite WAL on local non-synced storage for the initial Lite profile; PostgreSQL for Standard.
- Local filesystem storage abstraction.
- Database polling with one worker for Lite; Dramatiq + RabbitMQ transport for Standard. The selected database remains authoritative workflow state.
- Explicit application workflow state machine and deterministic policy engine.
- No Celery, no required Docker/GPU/local model, and no generic agent framework in MVP.

Both profiles use the same domain and provider contracts. The Lite profile must be safe on the current 4 GB Windows PC; it may pause new work if available memory is too low. The Standard profile and data migration between profiles require later integration tests. Provider/model assignments remain experimental and non-production until they pass bounded trials and receive an explicit Model Assignment Policy approval.

The user designated an example 8 GB office PC (Core i3-14100F, Radeon R7 240 4 GB, 256 GB NVMe SSD) as the representative mainstream validation target. This is not evidence of a statistical hardware average. Lite remains the default on that machine until benchmark data justifies Standard or more parallelism; the GPU is not a local-inference dependency. See `docs/RESOURCE_PROFILES.md`.

### Provider/model assignment — deliberately unselected

- Architecture remains provider-agnostic.
- Use `Workload → Model Assignment Policy → Provider Adapter → Selected Provider + Model`.
- Model IDs must be configuration, not business logic.
- `docs/MODEL_ASSIGNMENT_MATRIX.md` holds blank `[USER TO SELECT]` primary/fallback fields for every workload.
- Every production provider call must record assignment version, workload, provider, model, timestamp, and fallback/escalation rationale.
- Real Video/TTS/Audio providers remain mock/deferred; do not choose them because a provider is available.
- Gemini Free is approved only for the bounded, non-sensitive prototype inputs defined in `docs/PHASE_4_PROTOTYPE_EVALUATION_PLAN.md`; it is not approved for reference media analysis or production work.

### MuMuAINovel and Remotion

- MuMuAINovel is kept as a possible Story/Novel Engine foundation, but source/ZIP is not in this workspace yet.
- After requirements/technology are approved, review MuMuAINovel architecture, functionality, license, and dependencies; classify parts as adopt/adapt/reusable/rewrite/irrelevant. Never import the whole repository blindly.
- Remotion is a future candidate for composition/rendering only after raw assets exist. It is not an AI video generator and is not integrated now.

## 12. Operator UX

- Dashboard and daily operator guide: Vietnamese, low jargon.
- Creative outputs: English only.
- Quick Start presets: `60 Autonomous Stories`, `60 From Reference Set`, `60 From My Ideas`, `60 Reference + My Ideas`.
- Advanced/custom campaigns can select source type directly.
- MVP: one local operator, no accounts/RBAC. Do not block future Owner/Reviewer/Operator roles.
- Manual Facebook actions: open folder/video, copy caption/comment, mark published. Store status, timestamp, platform, optional URL/ID, caption version, and notes. Do not auto-publish.

## 13. Rules for the next assistant/chat

1. Read this file and `docs/FINAL_PRODUCT_REQUIREMENTS.md` before proposing changes.
2. Do not restart requirements discovery or contradict confirmed decisions.
3. Phase 6 is authorized; implement against the approved Phase 4/5 design and verify each increment before claiming MVP readiness.
4. Do not choose provider/model assignments, real video/TTS/audio provider, QC thresholds, retry limits, budget caps, or project license without user approval.
5. Do not hard-code paths, provider IDs, model IDs, secrets, output layout, or a browser-dependent worker flow.
6. Do not use reference content as material to copy.
7. Preserve the distinction between production KPI, approval KPI, and publishing KPI.
8. Keep technical/provider changes separate from confirmed product requirements.
9. If a new request conflicts with this context, explain the conflict and ask the user to explicitly change the confirmed requirement.

## 14. Immediate next action

Continue **Phase 6 — MVP Implementation** using `docs/RESOURCE_PROFILES.md`. Complete the Lite profile on the current 4 GB machine first, then verify Standard and a migration path before public GitHub release. Finish durable workflow/task processing, mock provider pipeline, artifact export, dashboard, and operations controls before the one-story validation phase. Do not claim `production_ready` for mock packages.
