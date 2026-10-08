# 11 — Engineering Standards

Status: **PROPOSED (revision 3).** These rules apply to every line written in Phase 2, by humans and by AI agents (they are mirrored in `AGENTS.md`). The goals, in priority order: **correct → readable → fast enough (measured) → abstractable.** Where "fast" and "readable" conflict, readability wins *unless a benchmark proves the budget is missed* — then the optimisation is isolated, commented with the benchmark, and covered by tests.

## 1. Principles

1. **Code is read far more than written.** Optimise for the next reader (including a future LLM agent with a small context window). A newcomer should be able to open any module and understand its single job in under a minute.
2. **Make illegal states unrepresentable.** Pydantic models with validators, enums instead of strings, `NewType` ids, frozen/immutable data, `Literal` unions.
3. **Pure core, impure edges.** Computation is pure and deterministic (domain, events, sim, league logic). I/O (DB, files, CLI, future network) lives at the edges behind ports.
4. **Explicit over implicit.** Dependencies passed in, randomness passed in, config passed in. No globals, no singletons, no module-level mutable state, no import-time side effects.
5. **Small, named, boring.** Small functions with intention-revealing names beat comments and cleverness.
6. **Measure, don't guess.** No optimisation without a profile; no claim of "fast" without a benchmark.

## 2. Clean-code rules (mostly enforced by tooling, not goodwill)

| Rule | Limit / convention | Enforced by |
|------|--------------------|-------------|
| Function length | ≤ 25 lines typical; hard cap 40 statements-ish (`PLR0915` ≤ 30) | ruff |
| Cyclomatic complexity | ≤ 8 per function (`C901 max-complexity = 8`) | ruff |
| Parameters | ≤ 5 (`PLR0913`); more ⇒ a parameter object (frozen dataclass/Pydantic model) | ruff |
| Nesting depth | ≤ 3; use guard clauses/early returns | review + ruff `PLR1702` |
| Module size | ≤ 400 lines; ≤ 1 public concept per module (SRP) | architecture test |
| Magic numbers | none; named constants or config (`PLR2004`); formulas live in named functions with a docstring giving the formula in plain words | ruff |
| Boolean flag parameters | not allowed in public APIs (use an enum, two functions, or a strategy) | ruff `FBT` |
| Naming | full words, domain vocabulary (glossary below); verbs for functions, nouns for types; no `data`, `info`, `manager`, `util`, `helper`, `tmp`, single letters except math (`x`, `y`, `t`, `dt`, `xg`) | review + ruff `N` |
| Types | 100% annotated; `mypy --strict`; no `Any` in `sim/`/`domain/`; `object`/`Protocol` over `Any` | mypy |
| Docstrings | every public module/class/function: one-line summary (imperative), then *why* / units / ranges when not obvious; **comments explain why, never what** | ruff `D` (pydocstyle, Google style) |
| Immutability | frozen models/dataclasses, tuples over lists in hot data, no in-place mutation of inputs | ruff + review; `sim/state.py` is the only place with mutable state (documented) |
| Errors | specific exception classes (`InvalidSetupError`, `ConflictError`, `SchemaVersionError`); no bare `except`; no silent `pass`; errors carry ids and context | ruff `BLE`, `TRY`, `S110` |
| Dead code / TODOs | none merged; TODOs must reference a changelog/roadmap id | vulture + ruff `FIX` |
| Imports | absolute, sorted, no wildcard, no cycles | ruff `I`, architecture test |
| Formatting | `ruff format` (single formatter) | CI |

**What good looks like** (illustrative style, not final code):

```python
HOME_CROWD_LIFT_MAX = 0.025  # share of a mental attribute a full, noisy crowd adds; tuned in M8

def crowd_lift(stadium: Stadium, fanbase: Fanbase, attendance: int) -> float:
    """Return the 0..HOME_CROWD_LIFT_MAX boost home mental attributes receive.

    Scales with how full the ground is, how close the stands are and how
    passionate the fans are; an empty stadium gives no lift.
    """
    fill = min(attendance / stadium.capacity, 1.0)
    intensity = fill * stadium.atmosphere * stadium.proximity * fanbase.passion
    return HOME_CROWD_LIFT_MAX * intensity
```

