# Project status

Updated at the end of milestone M1 (local, awaiting review — 2026-10-08). Read this first; then the design section for your task.

## Where we are
- Design is complete (`docs/design/`, index in `docs/design/README.md`; decisions in `09-schema-decisions.md`).
- **M0 is merged** to `main` (scaffold, quality gate, changelog, CI, ADRs).
- **M1 (domain models and schema export) is implemented** on local branch `feat/m1-domain-models`
  awaiting the owner's review before push / one PR. See `docs/milestones/M1.md`.
- **Next after M1 merges: M2 ∥ M4** (seed/world generators and sim kernel) as parallel tracks —
  one branch and one PR per milestone, not stacked slice PRs.

## How to work here
```bash
uv sync
git config core.hooksPath .githooks   # once per clone
uv run check                           # fast gate (about 10 s); --tier pr adds coverage
uv run changelog new "Imperative summary" --type added --scope sim --milestone M2
uv run changelog build                 # regenerate CHANGELOG.md after adding/changing fragments
uv run export-schemas                  # regenerate schemas/ after model changes
uv run pr-size --base origin/main      # informational for milestone PRs
```
- Workflow: branch from `main`, atomic Conventional Commits, gate green, **stop for the owner's review**, only
  then push and open a PR (`.claude/rules/git-workflow.md`). Never push or open a PR without that approval.
- A Stop hook runs `uv run check` after every agent turn and blocks until it passes.

## What exists (src/footystreams)
| Package | State |
|---------|-------|
| `domain` | Full M1 models: types, person/player, ratings/valuation, tactics, club, competition, match, world/transfer/dev, media; `SCHEMA_VERSION` / `SIM_VERSION`; usage registry |
| `events` | MatchEvent discriminated union, summary, MatchResult |
| `cli` | `export-schemas` (argparse) |
| `sim`, `league`, `persistence`, `extensions`, `analytics`, `runtime`, `seed` | Empty skeletons; layering rules enforced |
| `verify` | `Violation` type only |
| `tools` | `check`, `architecture`, `changelog` (incl. SCHEMA_VERSION bump policy), `commitmsg`, `prsize` |

Also: committed `schemas/` (drift-tested), factories/strategies under `tests/`, `tools/hooks/gate.py`,
`.githooks/`, `.github/workflows/ci.yml`, ADRs, glossary.

## Known issues and caveats
- CI / branch protection checklist from M0 still applies where not yet configured on GitHub.
- The architecture checker matches imports by name (aliases like `import math as m` are not tracked).
- Claude and Cursor rule files are maintained by hand in pairs (`.claude/rules` and `.cursor/rules`).
- Mood caps are named defaults only until `mood.yaml` (M2/M9).
