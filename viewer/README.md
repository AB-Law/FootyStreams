# Pixel replay viewer (prototype)

A silent browser page that replays a recorded match as a 320x180 pixel pitch scaled up without
smoothing. It exists to iterate on the look before a live feed exists. It is **not a milestone**: no
engine, schema or sim change, and it lives outside `src/` and `tests/` so the Python gate ignores it.

Design context: `docs/design/08-roadmap.md` section 3a (the studio, social and stream wishlist).

## Record a match

A recorded match is about 15 MB (5,800 frames of 22 players), so it is recorded on demand and
git-ignored (`viewer/replays/`), not committed. From the repository root:

```bash
uv run python viewer/scripts/record_match.py --home SEI --away BUK --seed 2
```

This writes `viewer/replays/replay.ndjson` (the sim's event log with one `frame` per second, the same
as `uv run sim --format ndjson --frames --frame-interval 1`) and `viewer/replays/replay.meta.json`.
Frames only carry player ids, so the meta file adds what is needed to dress them: both clubs' names
and kits, and each player's name, shirt number and `Appearance`. Seed 2 of SEI v BUK ends 2-2 with
four goals, a yellow card and several substitutions. On Windows set `PYTHONUTF8=1` if the console
complains about names.

## Run it

```bash
cd viewer
npm install        # once: typescript only
npm start          # builds with tsc, serves http://127.0.0.1:5173/
```

Open `http://127.0.0.1:5173/`. Options in the address: `?replay=replays/other` (another recording),
`?t=2500` (start at a second), `?autoplay=1`. Space toggles play and pause. Other commands:
`npm run typecheck`, `npm test` (Node's built-in test runner, no extra dependencies).

## How it is built

- `src/store.ts`: `MatchStore.onEvent(event)` is the **one** entry point for events. The file reader
  (`src/source.ts`) calls it for every line; a live source would call it as events arrive. Unknown
  event types are ignored, so new ones (M13 review events and so on) never break it.
- `src/interpolate.ts`: blends the 1 Hz frames to the draw rate (about 30 fps). It never extrapolates,
  and holds a position across a reset (kick-off, the half-time side swap) instead of sliding.
- `src/overlays.ts`, `src/hud.ts`: scoreboard, clock, goal banner, yellow/red card flash,
  substitution note, half-time and full-time. Windows are in real seconds, stretched at 4x and 16x.
- `src/flights.ts`: passes and shots fly as short animations between the event's start and end points
  (a shot on a curve with a trail, long balls arcing), taking over from the 1 Hz ball while in the air.
  Shots read `target`, `curve` and `speed_mps` when the sim provides them and otherwise go straight.
- `src/referee.ts`: the referee is not in the sim's frames. He is a deterministic follower: he trails
  the play at running speed (never faster than 6.5 m/s) and goes to fouls and bookings.
- `src/pitch.ts`, `src/sprites.ts`, `src/palette.ts`, `src/font.ts`: everything is drawn in code from
  the kit colours and appearance (skin tone, hair, facial hair); no art assets, and a 3x5 bitmap font.
- `src/events.ts`, `src/meta.ts`: hand-written types for only the events used, each pointing at its
  Python source. They are not generated: the broadcast schema export waits for the next schema bump.

## Deliberately missing

Audio, commentary, TTS, LLM text, studio scenes, recording or encoding for a stream, any WebSocket or
engine sink, replays of goals, shirt numbers on screen, linesmen (the referee is a drawn guess,
not sim data), camera moves, formation-aware kits for goalkeepers beyond a plain colour, and other
event types (pass, shot, foul and so on are accepted and ignored).

## Known limits

- There are no frames during the half-time break, so the "half time" banner appears over the first
  seconds of the second half.
- Flights start at the second of their event, queued one after another; a busy second can look
  slightly out of step with the players, who are only known once a second.
- Event overlays are timed to the latest frame before the event (one second resolution).
- Playback time is the frame index (one frame per sim second); the scoreboard shows the match clock
  of the frame on screen, so the two differ by the break.
