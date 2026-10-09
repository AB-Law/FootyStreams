# Pixel replay viewer (prototype)

A silent browser page that replays a recorded match as a 320x226 pixel pitch scaled up without
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
- `src/flights.ts`: a shot flies as a short animation to its target (on a curve with a trail).
  Shots read `target`, `curve` and `speed_mps` when the sim provides them and otherwise go straight.
- `src/referee.ts`: the referee is not in the sim's frames. He is a deterministic follower: he trails
  the play at running speed (never faster than 6.5 m/s) and goes to fouls and bookings.
- `src/camera.ts`: a follow camera (Full, 2x, 3x buttons; 2x by default, `?zoom=3`) that glides after
  the ball so players and tackles are drawn large. Its position depends only on the time, so
  scrubbing is exact. The ball itself is drawn at the carrier's feet and passes carry it between
  players (`src/interpolate.ts`); only shots keep their own flight.
- `src/poses.ts`, `separate` in `src/interpolate.ts`: players are kept 2 m apart so nobody walks through
  the man on the ball; a tackle sends the tackler in (a slide when the tackle is won, a foul puts the
  other player on the ground, a missed one is sidestepped) and a take-on sways the carrier, all from
  the real `tackle` and `dribble` events.
- Set pieces (`src/poses.ts`): the taker of a corner, free kick, goal kick or penalty takes a run-up and
  lunges at the kick; a throw-in is taken with both arms over the head and the ball held up, on
  the line. The kick is found where the still ball first moves again. The sim places the wall, the
  box crowd and the throw-in outlets (`sim/setpiece_shape.py`) and the frames show them walking in.
- `src/deadtime.ts`: stoppages where the ball stands still (throw-ins, goal kicks, injuries,
  celebrations) are played 3x faster after a short lead-in, shown by `>>` in the corner.
- `src/pitch.ts`, `src/sprites.ts`, `src/palette.ts`, `src/font.ts`: everything is drawn in code from
  the kit colours and appearance (skin tone, hair, facial hair); no art assets, and a 3x5 bitmap font.
- `src/events.ts`, `src/meta.ts`: hand-written types for only the events used, each pointing at its
  Python source. They are not generated: the broadcast schema export waits for the next schema bump.

## Stats, lineups and maps
Beside the pitch the page shows lineups (left), live statistics (right) and an analysis drawer below. All of
it is computed in the browser from the replay at the current time, so scrubbing updates it.

- `stats.ts` turns the store's event log and running sums over the frames into team statistics (possession,
  field tilt, momentum over the last five minutes, xG, shots, passes, tackles, a pressing metric, distance),
  player tallies and a form figure. `analysis.ts` builds the map data from the same log.
- Maps are drawn by `mapview.ts`, one team attacking left to right: pass network, pass lines, press map,
  heatmap, shots and average shape. Choose the window (whole match, last 15 or last 5 minutes) and a player,
  or click a player in the lineup.
- The lineup needs the formation, lineup and bench that `record_match.py` writes into the meta file; replays
  recorded before that show the statistics and maps without lineups.

## The broadcast view and skill moves
The page opens in a side-on "TV gantry" view (the Top-down button switches back). `sideview.ts` projects the
pitch as a trapezoid (the far touchline is about 60% the size of the near one, rows are spaced the way a
camera spaces them), draws the stands, boards, striped grass, markings and goals, and sorts players, referee
and ball back to front. The camera pans along the pitch only, following the ball or a chosen player. Wide
shows the whole pitch; Broadcast shows about half of it. `profile.ts` holds the side-on player art (facing
right, flipped to face left), with run, lean, feint, kick and flick poses.

Dribbles carry the move the sim chose (`skill_move`, schema 0.6.0): `skillposes.ts` gives each move its
shape (player shift, ball path, ball lift, pose, a turn for the roulette) and `poses.ts` plays it for 1.6 s.
The defender is not shown reacting yet: the event does not name him.

## Deliberately missing

Audio, commentary, TTS, LLM text, studio scenes, recording or encoding for a stream, any WebSocket or
engine sink, replays of goals, shirt numbers on screen, linesmen (the referee is a drawn guess,
not sim data), camera moves, formation-aware kits for goalkeepers beyond a plain colour, and other
event types (pass, shot, foul and so on are accepted and ignored).

## Known limits

- There are no frames during the half-time break, so the "half time" banner appears over the first
  seconds of the second half.
- A pass is placed to the nearest second, so a very long pass crosses the pitch in under a second.
- Event overlays are timed to the latest frame before the event (one second resolution).
- Playback time is the frame index (one frame per sim second); the scoreboard shows the match clock
  of the frame on screen, so the two differ by the break.
