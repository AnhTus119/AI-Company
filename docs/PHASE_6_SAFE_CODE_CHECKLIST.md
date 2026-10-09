# Phase 6 — Safe Implementation Checklist

Code has already begun. No additional hardware specification, model subscription, or API key is required for the next offline/mock increments. Safety comes from small, reversible changes and evidence, not a promise that code cannot fail.

## Required before each new increment

1. Read the current PRD, Phase 5 contracts, resource profiles, and affected code. Preserve unrelated or user-authored changes.
2. Define one narrow behavior and its fail-closed boundary. A mock result must stay marked mock and must never create `production_ready` or spend external budget.
3. Add a focused test for the success path and at least one failure/restart/idempotency or resource-limit path. Run the full suite after the change.
4. Keep source, test fixtures, and configuration free of secrets. Do not call cloud providers or install background services in a test without explicit scope and approval.
5. For any database schema change, add a versioned migration, backup/restore test, and compatibility check before opening an existing user database. Never silently recreate or drop user data.
6. Record exactly what was verified and what remains unverified; do not label the MVP complete because a mock path passes.

## Before a real one-story dry run on the 4 GB PC

- Verify local disk headroom and a database backup; use a non-OneDrive runtime directory.
- Verify HTTP transport and the local worker as separate processes, not only direct function calls.
- Verify low-memory deferral, crash/restart recovery, duplicate task delivery, and explicit operator confirmation.
- Complete sequential chapter/continuity data, mock media artifacts, integrity checks, and the five-file export path.
- Confirm all mocks remain excluded from Production KPI and cannot reach final human approval.

## Before real providers or public GitHub release

- Approve provider/model assignments, Cloud Boundary permissions, cost cap, and non-sensitive test data separately.
- Benchmark 4 GB and the user-designated 8 GB reference PC; report throughput rather than assume 60 packages/day.
- Test Standard services, Lite→Standard data/artifact migration, backup/restore, installation, license/dependency inventory, and clean-machine setup.