Each function does one thing, takes explicit inputs, returns a value, and states its range.

**Glossary (ubiquitous language)** is kept in `docs/glossary.md` and used verbatim in code: *moment, chain, phase, possession, press, line, shape, slot, role, duty, snapshot, sheet, matchday, window, ledger, modifier, mood, storyline, digest, profile, knob*. A term has one meaning everywhere; renames are done project-wide.

## 3. SOLID, concretely

| Principle | How it shows up here | Guard |
|-----------|----------------------|-------|
| **S**ingle responsibility | One module = one reason to change: `fatigue.py` only fatigue; `discipline.py` only fouls/cards; `standings.py` only table computation; `schedule.py` only fixtures. Orchestrators (`api.py`, `season.py`) only sequence collaborators — no formulas. | module-size + one-concept review rule |
| **O**pen/closed | New behaviour is *added*, not edited: roles, traits, formations, injury types, mood kinds, development curves, balance profiles are **data** (YAML → validated models); new event type = new class registered in the union; new sim behaviour = new component implementation selected by `model_profile`; new transfer rule = new policy object. | data-driven tables; registry tests ("adding a role requires zero Python edits" has a test that loads a synthetic role) |
| **L**iskov | Any implementation of a Protocol is substitutable: the **same contract test suite** runs against every repository (memory/SQLite), every sim component version, every `ManagerPolicy`, every Narrator/Voice stub. | `tests/contracts/` parametrised over implementations |
| **I**nterface segregation | Small, role-specific Protocols: `WorldReader` (read-only) vs per-entity repositories; the sim sees only `MatchSetup` (never a repository); `ManagerPolicy` sees only `ManagerObservation`; extension Protocols have 1–3 methods. | architecture test on imports; review |
| **D**ependency inversion | High-level modules depend on abstractions they own: `sim` depends on nothing but domain/events; `league` depends on **ports** (`ports.py`), never on SQLAlchemy; implementations are wired only in the **composition root** (`cli/`, `tests/factories`). | import matrix test |

**Other patterns used, deliberately few:** *Strategy* (sim components, transfer valuation, manager policy), *Factory/Builder* (world generator, test factories, `build_match_setup`), *Repository + Unit of Work* (persistence), *Pipeline* (daily tick stages), *Registry* (events, roles, traits, state kinds), *Value objects* (frozen models). No inheritance hierarchies deeper than 2; prefer composition and Protocols over base classes.

## 4. DRY — single source of truth

- **Schemas:** Pydantic models are the only definition; JSON Schema, docs tables and TS types are *generated*. Field usage tags (`__usage__`) are the single source for the S/L/R documentation counts.
- **Invariants:** implemented once in `verify/`, reused by tests, the `--strict` flag, soak runs and the production pre-air gate.
- **Constants & tunables:** one `SimConfig`/YAML per concern; no number appears twice. Shared maths (`squash`, `gauss`, interpolation, clamping) lives in `sim/mathx.py`/`domain/maths.py`.
- **Config duplication across layers:** league/transfer/mood/development config models share a `ConfigBase` and the same load/merge/hash utilities (`config_io.py`).
- **Repositories:** a generic `JsonDocumentRepository[T]` implements get/save/list/delete for the JSON-document tables; concrete repositories add only their specific queries.
- **Tests:** builders and helper assertions (`tests/factories`, `tests/helpers`); contract suites reused across implementations; golden updates through one command.
- **Docs and release notes** are generated where possible (schema docs, change log from fragments, CLI help from the same option definitions).
- **Detection:** `pylint --disable=all --enable=duplicate-code` (min 6 similar lines) in T1; `vulture` for dead code.
- **Counter-rule (avoid over-abstraction):** *rule of three* — duplicate once if the cases might diverge; extract on the third occurrence, or immediately if the logic encodes a domain rule that must never differ. Abstractions are introduced to **remove duplication or create a seam we test/swap**, not "just in case". A Protocol needs ≥ 2 implementations or a concrete test/seam reason.

## 5. Abstractability without confusion

