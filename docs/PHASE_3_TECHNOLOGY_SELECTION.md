# Phase 3 — Technology Selection Proposal

**Status:** Approved prototype direction — revised 2026-10-09 for Lite/Standard resource profiles  
**Current runtime decision:** See `RESOURCE_PROFILES.md`. It supersedes the single PostgreSQL/RabbitMQ selection below for the current 4 GB machine.
**Based on:** `FINAL_PRODUCT_REQUIREMENTS.md`  
**Does not include:** implementation code, a locked real video/TTS provider, or a production budget cap.

## 1. Decision summary

| Area | Recommended MVP selection | Why it fits the approved requirements |
|---|---|---|
| Core language | Python 3.12+ | Fits MuMuAINovel review/reuse path, multimodal/AI ecosystem, and CPU-only Windows baseline. |
| Local API/control plane | FastAPI | Typed API contract, local dashboard backend, provider adapters, and clear separation from workers. |
| Dashboard | React + TypeScript + Vite | Vietnamese local operator UI, video preview, review screens, live job state, and future extensibility without a server-rendering requirement. |
| Durable system database | Lite: SQLite WAL on local disk; Standard: PostgreSQL | Lite fits the first 4 GB PC; Standard supports greater write concurrency. Both store persistent state and audit history. |
| Queue/broker | Lite: database polling with one worker; Standard: Dramatiq + RabbitMQ | The database is authoritative; the broker is optional transport for stronger deployments. |
| Workflow state machine | Explicit application-domain state machine persisted in PostgreSQL | Required for approvals, backpressure, campaign policies, failure classification, and export-profile versioning. |
| Artifact storage | Local filesystem behind a storage abstraction | Meets local-first output/backup/cleanup requirements without hard-coded paths. |
| AI orchestration | Provider adapters + deterministic policy engine; no agent framework in MVP | Preserves AI CEO autonomy while keeping safety, budget, originality, and cloud-boundary enforcement deterministic. |
| LLM/vision provider strategy | Provider-agnostic `LLMProvider`/multimodal adapter; OpenAI and Google Gemini are researched candidates | Enables user-controlled assignment without provider or model lock-in. |
| Video/voice/audio in MVP | MockVideoProvider, MockVoiceProvider, MockAudioAssetProvider | Allows end-to-end MVP verification before a real video/TTS provider is approved. |
| Renderer | Minimal mock/placeholder composition path for MVP | Real composition technology, including potential Remotion integration, is deferred until real raw assets exist. |
| Background Windows runtime | Windows-started service processes, designed in Phase 4/5 | Supports boot start and user-confirmed recovery without binding work to a browser. |

## 2. Why this queue choice

### Standard profile: Dramatiq + RabbitMQ, with PostgreSQL as source of truth

Dramatiq supplies worker-side message delivery, delayed work, retry handling, task priorities, rate/lock middleware, and documents Windows support. It supports RabbitMQ and Redis; RabbitMQ is its recommended broker. PostgreSQL holds every authoritative job, task, approval, policy, cost, and artifact record. A worker only performs a task after it claims an eligible database record, and it writes the resulting state back transactionally.

This division is important: RabbitMQ transports work; it does **not** replace the business workflow database. Therefore pause/stop, pending-approval backpressure, calendar KPI, human gates, recovery prompts, and classification remain auditable and controllable by the application.

### Rejected for MVP: FastAPI in-process background tasks

FastAPI documents `BackgroundTasks` for work after a response and points heavy multi-process/multi-server work toward bigger queue tools. The project requires independent, durable workers that remain alive after dashboard closure; in-process tasks are therefore insufficient.

### Rejected for MVP: Celery

Celery's own current documentation states that Microsoft Windows is not supported. The local-first Windows baseline makes this a poor default despite Celery's broad ecosystem.

### Deferred: Temporal

Temporal is a strong durable-execution platform and explicitly supports workflows resuming after crashes/outages. It is not selected for the first local MVP because it adds a separate workflow platform/service and operational overhead beyond the immediate single-PC scope. It should be reconsidered if the product moves to multi-machine or cloud-hosted orchestration, or if custom workflow-state maintenance becomes too costly.

