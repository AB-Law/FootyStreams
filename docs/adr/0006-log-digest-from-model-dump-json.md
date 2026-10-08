# ADR 0006: the log digest hashes `model_dump_json()` lines

Status: proposed (2026-10-08, Track A / M4). Needs the owner's sign-off in the M4 PR review. Refines
docs/design/02 section 13.

## Context
Design 02 section 13 defined `log_digest` as the sha256 of the *canonical* NDJSON of every event
(sorted keys, `canonical_json`). Measured in M4 (benchmark `M4-digest`), canonical serialisation cost
about 70 ms per match, nearly half of the 150 ms budget (docs/design/11 section 6.1).

## Decision
`events/digest.py` hashes one `event.model_dump_json()` line per event: keys in field-declaration
order, floats as shortest round-trip decimals, no whitespace. The simulator records the digest and
`verify` recomputes it with the same function (`event_line`, `log_digest`). About 10 ms per match.
Everything else is unchanged: the digest still covers all events before the summary.

## Consequences
- The digest is a pure function of the validated model, but it now depends on pydantic's serialiser
  and on field-declaration order. Reordering fields changes JSON Schema property order, which the
  schema drift test already forces through a `SCHEMA_VERSION` bump, and `uv run golden check` fails
  on any pydantic change that alters the bytes. Pydantic stays pinned in `uv.lock`.
- Anything that persists or replays NDJSON and wants to re-verify the digest must write lines with
  `event_line`, not `canonical_json`.
- If the owner prefers the original definition, switch `event_line` back to `canonical_json` and
  accept about 60 ms more per match; the goldens are regenerated under a `SIM_VERSION` bump.
