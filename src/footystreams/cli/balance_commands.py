"""The ``balance`` commands: each prints its answer and returns an exit code."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from footystreams.balance import knobs, overrides
from footystreams.balance.evaluate import MetricResult, Verdict, evaluate, failures, total_loss
from footystreams.balance.fit import DEFAULT_BOUNDS, FitResult, FitSettings, fit, format_candidate
from footystreams.balance.report import format_failures, format_report
from footystreams.balance.sensitivity import format_matrix, noise_floor, strongest, sweep
from footystreams.balance.targets import Target
from footystreams.cli.balance_session import Session

EXIT_OK, EXIT_OFF_TARGET = 0, 1
# The columns of the sensitivity matrix unless --metrics says otherwise: the headline numbers.
MATRIX_METRICS = (
    "goals_per_match",
    "shots_per_team",
    "on_target_per_shot",
    "goals_per_shot_pct",
    "pass_completion_pct",
    "draw_pct",
    "fouls_per_match",
    "yellows_per_match",
    "reds_per_match",
    "corners_per_match",
    "offsides_per_match",
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


def sensitivity(session: Session) -> int:
    """Nudge the chosen knobs and print which metric each one moves."""
    arguments = session.arguments
    targets = _matrix_targets(session)
    chosen = chosen_knobs(session)
    with session.runner() as runner:
        base = evaluate(runner.run(session.config), targets)
        found = sweep(runner.run, session.config, chosen, targets, arguments.relative)
    print(
        f"profile {session.profile.name}, {arguments.matches} matches, +-{arguments.relative:.0%}"
    )
    print(format_matrix(found, list(targets), noise_floor(base)))
    for name in targets:
        top = ", ".join(
            f"{s.knob.path} {(s.effects or {})[name]:+.2f}"
            for s in strongest(found, name, STRONGEST_PER_METRIC)
        )
        print(f"moves {name}: {top}")
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
