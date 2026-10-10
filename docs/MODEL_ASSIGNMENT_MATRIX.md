# Model Assignment Matrix

**Status:** GPT-5.6-Terra text slice approved by user on 2026-10-10
**Rule:** current implemented text workloads use OpenAI `gpt-5.6-terra` only, with no fallback. Video/TTS/audio remain unselected.

## How to use this matrix

1. Keep the provider/model values blank until you approve a candidate.
2. Use a new `model_assignment_version` whenever any approved assignment changes.
3. A production job records the assignment version, provider, model, workload, timestamp, and fallback/escalation reason for every call.
4. A fallback is usable only if it is user-approved, Cloud-Boundary-allowed, within budget/rate limits, and compatible with the required capabilities.
5. Video/TTS/audio remain mock/deferred in MVP unless explicitly changed by a later approved decision.

## Fields

| Field | Meaning |
|---|---|
| Primary Provider / Model | User-approved default provider/model; initially `[USER TO SELECT]`. |
| Fallback Provider / Model | User-approved fallback; initially `[USER TO SELECT]`. |
| Required capabilities | Functional needs for the workload. |
| Vision / reasoning / context / structured output | Mandatory capability settings, not model names. |
| Q/C/S priority | Relative Quality / Cost / Speed priority. |
| Escalation condition | When an approved escalation assignment may be used. |
| Selection status | `UNSELECTED`, `CANDIDATE_RESEARCHED`, `USER_APPROVED`, or `RETIRED`. |

## Matrix