- **Seams are few, named, documented:** the pure sim API; component Protocols inside the sim; repository ports; extension Protocols (Narrator, MemoryUpdater, VoiceSynthesizer, EventSink, ManagerPolicy). Each seam is described in one paragraph at the top of its module and in `04-architecture.md`.
- **Depth over breadth:** a reader follows *at most* `api → component → helper` (3 hops) to understand any behaviour; no "manager of managers", no deep inheritance, no metaclass magic, no decorators that hide control flow (except `@property`, `@dataclass`, `@cached_property`, `@pytest.fixture`).
- **Public API per package** is exported explicitly in `__init__.py` (`__all__`); everything else is private (`_name`), so refactors don't ripple.
- **Dependency injection by constructor/arguments**, composition in one place per executable.

## 6. Performance standards

### 6.1 Budgets (asserted by `tests/performance/`; baseline stored; see 10 §6)

| Operation | Budget (reference: 4-core dev laptop) | Notes |
|-----------|----------------------------------------|-------|
| Simulate one match (events validated) | mean ≤ **150 ms**, p95 ≤ 220 ms, p99 ≤ 300 ms | validation share ≤ 30%; frames off |
| Same, frames at 1 s | ≤ 220 ms | interpolation only |
| Persist one match (≈ 1,300 events + summary + deltas) | ≤ 120 ms | batch `executemany`, WAL |
| Read a stored match log | ≤ 25 ms | single indexed query |
| Full 56-match season, 4 workers (matchday-parallel) | ≤ 12 s total, incl. persistence | matches in a matchday are independent ⇒ `ProcessPoolExecutor`, merged in fixture order (still deterministic) |
| Daily tick, non-match day | mean ≤ 50 ms | |
| Transfer window (8 clubs, all days) | ≤ 3 s | |
| Off-season rollover (development + intake + retirements) | ≤ 3 s | |
| 20 seasons end-to-end | ≤ 6 min | no super-linear drift |
| World generation | ≤ 5 s | |
| CLI start-up (`--help`) | ≤ 400 ms | lazy imports of heavy modules |
| Memory (league run) | RSS ≤ 250 MB; per-match sim peak ≤ 60 MB | `tracemalloc` test |

*Exception, M4-M7 (Track A):* the simulate-one-match budget is not yet met (about 0.4 s CPU on the build container at M4); `tests/performance/test_sim_budget.py` is only an order-of-magnitude tripwire (0.5 s best of 3) until the M8 optimisation pass asserts the table above. The milestone reports carry the measured number.

### 6.2 How we get there without making code unreadable

- **Architecture does most of the work:** pure data-in/data-out, no I/O in the sim, matchday parallelism, pre-simulation buffer (nothing is simulated on the live path).
- **Hot path discipline** (only in `sim/`): `__slots__` dataclasses for mutable state, tuples for static tables, integer ids/indices internally (strings only at the event boundary), pre-computed per-match tables (role offsets, effective-attribute caches recomputed only when energy/mood bucket changes), squared-distance comparisons instead of `sqrt` where only ordering matters, no per-moment allocation of temporary lists in the decision loop, local variable binding for repeated attribute access *only where the profile shows it matters*.
- **Pydantic only at boundaries:** inside the loop we use light dataclasses; events are built once through their model (validated). If profiling shows event construction dominates, the fallback (trusted construction in production + full validation in the verification gate and tests) is documented, benchmarked and reviewed *before* adoption — never silently.
- **DB:** WAL mode, `synchronous=NORMAL`, batch inserts, indexed query columns (L3), no N+1 in repositories (`list_by_club` returns hydrated models in one query), prepared statements, connection reuse via the unit of work.
- **Algorithms:** O(players) per position update with a 4 s cadence; spatial queries limited to the 10 nearest players; transfer AI prunes candidates by position/budget/age before scoring; standings recomputed incrementally with a full-recompute check in tests.
- **numpy** only in tooling (balance harness, analytics); the sim stays plain Python for exactness and determinism.
- **Rule:** every optimisation PR includes *before/after numbers*, the benchmark that proves it, and a comment (`# Perf: <benchmark id> — <why this shape>`) so the next reader doesn't "clean it up" into a regression.