## 3. Component boundaries

```text
Vietnamese React dashboard
          │ local HTTP/WebSocket API
          ▼
FastAPI control plane ─────── PostgreSQL (source of truth)
          │                              │
          │ enqueue eligible work         │ state, policies, audit, cost
          ▼                              │
RabbitMQ ─────── Dramatiq workers ───────┘
          │
          ├── Reference worker
          ├── Creative/novel worker
          ├── Hook/media worker
          ├── QC/originality worker
          └── Maintenance/cleanup worker

Local artifact storage ← Storage abstraction → versioned export profiles
Cloud providers only through scoped adapters and the Cloud Boundary policy layer
```

FastAPI is the control plane, not the execution engine. It receives dashboard actions, validates policies, provides review APIs, and issues durable work. Workers may run while the dashboard/browser is closed.

## 4. Data and persistence selection

### PostgreSQL: Standard profile

Use PostgreSQL for structured state: campaigns, StoryRequests, jobs, task leases, approvals, policy decisions, cost ledger, Reference DNA, provenance, fingerprints, QC reports, publishing records, audit events, and export-profile versions.

It is preferable to SQLite for this project because the worker fleet needs concurrent claims/leases, transactional state transitions, long-term metadata, and future scale beyond one process. PostgreSQL provides Windows distributions, while keeping the data model portable to future server deployment.

### Local artifact storage: selected

Use configurable local directories for temporary normalized media, cache, durable final output, trash/recovery, and backup exports. Database records store artifact identity, checksum, classification, retention/pin state, and storage URI/path. They must not assume a drive letter or a permanent folder layout.

### Vector/search implementation: deferred

Store StoryFingerprint structure in PostgreSQL from MVP. Select the exact embedding/vector extension after the real similarity workload and chosen LLM provider are known. This avoids adding a separate vector database before it is justified.

## 5. LLM and multimodal provider strategy

### Prototype policy — user direction recorded

All provider/model choices in this phase are **experimental prototypes**, not production approvals. The purpose of the first trials is to prove the end-to-end workflow, structured outputs, continuity, QC gates, and observability before any paid provider commitment.

The trial roster is:

| Candidate | Classification in this system | Prototype decision |
|---|---|---|
| ChatGPT Free | Interactive ChatGPT product, not a general automation API | May be used manually for qualitative comparison only. It must not be automated through browser/UI scripting or treated as an API provider. A programmatic OpenAI provider requires separately authorized API access/billing. |
| Google Gemini API Free tier | Cloud LLM/multimodal provider | Candidate for small, quota-limited prototype calls after Cloud Boundary review. Free-tier data handling and quota limits must be visible to the operator. |
| Ollama + Qwen3 | Local provider/runtime plus open-weight model family | Recommended no-provider-cost prototype path. On the current 4 GB RAM / integrated-GPU PC, use Qwen3 0.6B only for adapter smoke tests; defer 4B/8B until hardware capacity improves. This can exercise the same adapter contract offline. |
| Muse.ai | External personal AI agent/product | Not an LLM provider assignment. There is no verified public inference API suitable for this production pipeline. It may be evaluated manually as a workflow/product reference, but is not integrated into workers. |
| MuMuAINovel | Potential story-engine codebase, not a model | Deferred until its source, license, architecture, and dependencies are reviewed. Reuse only compatible parts; never import the whole repository by default. |

No candidate becomes available to the AI CEO merely because it is installed or listed here. Each must pass a bounded trial and then receive an explicit Model Assignment Policy approval.

### Prototype evaluation gate

Use a deliberately small, non-production test: one StoryRequest at a time, no automatic publishing, no real video/TTS/audio provider, and no sensitive or unapproved reference upload. Record the exact candidate/version, local or cloud location, prompt/output token counts when available, latency, quota/rate-limit failures, structured-output validity, English prose quality, continuity/QC results, and data-handling notes.

Promote a candidate only when it passes the applicable workload tests. A failed candidate is marked `RETIRED` or remains `CANDIDATE_RESEARCHED`; it is never silently substituted into production work.

### Provider/model selection is user-controlled

Technology selection, provider selection, model assignment, and QC/retry policy are four separate decisions. This document selects the **adapter architecture**, not a permanent provider or model assignment.