| Workload | Purpose | Primary Provider / Model | Fallback Provider / Model | Required capabilities | Vision / Reasoning / Context / Structured output | Q/C/S priority | Escalation condition | Notes | Selection status |
|---|---|---|---|---|---|---|---|---|---|
| Reference Video Analysis | Extract visual/audio/narrative/retention evidence | [USER TO SELECT] | [USER TO SELECT] | Video/multimodal analysis, timestamps | Vision: required; Reasoning: high; Context: long; Structured: required | Q> C, S | Incomplete/conflicting analysis | Cloud-boundary scoped upload only | UNSELECTED |
| Unified Reference DNA | Synthesize common reusable principles | [USER TO SELECT] | [USER TO SELECT] | Synthesis, schema reliability | Vision: optional via source analysis; Reasoning: high; Context: long; Structured: required | Q> C | Low confidence/conflict | Abstract principles only | UNSELECTED |
| Per-Reference Pattern Analysis | Preserve attributable useful patterns | [USER TO SELECT] | [USER TO SELECT] | Pattern extraction, citations to source evidence | Vision: as needed; Reasoning: medium-high; Context: medium; Structured: required | Q/C balanced | Low confidence | Never reproduces distinctive identity | UNSELECTED |
| Autonomous Concept Generation | Create diverse concepts from policy/history | [USER TO SELECT] | [USER TO SELECT] | Creative ideation, diversity constraints | Vision: no; Reasoning: medium; Context: medium; Structured: required | Q/C balanced | Weak concept QC | No mandatory concept approval by default | UNSELECTED |
| User Idea Expansion | Refine a user seed into a concept | [USER TO SELECT] | [USER TO SELECT] | Instruction following, creativity | Vision: no; Reasoning: medium; Context: medium; Structured: required | Q/C balanced | Concept fails QC | Preserve explicit user constraints | UNSELECTED |
| Reference + User Idea Synthesis | Blend idea with abstract DNA | [USER TO SELECT] | [USER TO SELECT] | Constraint synthesis, originality | Vision: optional; Reasoning: high; Context: long; Structured: required | Q> C | Boundary-risk finding | No near-copy | UNSELECTED |
| Story Bible | Create canonical story facts/arcs | OpenAI / `gpt-5.6-terra` | NONE | Planning, consistency, JSON schema | Vision: no; Reasoning: low; Context: long; Structured: required | Q/C/S balanced | Fail closed | Bundled with plan + hook contract | USER_APPROVED |
| 20-Chapter Planning | Build objectives, reveals, pacing | OpenAI / `gpt-5.6-terra` | NONE | Long-form planning, retention design | Vision: no; Reasoning: low; Context: long; Structured: required | Q/C/S balanced | Fail closed | Exactly 20 chapters | USER_APPROVED |
| Hook–Story Contract | Define Chapter 0 continuity | OpenAI / `gpt-5.6-terra` | NONE | Continuity, open-loop mapping | Vision: no; Reasoning: low; Context: medium; Structured: required | Q/C/S balanced | Fail closed | Required before production-ready | USER_APPROVED |
| Chapter Generation | Produce one approved-plan chapter | OpenAI / `gpt-5.6-terra` | NONE | English prose, instruction following | Vision: no; Reasoning: none/low; Context: medium-long; Structured: required | S/C/Q balanced | Fail closed | Fast mode combines edit + QC | USER_APPROVED |
| Chapter Recap | Create spoiler-safe prior-state recap | [USER TO SELECT] | [USER TO SELECT] | Concise faithful summarization | Vision: no; Reasoning: low-medium; Context: short; Structured: optional | C/S> Q | Continuity mismatch | Chapters 2–20 only | UNSELECTED |
| Continuity Repair | Correct accepted-state conflict | [USER TO SELECT] | [USER TO SELECT] | Fact tracking, targeted rewrite | Vision: no; Reasoning: high; Context: long; Structured: required | Q> C | Repeated contradiction | Preserve intended arc | UNSELECTED |
| Hook Concept | Select first-3-second pattern and beats | [USER TO SELECT] | [USER TO SELECT] | Retention design, originality | Vision: optional; Reasoning: high; Context: medium; Structured: required | Q> C | Hook QC failure | No fixed shock formula | UNSELECTED |
| Hook Script | Write character dialogue | [USER TO SELECT] | [USER TO SELECT] | Dialogue, timing, safety | Vision: no; Reasoning: medium; Context: medium; Structured: required | Q/C balanced | Timing/Hook QC failure | Max 3 voices | UNSELECTED |
| Hook Visual Prompt | Produce provider-neutral visual plan/prompt | [USER TO SELECT] | [USER TO SELECT] | Visual specification, continuity | Vision: optional; Reasoning: medium; Context: medium; Structured: required | Q> C | Visual continuity failure | Provider adapter transforms it | UNSELECTED |
| Hook Transcript | Align approved dialogue to text | [USER TO SELECT] | [USER TO SELECT] | Transcript/timing fidelity | Vision: no; Reasoning: low; Context: short; Structured: required | C/S> Q | Mismatch with audio | Produces subtitle timing input | UNSELECTED |
| Story Bible QC | Evaluate Story Bible | [USER TO SELECT] | [USER TO SELECT] | Critical reasoning, rubric scoring | Vision: no; Reasoning: high; Context: long; Structured: required | Q> C | Low confidence or critical issue | Separate critic role | UNSELECTED |
| Chapter QC | Diagnose chapter issues | OpenAI / `gpt-5.6-terra` | NONE | Continuity, prose, issue severity | Vision: no; Reasoning: low; Context: medium; Structured: required | Q/C/S balanced | Stop auto-chain on fail | Combined in fast; independent in quality mode | USER_APPROVED |
| Retention Evaluation | Score curiosity/tension/engagement | [USER TO SELECT] | [USER TO SELECT] | Reader-retention rubric | Vision: no; Reasoning: medium; Context: medium; Structured: required | Q/C balanced | Core arc impact | Diagnostic by default | UNSELECTED |
| Final Story QC | Evaluate complete story package | [USER TO SELECT] | [USER TO SELECT] | Long-context criticism, rubric | Vision: no; Reasoning: high; Context: long; Structured: required | Q> C | Critical failure/contradiction | Before production_ready | UNSELECTED |
| Originality / Reference Boundary Analysis | Prevent near-copy | [USER TO SELECT] | [USER TO SELECT] | Comparative reasoning, evidence | Vision: optional; Reasoning: high; Context: long; Structured: required | Q> C | High similarity/risk | Critical gate | UNSELECTED |
| Diversity / Similarity Analysis | Compare new story fingerprints/history | [USER TO SELECT] | [USER TO SELECT] | Embedding + structured comparison | Vision: no; Reasoning: medium; Context: medium; Structured: required | Q/C balanced | Similarity threshold/risk | Uses long-term fingerprints | UNSELECTED |
| Caption Generation | Generate Facebook post caption | [USER TO SELECT] | [USER TO SELECT] | Concise copy, CTA boundaries | Vision: no; Reasoning: low-medium; Context: short; Structured: optional | C/S> Q | Policy/copy QC issue | English only | UNSELECTED |
| Comment / CTA Generation | Generate first-comment CTA | [USER TO SELECT] | [USER TO SELECT] | Concise engagement copy | Vision: no; Reasoning: low-medium; Context: short; Structured: optional | C/S> Q | Policy/copy QC issue | Separate final artifact | UNSELECTED |
| Difficult Creative Rewrite | Repair high-impact creative defects | [USER TO SELECT] | [USER TO SELECT] | High-quality rewriting, constraints | Vision: no; Reasoning: high; Context: long; Structured: required | Q> C | Prior repair fails | Budget-controlled | UNSELECTED |
| Contradictory QC Resolution | Reconcile conflicting evaluator reports | [USER TO SELECT] | [USER TO SELECT] | Adjudication, evidence review | Vision: optional; Reasoning: high; Context: long; Structured: required | Q> C | Reports remain unresolved | Cannot lower thresholds | UNSELECTED |
| Escalation | Handle allowed high-complexity cases | [USER TO SELECT] | [USER TO SELECT] | Strong reasoning, auditability | Vision: as required; Reasoning: high; Context: long; Structured: required | Q> C | User-approved policy trigger | Never self-introduces a provider | UNSELECTED |
| Embeddings / Similarity | Produce semantic vectors | [USER TO SELECT] | [USER TO SELECT] | Embeddings, stable versioning | Vision: no; Reasoning: none; Context: chunked; Structured: API-native | C/S> Q | Provider unavailable | Store embedding version | UNSELECTED |
| Video Generation | Produce raw visual clips | [USER TO SELECT LATER] | [USER TO SELECT LATER] | Text/image-to-video, continuity | Vision: output; Reasoning: provider-specific; Context: prompt; Structured: manifest | Q/C balanced | Provider failure | Mock in MVP | DEFERRED |
| TTS / Voice | Produce character dialogue audio | [USER TO SELECT LATER] | [USER TO SELECT LATER] | Multi-voice, timing, controllability | Vision: no; Reasoning: no; Context: script; Structured: timing manifest | Q/C balanced | Audio QC failure | Mock in MVP | DEFERRED |
| Audio / Music / SFX | Provide royalty-safe audio assets | [USER TO SELECT LATER] | [USER TO SELECT LATER] | Licensing/provenance, mixing metadata | Vision: no; Reasoning: no; Context: brief; Structured: asset manifest | Q/C balanced | Rights/audio QC issue | Mock in MVP | DEFERRED |

