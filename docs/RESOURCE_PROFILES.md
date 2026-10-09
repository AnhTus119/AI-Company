# Resource Profiles — One Codebase, Different Machines

**Decision:** 2026-10-09, following the user's instruction to run the first version on the current 4 GB Windows PC and later support stronger machines and public GitHub users. The user subsequently designated an 8 GB office PC as the representative mainstream machine; this is a product test target, not a measured market average.

This document supersedes the single-stack PostgreSQL/RabbitMQ assumption in Phase 3–5 where it conflicts. Product rules, Story Bible, chapter continuity, QC, originality, Cloud Boundary, KPI, and Output Profiles are identical in both profiles.

| Profile | Intended deployment | Authoritative state | Work transport | Local concurrency |
|---|---|---|---|---|
| `lite` (default) | One low-memory Windows PC, including the current 4 GB prototype machine | SQLite database on a local, non-synced disk, WAL mode | Database polling against durable tasks | At most one worker; zero when memory/budget/provider headroom is insufficient |
| `standard` | Stronger single PC or future multi-process deployment | PostgreSQL | Dramatiq + RabbitMQ; database still controls task claims and transitions | Calculated from actual RAM/CPU, provider limits, budget, queue, and requested cap |

## Hardware validation targets

| Target | Supplied configuration | Default expectation |
|---|---|---|
| Minimum prototype | Current Windows PC: 11th-gen Core i3-1115G4, 4 GB RAM, integrated Intel graphics, SSD | Lite; one worker maximum and pause when free RAM is too low |
| Representative mainstream PC | User-supplied example: Core i3-14100F (4 cores/8 threads), 8 GB RAM, Radeon R7 240 4 GB, 256 GB NVMe SSD | Lite remains the safe default; benchmark before enabling Standard services or more parallel work |
| Higher-memory PC | Exact hardware not yet supplied | Auto-detect available RAM/CPU, then allow operator-configured limits; validate with benchmarks and migration tests |

The R7 240 is **not** an assumed AI-inference accelerator. The MVP must not require a local GPU, a local LLM, Docker, PostgreSQL, or RabbitMQ on either of the first two targets. An 8 GB machine is not automatically a Standard deployment: actual free RAM, background applications, storage headroom, and workload measurements decide whether the heavier services are worthwhile.

The current PC showed 97% RAM use in the supplied screenshot. The scheduler must defer new work when available RAM falls below its safe threshold; a 4 GB machine can run the lightweight control plane but cannot be promised 60 completed packages per day without throughput testing. No local LLM is required. Gemini API Free is limited to approved, non-sensitive prototype data.

## Storage and recovery

- The Lite database defaults to an application data directory under Windows `LOCALAPPDATA`, not the OneDrive project directory. `AI_COMPANY_DATA_DIR` may override the location; choose a local disk, not a network or synchronized folder.
- SQLite uses WAL, foreign keys, a busy timeout, and full synchronous durability. WAL permits readers and a writer to overlap, but still has one writer at a time; short transactions and a single worker are required. [SQLite WAL](https://sqlite.org/wal.html) · [Appropriate uses](https://www.sqlite.org/whentouse.html)
- Task claim uses an atomic conditional update. API startup places prior running tasks on hold; an operator must confirm recovery before they may be claimed again.
- Both profiles preserve checkpoint, failure, audit, and backup requirements. RabbitMQ messages are transport hints only; durable task state belongs to the selected database.

## Portable configuration

Profile selection is explicit via `AI_COMPANY_PROFILE=lite|standard`; model assignments, output root, and provider credentials remain separate configuration. This is a runtime choice, never a branch in story generation rules. The safe worker count is the minimum of the operator request, provider slots, budget slots, and machine capacity. The Standard RAM-per-worker value is only a conservative initial estimate; it must be calibrated with actual provider and media workloads before claiming optimal throughput.

Installing Lite requires only core dependencies. Standard-specific PostgreSQL/RabbitMQ libraries are optional dependencies. Changing from Lite to Standard later requires a verified backup and an application-level data/artifact migration tool; changing the environment variable alone must never make old work disappear. The migration tool is still to be implemented and tested before public release.

## Publication requirements

Before GitHub release, provide reproducible setup for both profiles, configuration examples without secrets, migration/backup/restore procedures, hardware-aware defaults, tests on representative low/high-memory machines, and a license/dependency review. Do not publish a claim that every machine achieves the 60/day target; report measured throughput by configuration.
