"""Release notes for one published version, as readable Markdown and as structured JSON."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from footystreams.tools.changelog.build import render_sections
from footystreams.tools.changelog.fragment import Fragment, Impact
from footystreams.tools.changelog.store import Release

NOTES_DIR = "release-notes"
_IMPACT_ORDER = (Impact.NONE, Impact.PATCH, Impact.MINOR, Impact.MAJOR)


def strongest_impact(impacts: Sequence[Impact]) -> Impact:
    """The largest of several impacts (none < patch < minor < major)."""
    return max(impacts, key=_IMPACT_ORDER.index, default=Impact.NONE)


def render_notes(release: Release) -> str:
    """Render human-readable release notes."""
    fragments = release.fragments
    parts = [f"# Release v{release.version} ({release.date.isoformat()})"]
    breaking = [f for f in fragments if f.breaking]
    migrations = [f for f in fragments if f.migration]
    if breaking:
        parts.append(_list("## Breaking changes", breaking))
    if migrations:
        parts.append(_list("## Migration steps required", migrations))
    parts.append(
        "## Version impact\n"
        f"- Simulation output (`SIM_VERSION`): **{_sim_impact(fragments)}**\n"
        f"- Schemas (`SCHEMA_VERSION`): **{_schema_impact(fragments)}**"
    )
    parts.append("## Changes\n\n" + "\n\n".join(render_sections(fragments)))
    return "\n\n".join(parts) + "\n"


def release_json(release: Release) -> str:
    """Render machine-readable release notes (sorted keys, stable output)."""
    document = {
        "version": release.version,
        "date": release.date.isoformat(),
        "sim_version_impact": str(_sim_impact(release.fragments)),
        "schema_version_impact": str(_schema_impact(release.fragments)),
        "changes": [_fragment_json(fragment) for fragment in release.fragments],
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def write_release_notes(root: Path, release: Release) -> list[Path]:
    """Write `release-notes/v<version>.md` and `.json`; return the paths."""
    folder = root / NOTES_DIR
    folder.mkdir(exist_ok=True)
    outputs = {
        folder / f"v{release.version}.md": render_notes(release),
        folder / f"v{release.version}.json": release_json(release),
    }
    for path, text in outputs.items():
        path.write_text(text, encoding="utf-8", newline="\n")
    return list(outputs)


def _sim_impact(fragments: Sequence[Fragment]) -> Impact:
    return strongest_impact([fragment.sim_version_impact for fragment in fragments])


def _schema_impact(fragments: Sequence[Fragment]) -> Impact:
    return strongest_impact([fragment.schema_version_impact for fragment in fragments])


def _list(heading: str, fragments: Sequence[Fragment]) -> str:
    return "\n".join([heading, *(f"- **{f.id}** {f.summary}" for f in fragments)])


def _fragment_json(fragment: Fragment) -> dict[str, object]:
    return {
        "id": fragment.id,
        "date": fragment.date.isoformat(),
        "type": str(fragment.type),
        "scope": list(fragment.scope),
        "milestone": fragment.milestone,
        "summary": fragment.summary,
        "body": fragment.body,
        "breaking": fragment.breaking,
        "migration": fragment.migration,
        "config_impact": fragment.config_impact,
        "sim_version_impact": str(fragment.sim_version_impact),
        "schema_version_impact": str(fragment.schema_version_impact),
    }