## User selections to complete later

At minimum, the user must choose for each non-deferred workload:

1. Primary provider and model.
2. Approved fallback provider and model, or explicitly `NONE`.
3. Any allowed escalation assignment and its budget/quality trigger.
4. Selection status/version effective date.

The user must choose video/TTS/audio providers later, after identifying/evaluating the intended tools. No final model assignment is locked until the completed matrix is explicitly approved.

## Prototype roster (not workload assignments)

The following candidates were requested for proof-of-concept evaluation. They do not fill any Primary/Fallback cell above and are not production approvals.

| Candidate | System role | Status | Constraint |
|---|---|---|---|
| ChatGPT Free | Manual comparison baseline | CANDIDATE_RESEARCHED | Not an automated API provider; do not use UI/browser automation for production calls. |
| Google Gemini API Free tier | Cloud LLM/multimodal trial candidate | CANDIDATE_RESEARCHED | Quota-limited; Cloud Boundary and free-tier data handling apply. |
| Ollama + Qwen3 0.6B | Local adapter/structured-output smoke-test candidate | CANDIDATE_RESEARCHED | Current 4 GB RAM / integrated-GPU prototype PC cannot safely support 4B/8B. Do not treat this small model as a full-story quality candidate. |
| Muse.ai | Manual workflow/product-reference candidate | NOT_A_MODEL_PROVIDER | Do not assign to workloads until a suitable public programmatic inference API is verified. |
| MuMuAINovel | Candidate reusable story-engine codebase | DEFERRED | Requires source, architecture, dependency, and license review before any reuse. |

When a prototype is approved for a workload, create a new `model_assignment_version` and fill the relevant Primary/Fallback fields with the exact provider/model identifier and trial evidence.
