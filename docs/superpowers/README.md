# Superpowers Plan Status

Last reviewed: 2026-03-30

This index records the actual status of the plans in `docs/superpowers/plans` against the current branch `chore/continue-superpowers-factor-runtime`.

## Status Legend

- `planned`: plan written on the current branch, not yet executed
- `done`: implemented in the current branch
- `done-foundation`: implemented in the current branch and later extended by newer plans
- `active-runbook`: not a backlog; still used as an operator checklist
- `branch-only`: work exists on another branch but is not merged into the current branch

## Plan Index

- `2026-03-20-hyperliquid-factor-research-pipeline.md`
  - Status: `done-foundation`
  - Notes: foundational research pipeline is implemented and extended by later portfolio/runtime work

- `2026-03-21-factor-strategy-platform.md`
  - Status: `branch-only`
  - Notes: strategy-lifecycle work exists on `sdd/factor-strategy-platform`, but is not merged into the current branch

- `2026-03-22-auto-factor-portfolio-platform.md`
  - Status: `done`
  - Notes: current branch contains the portfolio persistence, ranking, deployment APIs, and frontend workflow

- `2026-03-22-backend-lint-debt-cleanup.md`
  - Status: `done`
  - Notes: historical cleanup plan with completion notes already recorded in the file

- `2026-03-22-factor-portfolio-go-live-checklist.md`
  - Status: `active-runbook`
  - Notes: keep as an operator checklist for verification and release rehearsal

- `2026-03-27-factor-cleanup-pass-1.md`
  - Status: `done`
  - Notes: current branch contains the documented cleanup and verification notes

- `2026-03-27-factor-runtime.md`
  - Status: `done`
  - Notes: current branch uses the factor runtime split as the main deployment profile

- `2026-03-30-current-flow-consolidation.md`
  - Status: `done`
  - Notes: current branch now uses one canonical factor UI flow plus one canonical smoke/regression entry, without adding a separate strategy layer

## Current Product Line

The merged product line in this branch is:

`Factor Research Workspace -> Portfolio Deployments -> Live Gate -> Factor Runtime`

That is the effective successor to the older `Factor Strategy` lifecycle proposal for this branch, unless the strategy branch is merged later.
