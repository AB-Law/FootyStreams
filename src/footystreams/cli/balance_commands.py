"""The ``balance`` commands: each prints its answer and returns an exit code."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from footystreams.balance import knobs, overrides
from footystreams.balance import state as sweep_state
from footystreams.balance.evaluate import MetricResult, Verdict, evaluate, failures, total_loss
from footystreams.balance.fit import DEFAULT_BOUNDS, FitResult, FitSettings, fit, format_candidate
from footystreams.balance.report import format_failures, format_report
from footystreams.balance.runner import BalanceRunner
from footystreams.balance.sensitivity import (
    Baseline,
    Sensitivity,
    Sides,
    SweepOptions,
    format_matrix,
    noise_floor,
    strongest,
    sweep,
)
from footystreams.balance.targets import Target
from footystreams.cli.balance_session import Session
from footystreams.domain.versions import SIM_VERSION
from footystreams.sim.config import config_hash

EXIT_OK, EXIT_OFF_TARGET = 0, 1
# The columns of the sensitivity matrix unless --metrics says otherwise: the headline numbers.
MATRIX_METRICS = (
    "goals_per_match",
    "home_goals_per_match",
    "away_goals_per_match",
    "draw_pct",
    "home_win_pct",
    "scoreless_pct",
    "five_plus_goals_pct",
    "second_half_goal_share_pct",
    "late_goal_share_pct",
    "shots_per_team",
    "on_target_per_shot",
    "goals_per_shot_pct",
    "pass_completion_pct",
    "possession_spread_pp",
    "corners_per_match",
    "offsides_per_match",
    "fouls_per_match",
    "yellows_per_match",
    "reds_per_match",
    "penalties_per_match",
    "injuries_per_match",
    "substitutions_per_team",
    "early_tactical_subs_per_match",
    "favourite_win_pct_medium",
    "favourite_win_pct_large",
    "underdog_win_pct_medium",
    "home_favourite_edge_pp",
)
STRONGEST_PER_METRIC = 3
VALIDATION_SEED_OFFSET = (
    1_000_003  # a different seed set, so a fit is judged on matches it never saw
)


def _split(text: str | None) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()] if text else []


def run(session: Session) -> int:
    """Play the matches and print the targets table."""
    with session.runner() as runner:
        results = evaluate(runner.run(session.config), session.profile.metrics)
    print(format_report(results, session.arguments.matches, session.profile.name))
    if session.arguments.failures and failures(results):
        print()
        print(format_failures(results))
    return EXIT_OFF_TARGET if failures(results) else EXIT_OK


def chosen_knobs(session: Session) -> list[knobs.Knob]:
    """The knobs named by ``--knobs`` and ``--group``; at least one of them is required."""
    arguments = session.arguments
    if arguments.knobs:
        return knobs.choose(session.config, _split(arguments.knobs))
    prefixes = tuple(f"{group}." for group in _split(arguments.group))
    if not prefixes:
        msg = "this command needs --knobs or --group (for example --group shot,passing)"
        raise ValueError(msg)
    return [k for k in knobs.discover(session.config) if k.path.startswith(prefixes)]


def _matrix_targets(session: Session) -> dict[str, Target]:
    metrics = session.profile.metrics
    names = _split(session.arguments.metrics) or [m for m in MATRIX_METRICS if m in metrics]
    unknown = [name for name in names if name not in metrics]
    if unknown:
        msg = f"unknown metrics: {', '.join(unknown)}"
        raise ValueError(msg)
    return {name: metrics[name] for name in names}


def _sweep_settings(session: Session, targets: dict[str, Target]) -> dict[str, object]:
    """Everything that makes two sweeps comparable; a resumed run must match it exactly."""
    arguments = session.arguments
    return {
        "profile": session.profile.name,
        "world": str(arguments.world),
        "matches": arguments.matches,
        "seed": arguments.seed,
        "min_gap": arguments.min_gap,
        "relative": arguments.relative,
        "sides": arguments.sides,
        "metrics": list(targets),
        "config_hash": config_hash(session.config),
        "sim_version": SIM_VERSION,
    }


def _start(
    session: Session, runner: BalanceRunner, targets: dict[str, Target]
) -> tuple[sweep_state.Header, dict[str, Sensitivity]]:
    """Resume from ``--state`` when it exists, else measure the base and begin the file."""
    path: Path | None = session.arguments.state
    settings = _sweep_settings(session, targets)
    if path is not None and path.exists():
        return sweep_state.load(path, settings)
    base = evaluate(runner.run(session.config), targets)
    header = sweep_state.Header(settings, {r.name: r.value for r in base}, noise_floor(base))
    if path is not None:
        sweep_state.write_header(path, header)
    return header, {}


def _progress(session: Session, total: int, finished: int) -> Callable[[Sensitivity], None]:
    """Record each result to ``--state`` and say how far the sweep is on stderr."""
    path: Path | None = session.arguments.state
    count = [finished]

    def record(item: Sensitivity) -> None:
        if path is not None:
            sweep_state.append(path, item)
        count[0] += 1
        print(f"[{count[0]}/{total}] {item.knob.path}", file=sys.stderr, flush=True)

    return record


def sensitivity(session: Session) -> int:
    """Nudge the chosen knobs and print which metric each one moves (resumable with --state)."""
    arguments = session.arguments
    targets = _matrix_targets(session)
    chosen = chosen_knobs(session)
    with session.runner() as runner:
        header, done = _start(session, runner, targets)
        options = SweepOptions(
            arguments.relative,
            Sides(arguments.sides),
            done,
            _progress(session, len(chosen), sum(k.path in done for k in chosen)),
        )
        baseline = Baseline(session.config, header.base_values)
        found = sweep(runner.run, baseline, chosen, targets, options)
    lines = [
        f"profile {session.profile.name}, {arguments.matches} matches, "
        f"+-{arguments.relative:.0%}, sides {arguments.sides}",
        format_matrix(found, list(targets), header.noise),
    ]
    for name in targets:
        top = ", ".join(
            f"{s.knob.path} {(s.effects or {})[name]:+.2f}"
            for s in strongest(found, name, STRONGEST_PER_METRIC)
        )
        lines.append(f"moves {name}: {top}")
    text = "\n".join(lines)
    print(text)
    if arguments.report is not None:
        arguments.report.write_text(text + "\n", encoding="utf-8")
    return EXIT_OK


def _summary(label: str, results: list[MetricResult]) -> str:
    passed = sum(r.verdict is Verdict.PASS for r in results)
    return f"{label}: {passed}/{len(results)} PASS, loss {total_loss(results):.3f}"


def _validate(session: Session, found: FitResult) -> list[str]:
    """Re-measure the current config and the candidate on seeds the fit never saw."""
    arguments = session.arguments
    seed = arguments.seed + VALIDATION_SEED_OFFSET
    candidate = overrides.apply(session.config, found.overrides)
    with session.runner(arguments.validation_matches, seed) as runner:
        before = evaluate(runner.run(session.config), session.profile.metrics)
        after = evaluate(runner.run(candidate), session.profile.metrics)
    title = f"on {arguments.validation_matches} fresh matches (seed {seed})"
    return [_summary(f"{title}, current", before), _summary(f"{title}, candidate", after)]


def _parse_bounds(text: str) -> tuple[float, float]:
    low, _, high = text.partition(",")
    bounds = (float(low), float(high))
    if not 0.0 < bounds[0] < bounds[1]:
        msg = f"--bounds must be two positive numbers, low,high; got {text!r}"
        raise ValueError(msg)
    return bounds


def fit_command(session: Session) -> int:
    """Fit the chosen knobs to the profile and print or write a candidate config."""
    arguments = session.arguments
    out: Path | None = arguments.out
    if out is not None and out.exists():
        msg = f"{out} already exists; a fit never overwrites a file"
        raise ValueError(msg)
    chosen = chosen_knobs(session)
    bounds = _parse_bounds(arguments.bounds) if arguments.bounds else DEFAULT_BOUNDS
    with session.runner() as runner:
        settings = FitSettings(
            bounds=bounds,
            max_evaluations=arguments.max_evals,
            restarts=arguments.restarts,
            seed=arguments.seed,
        )
        found = fit(runner.run, session.config, chosen, session.profile.metrics, settings)
    notes = [
        f"balance fit: profile {session.profile.name}, {arguments.matches} matches, "
        f"seed {arguments.seed}, {found.evaluations} evaluations",
        f"knobs: {', '.join(k.path for k in chosen)}",
    ]
    text = format_candidate(found, notes)
    if out is None:
        print(text)
    else:
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}")
    for line in _validate(session, found):
        print(line)
    return EXIT_OK


HANDLERS: dict[str, Callable[[Session], int]] = {
    "run": run,
    "sensitivity": sensitivity,
    "fit": fit_command,
}