### 6.3 Regression defence
Budgets as tests (T1), baseline comparison on a pinned runner (T2), op-count assertions (hardware-independent), per-milestone profile attached to the milestone report.

## 7. The change log (human release notes **and** machine/agent context)

**One source of truth: change fragments.** Every change that touches `src/`, `data/`, `schemas/`, `docs/design/` or tooling adds one small file in `changes/unreleased/` (towncrier-style, avoids merge conflicts, structured for tools):

```markdown
---
id: 0007                     # zero-padded, unique, monotonically increasing
date: 2026-10-07             # real calendar date of the change
type: added                  # added | changed | fixed | removed | deprecated | security | perf | refactor | test | docs | build
scope: [sim, events]         # domain | events | sim | league | persistence | seed | cli | tools | schemas | data | docs | ci
milestone: M5
breaking: false
schema_version_impact: none  # none | patch | minor | major   (events/models JSON Schema)
sim_version_impact: none     # none | patch | minor | major   (changes match output for the same seed ⇒ must not be `none`)
config_impact: false         # SimConfig/YAML keys added/changed/removed
migration: false             # needs an Alembic migration / data migration
summary: Add offside detection to the pass resolver.     # one line, imperative, user-facing
---
Longer explanation for humans and agents: what changed, why, how it was verified (tests/benchmarks),
links to design sections (e.g. 02 §5.3), follow-ups, and any migration notes. Optional.
```

Tooling (`uv run changelog …`, `tools/changelog.py`, M0):

- `changelog new --type added --scope sim --milestone M5 "summary"` creates the next fragment (agents and humans use the same command).
- `changelog check` (pre-commit + CI): fails if changed files under `src/ data/ schemas/` have no fragment; if golden digests changed without a fragment declaring `sim_version_impact ≠ none` **and** a bumped `SIM_VERSION`; if `schemas/` changed without `schema_version_impact ≠ none` and a bumped `SCHEMA_VERSION`; if a fragment is malformed.
- `changelog build` compiles `CHANGELOG.md` (Keep-a-Changelog layout, grouped by type, newest first, with an **Unreleased** section always current) — this file is *generated, never hand-edited*.
- `changelog release X.Y.Z` moves fragments into `changes/released/X.Y.Z/`, writes `release-notes/vX.Y.Z.md` (readable notes: highlights, breaking changes, migration steps, sim/schema version bumps, balance-metric deltas from the nightly report) **and** `release-notes/vX.Y.Z.json` (structured, for machines — e.g. a future "patch notes" segment on the channel).
- **Versions:** project SemVer; `SIM_VERSION` and `SCHEMA_VERSION` are separate constants with their own bump rules (above) and are recorded on every match and in every release note.
- **Milestone reports** (`docs/milestones/Mx.md`, written at the end of each milestone): what was built, commands run and their output, test/coverage/mutation numbers, benchmark table vs. budgets, deviations from the design, open follow-ups. A short **`docs/status.md`** (≤ 100 lines: current milestone, what works, how to run, next steps, known issues) is rewritten at each milestone so any agent starting a session reads state in one file.
- **Commits/PRs:** Conventional Commits (`feat(sim): …`) with the fragment id in the footer; the PR template includes the §10 checklist. One fragment per PR (not per commit). Full workflow in §12.

The design phase itself is already logged: see `changes/unreleased/` and the hand-compiled `CHANGELOG.md` (replaced by the generated file in M0).

## 8. Release process (live-channel safe)

1. Feature work merges only with T1 green + changelog fragment.
2. Release candidate: tag `vX.Y.Z-rc`; run **T3** (200-season parity, migration from previous release DB, determinism matrix, shadow week on a copy of the live world — 10 §7).
3. `changelog release`; golden/perf baselines refreshed intentionally (separate commit, reviewed).
4. Deploy: DB backup → migration (offline) → `uv run verify` → `uv run health` → resume.
5. Rollback plan: previous release + DB backup; versions recorded on every match make mixed-version history explicit.

## 9. Documentation standards