Business logic must use this path:

```text
Workload → Model Assignment Policy → Provider Adapter → Selected Provider + Model
```

Model IDs are configuration data, never Story Bible/Hook/Chapter business logic. The editable [Model Assignment Matrix](MODEL_ASSIGNMENT_MATRIX.md) is the required decision record. Primary and fallback models remain `[USER TO SELECT]` until approved by the user.

### Candidate research shortlist (not assignments)

| Workload family | Candidate provider/model family | Why it is a candidate | User decision |
|---|---|---|---|
| Complex planning, difficult QC, contradiction resolution | OpenAI GPT-6 Astra or GPT-6.1 Sol; Google Gemini 3.1 Pro | Official docs describe high-capability/reasoning tiers, long context, structured outputs, and multimodal capability. | `[USER TO SELECT]` |
| High-volume chapters, recaps, captions, routine QC | OpenAI GPT-6 Luna; Google Gemini 3.1 Flash-Lite/3.8 Flash | Cost/speed-oriented tiers; suitability must be calibrated against prose quality. | `[USER TO SELECT]` |
| Reference video/multimodal analysis | Google Gemini video-capable model families; OpenAI vision-capable model families | Both candidate paths support multimodal/vision workloads; actual video handling, regional availability, limits, and cost require a controlled trial. | `[USER TO SELECT]` |
| Embeddings/similarity | OpenAI embedding capability; provider-specific embedding alternative | Uses a dedicated embedding capability through the same provider abstraction; compare semantic quality/cost on project data. | `[USER TO SELECT]` |
| TTS/voice, video, music/SFX | Mock providers in MVP; real providers deferred | The PRD deliberately defers real media providers and retains provider-neutral interfaces. | `[USER TO SELECT LATER]` |

These are candidates only. They are not a recommendation to use a particular provider for a given production workload, and no provider becomes available to the AI CEO until the user approves it in Model Assignment Policy.

At the current official pricing pages, token costs and rate limits vary significantly by tier and provider. The Cost Manager must calculate estimates from real prompt/output telemetry during one-story calibration; it must not use a fixed hard-coded expectation.

### Provider fallback

Provider adapters are registered only after category/provider approval. Fallback selection is automatic only among user-approved fallback assignments and must be visible in the dashboard and audit history. Cloud Boundary checks happen before network calls.

### Versioned Model Assignment Policy

Each production job records the immutable model assignment snapshot used for every provider call: `model_assignment_version`, workload, provider, model, timestamp, fallback/escalation reason, and relevant policy identifiers. If the user changes an assignment, new jobs use a new version; previous jobs retain their original history and are never retroactively rewritten.

The AI CEO may select the configured primary assignment, an approved fallback, or an approved escalation path. It must not silently introduce a provider, change a selected model, bypass Cloud Boundary, exceed budget/rate limits, or bypass allowlists.

### Real video/TTS/audio providers: deliberately deferred

The requirements and project workflow explicitly put real Video/TTS providers after scaling phases. MVP uses mocks. This avoids locking product architecture to the unknown current video tool and permits a pipeline test without paid media generation.

## 6. Policy and quality technology approach

Do not select LangGraph, CrewAI, AutoGen, n8n, or a similar agent framework for MVP. The PRD needs durable state, policy enforcement, auditable jobs, deterministic gates, and controlled human approvals—not an opaque autonomous-agent runtime.

Use:

- Typed domain contracts for all artifacts and provider requests/results.
- Deterministic state/policy checks for budget, approvals, Cloud Boundary, retention, provider allowlists, and critical failure gates.
- LLM calls only for bounded creative, analysis, and evaluator work.
- Structured outputs for Story Bible, ChapterPlan, QCReport, StoryFingerprint, and RewriteInstruction.

This keeps the AI CEO broad in creative autonomy but unable to bypass hard constraints.

## 7. Supporting technology proposals

