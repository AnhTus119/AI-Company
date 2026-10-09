# Phase 4 — Prototype Evaluation Plan

**Status:** Approved Cloud Boundary for non-sensitive Gemini Free prototype data — 2026-10-07  
**Purpose:** Validate architecture assumptions with a bounded, non-production comparison. This is not an implementation, provider activation, or production run.

## 1. Guardrails

- Run exactly one synthetic `user_idea` StoryRequest at a time; do not use a real reference video, customer data, credentials, unpublished content, or personal data.
- No automatic Facebook publishing, real video/TTS/audio generation, purchase, or background campaign execution.
- ChatGPT Free is manual-only; no UI/browser automation.
- Gemini Pro subscription may be used manually in the Gemini app/AI Studio as a qualitative baseline; it does not itself authorize automated API calls.
- Gemini Free is used only if the user approves the provider-specific Cloud Boundary below and supplies an API key later through local-only settings.
- Ollama + Qwen3 0.6B is a local adapter smoke test, not a prose-quality candidate.
- Muse.ai and MuMuAINovel are excluded from this test because neither is a verified pipeline inference provider.

## 2. Provider-specific Cloud Boundary for the prototype

| Candidate | Allowed input | Explicitly prohibited input | Purpose |
|---|---|---|---|
| Gemini API Free | Synthetic English premise, generic system rubric, generated Story Bible/plan/chapter text, non-sensitive QC prompts | Raw reference media, real creator data, user-identifying data, secrets, credentials, cost/account data, local paths, internal database records | Quality and structured-output trial |
| Gemini Pro subscription | Same synthetic prompts, entered manually in Gemini | Same prohibited inputs; no automated access under the subscription | Human quality-comparison baseline |
| ChatGPT Free | Same synthetic prompts, entered manually by the operator | Same prohibited inputs; no automated access | Human comparison baseline |
| Ollama local | Same synthetic prompts; no network requirement after model download | Secrets should still not be used in prompts/logs | Adapter/schema smoke test |

The prototype report must state that Gemini Free-tier data handling applies. The user approved this restricted boundary on 2026-10-07. Passing this test does not approve Gemini for reference analysis or production work.

## 3. Single-story test seed

Use a deliberately original, non-reference seed:

> A hospital night janitor finds a child’s paper star hidden behind a vending machine. The note on it says, “Please don’t let my dad find me.” The janitor has one night to learn whether the message is current, while protecting the child without accusing an innocent parent.

The seed is only test input; it must be treated as fictional. The expected story profile remains 20 chapters, English-only, adult drama audience, child-safety limits, and a hook contract. During evaluation, generate only the selected artifacts/sections needed for measurement; do not claim a final production package.

## 4. Test sequence

1. **Schema test:** Generate a Story Bible as the canonical structured schema; measure parse/validation success.
2. **Planning test:** Generate the 20-chapter plan and Hook–Story Contract; inspect unresolved threads, payoffs, and Chapter 1 handoff.
3. **Sample prose test:** Generate Chapter 1 plus Chapter 2 recap, each against the plan and accepted state; assess English, continuity, and 500–700 word target.
4. **QC test:** Produce structured Story Bible QC and chapter QC reports using the same rubric.
5. **Originality test:** Confirm the output does not borrow names, dialogue, scenes, visual identity, or sequence from any reference; this test has no reference material.
6. **Operational test:** Record request/result metadata, elapsed time, schema failure, retry need, and any quota or local-resource failure.

Run Gemini Free and ChatGPT manual baseline separately. Run Ollama only for Steps 1 and 4 unless its quality proves unexpectedly adequate; no comparison winner is preselected.

## 5. Scorecard

| Category | Evidence | Pass condition for prototype usefulness |
|---|---|---|
| Structured output | Validation result and repair attempts | Canonical JSON/object is valid or recoverable with one bounded repair |
| Story planning | Bible, plan, Hook–Story Contract | Characters, stakes, timeline, open loop, and payoff are coherent |
| English prose | Chapter 1 and Chapter 2 recap | Readable English, within target length, no obvious safety violation |
| Continuity | Prior-state comparison and QC | No severe contradiction between Bible, plan, Chapter 1, and recap |
| Originality/safety | Review report | No copying signal or critical policy violation |
| Operational viability | Latency, quota/errors, resource observations | Completes without uncontrolled retry, secret exposure, or policy bypass |

The result is one of `useful_for_further_trial`, `adapter_only`, `needs_hardware_or_quota_change`, or `not_suitable`. No result creates a production assignment automatically.

## 6. Required records

For each candidate record: provider/model/version, run ID, assignment version (`prototype-v1`), prompt-template version, Cloud Boundary decision, schema outcome, concise QC summary, elapsed time, token/usage data when available, quota/error, operator observations, and final classification. Do not persist API keys or raw secrets.

## 7. Exit criteria

This test is complete when the comparison report exists and the user decides one of:

1. Continue Gemini as a controlled prototype candidate;
2. Keep Ollama only as a local adapter test;
3. Upgrade/change hardware before further local-model testing; or
4. Stop external testing and return to architecture/design work.