- Design docs (`docs/design/`) are updated in the same change that alters behaviour; deviations are recorded in the milestone report and a fragment.
- **ADRs** (`docs/adr/NNNN-title.md`, short: context / decision / consequences) for decisions that are non-obvious or hard to reverse (RNG choice, JSON-document persistence, restricted math).
- Module docstring = responsibility + the seam it implements + where it is described in the design.
- README = setup, commands, schema layout, extension points; kept executable by doc tests.
- Generated references (schema docs, CLI reference, config knob table with ranges/effects) are produced by tooling, not typed.

## 10. Review checklist (human or agent, every change)

- [ ] Does each new function/class have one clear job and a name that says it? Could someone understand it without reading its callers?
- [ ] No magic numbers; no flag arguments; no function > 25 lines / complexity > 8 / > 5 params; nesting ≤ 3?
- [ ] No duplicated logic (DRY) — and no abstraction without a second user or a seam? (rule of three)
- [ ] Dependencies injected; no globals; layering respected (architecture test green)?
- [ ] Pure where it can be; I/O only at edges; randomness only via passed `SimRng`; no wall-clock?
- [ ] Types complete; errors specific and informative?
- [ ] Tests: unit + (property/contract/e2e as relevant); regression test for a fix; invariants via `verify/` (not re-implemented)?
- [ ] Performance: budget unaffected, or benchmark attached; no new O(n²) in a loop over players/events?
- [ ] Changelog fragment added with correct impact flags; schema/sim versions bumped if required; docs updated?
- [ ] Code reads top-down like prose; comments say *why*.

## 11. Agent rules (Claude Code and Cursor) and the end-of-turn quality gate

**These standards are also delivered to the tools as rules** (no generator: the Cursor files are plain copies, changed together with the Claude files):

| Layer | Location | Purpose |
|-------|----------|---------|
| Claude rules | `.claude/rules/*.md` (optional frontmatter `paths:`; always-on when absent) | The compact, imperative form of §1–§5, §12 plus architecture/sim/testing/docs rules |
| Claude Code | the files above (loaded natively; scoped by `paths:`) + `AGENTS.md` (via `CLAUDE.md` import) | Always-on rules (`core`, `git-workflow`) and path-scoped rules that load only when relevant files are touched (keeps context small) |
| Cursor | `.cursor/rules/*.mdc` (same body; `description`/`globs`/`alwaysApply` frontmatter) + `AGENTS.md` (read natively) | Same content, Cursor's format |

`AGENTS.md` is a short index (read natively by both tools); the detailed rules are the files above; this document keeps the rationale.

**End-of-turn gate (hook).** At the end of **every agent turn** a Stop hook runs the fast quality tier and only lets the agent finish when it passes completely:

- Claude Code: `.claude/settings.json` → `Stop` hook → `tools/hooks/gate.py --agent claude`; a failing gate exits 2, which keeps Claude working with the failure report.
- Cursor: `.cursor/hooks.json` → `stop` hook → `tools/hooks/gate.py --agent cursor`; a failing gate returns a `followup_message` that Cursor submits automatically (`loop_limit` 8).
- What runs: `uv run check` = **ruff check, ruff format --check, mypy --strict, architecture tests, unit/property/contract tests (fast tier T0), golden digests, changelog check**. Budget ≤ 60 s.
- **Pass means 100%**: any failure blocks. Not a "mostly green".
- To avoid wasting time the gate **skips when no watched file changed since the last green run**.
- To avoid an infinite loop on a broken environment (e.g. no `uv`, no network), it **gives up loudly after `FOOTY_GATE_MAX_RETRIES` consecutive failures (default 8; set `0` for never give up)** — the notice states the gate is still red; it is never reported as a pass.
- The hook is stdlib-only and a no-op until `pyproject.toml` exists (M0), so it never traps the design phase. It is itself covered by unit tests in M0 and linted like all code.
- The hook enforces *tests and static checks*; it cannot judge readability — that remains the review checklist (§10) and CI (T1+).

**Rules for agents in short** (full text in `.claude/rules/`): read `docs/status.md` and the relevant design sections first; follow §2–§5; add a changelog fragment and update docs for every change; never introduce nondeterminism or I/O into the pure core; smallest change that solves the problem; never weaken a gate; follow the git workflow below.

