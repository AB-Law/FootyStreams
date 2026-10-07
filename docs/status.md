# Project status

Updated at the end of milestone M0 (2026-10-07). Read this first; then the design section for your task.

## Where we are
- Design is complete (`docs/design/`, index in `docs/design/README.md`; decisions in `09-schema-decisions.md`).
- **M0 (scaffold and test/quality infrastructure) is implemented** on local stacked branches awaiting review;
  see `docs/milestones/M0.md`. Merged to `main` so far: the baseline docs, the uv project and `uv run check`.
- There is no simulation, domain model or league code yet. **Next: M1** (domain models and schema export,
  about 15 small PRs listed in `docs/design/06-milestones.md`).

## How to work here
```bash
uv sync
git config core.hooksPath .githooks   # once per clone
uv run check                           # fast gate (about 10 s); --tier pr adds coverage
uv run changelog new "Imperative summary" --type added --scope sim --milestone M1
uv run changelog build                 # regenerate CHANGELOG.md after adding/changing fragments
uv run pr-size --base origin/main      # keep PRs under 400 changed lines (cap 800)
```
- Workflow: branch from `main`, atomic Conventional Commits, gate green, **stop for the owner's review**, only
  then push and open a PR (`.claude/rules/git-workflow.md`). Never push or open a PR without that approval.
- A Stop hook runs `uv run check` after every agent turn and blocks until it passes.

## What exists (src/footystreams)
| Package | State |
|---------|-------|
| `domain`, `events`, `sim`, `league`, `persistence`, `extensions`, `analytics`, `runtime`, `cli`, `seed` | Documented empty skeletons; layering rules enforced by the architecture checker |
| `verify` | `Violation` type only |
| `tools` | `check` (quality gate), `architecture` (layering/purity checker), `changelog` (new, check, build, release), `commitmsg`, `prsize`, shared `git`/`paths` |

Also: `tools/hooks/gate.py` (Stop hook, stdlib only), `.githooks/`, `.github/workflows/ci.yml`, ADRs in `docs/adr/`,
glossary in `docs/glossary.md`.

## Known issues and caveats
- CI has never run: it is proven only by its first run on GitHub (Python 3.13 is untested locally).
- Branch protection on `main` is not configured (needs the repository owner; checklist in `docs/milestones/M0.md`).
- `changelog check` does not yet verify that `SIM_VERSION` / `SCHEMA_VERSION` were bumped (constants do not exist).
- The architecture checker matches imports by name (aliases like `import math as m` are not tracked).
- Claude and Cursor rule files are maintained by hand in pairs (`.claude/rules` and `.cursor/rules`).
