# Pixel replay viewer (prototype)

A silent browser page that replays a recorded match as pixel art scaled up without smoothing: the
canvas is 640x452, the scoreboard and the top-down view are drawn on a logical 320x226 screen at twice
the size, and the broadcast view is drawn at the full 640x452. It exists to iterate on the look before a live feed exists. It is **not a milestone**: no
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

Open `http://127.0.0.1:5173/` for the **match**. Use the top nav **News desk** (or
`http://127.0.0.1:5173/studio.html`) for the separate news page. Options on the match URL:
`?replay=replays/other`, `?t=2500`, `?autoplay=1`, `?names=all`. Space toggles play/pause.
`preview.html` is the review sheet for player art. Other commands: `npm run typecheck`, `npm test`.

## News desk (separate page)

The news desk is **not** inside the match stream. It is its own tab (`studio.html`) and plays a
~2–3 minute desk script as one pixel-art broadcast on a 480x270 canvas: up to four anchors seated at
a desk (front-facing, dressed from their speaker id so the same person always looks the same), a
speech bubble over whoever is talking that types out at speaking pace, a lower third naming them, a
night-skyline window with the stadium floodlit, a wall screen for the current beat and one for the
score, an ON AIR sign and a scrolling ticker. Beside the picture are play/pause, previous/next line, a
scrubber and a transcript you can click to jump to a line.

```bash
uv run narrate --home SEI --away BUK --seed 2 --engine template
# LM Studio (local server on; falls back to templates if down):
uv run narrate --home SEI --away BUK --seed 2 --engine lmstudio --model "qwen/qwen3.5-9b"
```

That writes `viewer/replays/commentary.json`. Then open the News desk tab. Facts only — no invented
lore. Options: `?script=replays/other.json`, `?t=40` (start 40 s in), `?autoplay=1`; space plays and pauses.

How it is built (all text is the proportional mixed-case pixel font in `src/pixelfont.ts`, so the
bubble, lower third and ticker are drawn in the canvas and can be recorded as one picture later):

- `src/commentary.ts`: the script's shape, which line is on at time `t` (`cueAt`), who speaks, and the
  score read from the intro line. `src/bubble.ts` wraps a line to the bubble, pages it if it is too
  long and types it out; both are pure functions of the time, so scrubbing shows the same thing.
- `src/anchor-look.ts`, `src/anchor.ts`: the anchors. A look comes from a hash of the speaker id
  (seat picks the jacket, and nobody at the desk shares a hairstyle); the sprite is painted pixel by
  pixel with a face that blinks, glances at the speaker and moves its mouth while the bubble types.
- `src/studio-set.ts` (wall, window, desk), `src/studio-screens.ts` (wall screens, ON AIR, bug),
  `src/studio-hud.ts` (bubble, lower third, ticker), `src/studio.ts` (puts them together, one
  `draw(ctx, t)`), `src/studio-app.ts` (the page).

## Channel (24/7)

`channel.html` is the News desk as a channel that never goes off air. A producer writes an endless feed
and the page plays whatever the wall clock says is on air, joining in the middle (design:
`docs/design/15-the-channel.md`). The talk comes only from **LM Studio** (local server on, a model
loaded; no template fallback), so run this first:

```bash
uv run channel --model qwen/qwen3.5-9b        # keeps about 10 minutes of airtime queued; Ctrl+C to stop
```