## 12. Git workflow — one branch and one PR per milestone, atomic commits

Goal: history is a clean, bisectable story and the owner reviews **one coherent unit of work at a time**: a milestone.

**One PR per milestone (revision 5).** Each milestone (M1, M2, ...) is delivered as **a single branch and a single pull request**. The slice list in 06-milestones.md is the *commit plan* for that branch, not a list of separate PRs: no stacked PRs, no splitting a milestone across several PRs (unless the owner asks for it). The branch is named `<type>/<milestone>-<slug>` (`feat/m1-domain-models`, `feat/m4-sim-kernel`), types `feat fix refactor perf test docs build ci chore`, and is created from fresh `main` before the first edit. Keep it current by merging or rebasing `main` into it. Work outside a milestone (a fix, a docs change) gets its own small branch and PR.

**Reviewability comes from atomic commits, not from many PRs.**
- One logical change per commit; **every commit builds and passes `uv run check`** (so `git bisect` works). Tests live in the same commit as the code they cover. Refactors, formatting, dependency bumps and golden regeneration are **never mixed** with behaviour changes in one commit.
- Target **<= 400 changed lines per commit** (generated files excluded). The owner reviews the milestone PR commit by commit, so each commit must be understandable on its own. `uv run pr-size` reports the size of a whole branch and is informational for milestone PRs.
- Message: Conventional Commits `type(scope): imperative summary` (<= 72 chars), a body that explains *why* (and trade-offs), footer with the changelog fragment id and `BREAKING CHANGE:` if any. A `commit-msg` hook validates the format.
- Commit as you go; tidy (squash fixups, reorder, reword) **before** requesting review.
- The milestone PR description has one section per slice of the commit plan so the reviewer can follow the story.

**Human review checkpoint (mandatory).** Before **any** push or PR the owner reviews the work. At the end of a milestone the agent: has every slice committed locally with `uv run check --tier pr` green → writes the milestone report (`docs/milestones/Mx.md`) and refreshes `docs/status.md` → presents a review package (branch, commits grouped by slice, `git diff --stat`, what/why, verification, impact flags, deviations, open doubts; offers the diff pane) → **waits for an explicit go-ahead** → only then pushes the branch and runs `gh pr create` (one PR). If a milestone is long, the owner may ask for an interim look at the local branch; that is a preview, not approval to push. Changes requested in review become new atomic commits (or a tidy-up of still-unpushed history). The owner can still review again on GitHub before merging.

**Pull request.**
- Title = Conventional Commit line naming the milestone. Description follows `.github/pull_request_template.md`: **Summary** (what/why), **Changes** (per slice), **How verified** (commands and results), **Impact** (SIM_VERSION, SCHEMA_VERSION, config, migration, performance numbers), **Docs and changelog** (fragment ids), **Follow-ups**, **Checklist** (section 10).
- Opened only when `uv run check --tier pr` is green locally; CI must be green to merge.
- Merge strategy is the owner's (merge commits so far); delete the branch after merge. Release tags `vX.Y.Z` on `main`.
- Review expectations: the description lets the reviewer understand intent without reading the diff first; reviewers use the section 10 checklist; blocking comments are about correctness, clarity, determinism, performance or tests, not taste.

**Standing instruction for agents:** create the milestone branch before the first edit; commit atomically as you go; when the milestone is complete and the gate is green, **stop at the human review checkpoint**; push the branch and open **one** PR (`gh pr create`) **only after the user's explicit approval**; **do not** open stacked or per-slice PRs, merge PRs, push to `main`, force-push shared branches, skip hooks, or rewrite published history unless the user says so. Never delete a branch another open PR is based on. Remote: `https://github.com/AB-Law/FootyStreams` (public; `gh` is authenticated as the owner, who therefore cannot approve their own PRs).

**Protection and automation:** `.github/` PR template, CODEOWNERS (the owner), workflow `ci.yml` (PR tier on Windows and Linux, Python 3.12 and 3.13, plus an informational PR size report), `commit-msg` and `pre-commit` hooks. Branch-protection settings are listed in the M0 report for the owner to apply (they need repository admin rights).