| Need | Recommendation | Notes |
|---|---|---|
| Data validation/contracts | Pydantic v2 | Python-native structured contracts at API/worker/provider boundaries. |
| Persistence mapping/migrations | SQLAlchemy 2 + Alembic | Keeps PostgreSQL schema explicit, migratable, and portable. |
| Tests | pytest + contract/integration fixtures | Mock providers make pipeline and failure/retry tests repeatable. |
| Dashboard tests | Playwright | Covers Vietnamese operator paths, approval, pause/resume, and visible state. |
| API contracts | OpenAPI emitted by FastAPI | Allows dashboard/UI to stay contract-aligned. |
| Observability | JSON structured logs + PostgreSQL audit/cost/QC events | Start simple locally; add OpenTelemetry/export targets only when needed. |
| Packaging | Native Windows setup first; Docker Compose optional for reproducible dev/test | Docker must not be a required operator dependency in MVP. |

## 8. Explicit non-selections

- No Celery as the Windows MVP queue.
- No FastAPI `BackgroundTasks` for long-running generation.
- No local LLM/GPU requirement.
- No hard-coded provider/model/API key/output path.
- No direct social publishing integration.
- No database-only replacement for artifact storage.
- No permanent output folder assumption inside core production logic.
- No immediate integration of Remotion or the full MuMuAINovel repository.

## 9. Risks and mitigation

| Risk | Mitigation |
|---|---|
| RabbitMQ adds another local service | Keep it isolated; provide clear operator startup/health checks in later phases. PostgreSQL retains authoritative work state. |
| Provider prices/rate limits change | Provider registry and Cost Manager read configuration; perform calibration before production caps are approved. |
| 60/day proves more expensive/slower than expected | Validate exactly in the approved progression: 1 → 5 → 10 → 20 → 60. |
| Complex workflow logic grows | Keep explicit domain state machine; reevaluate Temporal when multi-machine/cloud durability warrants its operational cost. |
| MuMuAINovel overlaps components | Review and map it before reuse; adopt only compatible, licensed portions. |
| Generated media/provider policy blocks content | Retain mock path, provider adapters, content-policy checks, and alternate approved providers. |

## 10. Source basis

- [FastAPI background-task guidance](https://fastapi.tiangolo.com/tutorial/background-tasks/) distinguishes small in-process work from heavier jobs that benefit from an external task queue.
- [Celery FAQ](https://docs.celeryq.dev/en/main/faq.html) states that Windows is not supported.
- [Dramatiq motivation](https://dramatiq.io/motivation.html) documents Windows support plus retry, rate-limit, priority, broker, and delivery comparisons; [Dramatiq installation](https://dramatiq.io/installation.html) recommends RabbitMQ and supports Redis.
- [Temporal documentation](https://docs.temporal.io/) describes durable execution and self-hosted/Cloud options; it is retained as a future-scale candidate rather than selected for MVP.
- [PostgreSQL downloads](https://www.postgresql.org/download/) provides Windows distribution paths.
- [Official OpenAI model documentation](https://developers.openai.com/api/docs/models) and [pricing](https://developers.openai.com/api/docs/pricing) are current candidate-research sources for model tiers, capabilities, prices, and rate-limit planning.
- [Google Gemini models](https://ai.google.dev/gemini-api/docs/models), [structured output](https://ai.google.dev/gemini-api/docs/structured-output), and [pricing](https://ai.google.dev/gemini-api/docs/pricing) are current candidate-research sources for multimodal, schema, and price/rate-limit evaluation.

## 11. Approval record

Approved by the user on 2026-10-06 for Phase 4 architecture work and bounded prototype planning:

1. Python + FastAPI control plane.
2. React + TypeScript + Vite Vietnamese dashboard.
3. PostgreSQL as durable system database and local filesystem as artifact store.
4. Dramatiq + RabbitMQ for worker transport, with PostgreSQL as authoritative workflow state.
5. No Celery, no FastAPI in-process generation tasks, no agent framework, and no required Docker/local GPU.
6. Provider-agnostic LLM/vision adapters and the versioned Model Assignment Matrix; all listed candidates remain experimental/non-binding. Real video/TTS/audio stay mock/deferred.
7. Explicit domain state machine and deterministic policy layer rather than framework-led agent orchestration.

This approval does not authorize production provider use, paid API spending, automatic publishing, model installation, implementation code, or a final provider/model assignment.