Then open the **Channel** tab (`http://127.0.0.1:5173/channel.html`). Options: `--ahead-minutes 10`,
`--lead-seconds 15`, `--temperature 0.8`, `--max-segments N`, `--reset` (forget the show bible and the
feed), `--endpoint URL`. It writes `viewer/replays/channel/` (`index.json`, one `seg_NNNNNN.json` per
segment, and `bible.json`, the hosts' memory); delete that folder, or pass `--reset`, for a fresh show.

What is on: a preview and a recap of each fixture of the show's own double round robin (matches are
simulated when their recap is made), a post-match interview with a guest (the player of the match, or a
manager, drawn from their own appearance in their club's colours), club histories, manager and player
files, the table after each matchday, banter, and a **break** between fixtures: a slideshow of invented
sponsor ads, the table or results and the next match. Three hosts remember: results, who predicted what, and the running jokes and
opinions they came up with, all listed under "What the desk remembers". The page shows only what has
aired: the ticker and the memories come with each segment, and a match report is listed by its fixture,
never its score.

**Going back.** The feed keeps the last four hours (`--keep-hours`). "Earlier on VPL News" lists what has
aired; pick one to watch it again (pause and a scrubber appear, it carries on through what aired after it,
and "Back to live" returns), exactly as it went out.

**Breaking news and guests.** The control room panel on the page, or the command line, asks the running
producer for things:

```bash
uv run channel breaking "Seisund County sack their manager"   # a flash within seconds, cutting in, then the hosts react
uv run channel guest Jorsen                                  # interviewed after the current segment
```

Both leave a file in `replays/channel/triggers/`; the control room posts to `viewer/serve.mjs`
(`POST /api/trigger`, this machine only; restart `npm start` once to pick it up). If the producer or the model is away the page shows a stand-by scene and picks up when
segments arrive. `src/channel.ts` (what is on air at a time), `src/channel-app.ts` (the page),
`src/desk-page.ts` (styles shared with the News desk).

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
- `src/poses.ts` (top-down view), `separate` in `src/interpolate.ts`: players are kept 3.2 m apart so
  nobody walks through the man on the ball. Two paths that cross would swap the pair's places in one
  frame, so the push is averaged over the moments around the time shown: they slide past each other.
  In the top-down view a tackle sends the tackler in and a take-on sways the carrier.
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

## The broadcast view, figures and scenes
The page opens in a side-on "TV gantry" view (the Top-down button switches back). `sideview.ts` projects the
pitch as a trapezoid (the far touchline is drawn at 74% of the near one's size, rows are spaced the way a
camera spaces them), draws the stands, boards, striped grass, markings and goals, and sorts players, referee
and ball back to front. The camera pans along the pitch only, following the ball or a chosen player. Wide
shows the whole pitch; Broadcast shows about half of it. The Names button cycles name tags: the player on the
ball (and the one being followed), everybody, or nobody. The referee wears black and yellow.

Players are articulated figures (`figure.ts`): thighs, shins, arms, torso and a head with hair, face and
beard, painted pixel by pixel from joint angles and cached per look and pose. A run is a stride cycle by
speed; a scene poses the joints directly (`STANCES`).

Scenes (`choreo.ts`, `scenes.ts`) are scripts in the carrier's own frame (forward, toward the middle, up):
the seven skill moves, a take-on that ends in a tackle (won, missed, a foul, a slide that wins or fouls, a
heavy touch), a header and a dead-ball kick with a wall. The ball is its own object: it follows a player
only where a script says so, and each touch is placed on a boot taken from the figure's skeleton. A move
is done with either foot (the legs are swapped), by the foot his `preferred_foot` and `weak_foot` give.

`sceneplan.ts` turns each `dribble`, `tackle`, header (`shot` with `body_part: "head"`) and restart in the
log into a plan, built for where the replay really has the two players: a defender too far away to be part
of it is left out, one behind the carrier is brought in chasing from behind, one on the other side is put
there, and a long way to cover gets a longer run in, so nobody dashes or runs through the carrier. Nothing
is invented: the replay's own positions stay the truth, and `sceneplay.ts` plays the plan as offsets from
them, anchors the defender and a loose ball where the contact was as the carrier runs on, and eases
everyone and the ball back onto the replay at the end. `skillposes.ts` is now only the top-down view's
version of the same moves.

## Deliberately missing

Audio, TTS, live engine/WebSocket sink, replays of goals, shirt numbers on screen, linesmen (the
referee is a drawn guess, not sim data), camera moves, formation-aware kits for goalkeepers beyond a
plain colour, and other event types (pass, shot, foul and so on are accepted and ignored). Studio
commentary is a prototype (templated or local-LLM script beside the replay), not the M13 Narrator seam.

## Known limits

- There are no frames during the half-time break, so the "half time" banner appears over the first
  seconds of the second half.
- A pass is placed to the nearest second, so a very long pass crosses the pitch in under a second.
- Event overlays are timed to the latest frame before the event (one second resolution).
- Scenes are played from the replay's 1 Hz positions, so a tackle that the sim places a second away from
  where the two players are shown is left out (only duels with the defender within 7 m at the contact play),
  and a scene never changes who has the ball afterwards.
- Playback time is the frame index (one frame per sim second); the scoreboard shows the match clock
  of the frame on screen, so the two differ by the break.
