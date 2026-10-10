# 15 — The channel: a 24/7 desk show that remembers

**Status: PROTOTYPE, built on `feat/news-report-prototype` (2026-10-10). Not a milestone, not M13.** It is the first running version of the studio-show wish in 08 §3a: a news desk that never goes off air, whose hosts have memories, history and running jokes, with ad breaks, guests, breaking news and a replay. It lives in `extensions/show/` (pure), `cli/channel*.py` (I/O) and `viewer/channel.html`. The decisions below were the owner's; what is still open is in section 9.

## 1. What it is

`uv run channel` keeps a **feed** (`viewer/replays/channel/`) filled with segments of a show: previews and recaps of matches the world really plays, post-match interviews, club histories, manager and player files, the table, plain banter, and breaks between them. Three hosts sit at the desk, and a guest takes a fourth chair. They tease each other, call back to old jokes and settle the predictions they made. `channel.html` plays whatever the wall clock says is on air right now, joining in the middle like a real broadcast, shows a stand-by scene if nothing is on, and lets you go back through the last few hours.

```
 world files ──▶ Newsroom ──▶ Rundown (plan.py) ──▶ facts.py / facts_match.py ──▶ SegmentBrief
                                  ▲                                                      │
   ShowBible (bible.json) ◀── remember.py ◀── reply.py (checks) ◀── LM Studio ◀── prompt.py
        │                                                                  
        └──▶ feed.py ──▶ index.json + seg_NNNNNN.json ──▶ channel.html (wall clock)
```

## 2. Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Scope | A prototype loop outside any milestone | Same as the news-desk prototype: iterate on the show before the engine sink exists. Wiring the desk in as an engine programme block is later work. |
| Source of talk | **LM Studio only**, no template fallback | The owner wants the channel to sound alive. The cost, accepted: if the model is off the desk has nothing to say. The producer works ahead of the clock and the page shows a stand-by scene; it never airs filler talk. |
| Memory | A JSON **show bible** beside the feed, records in the world's `MemoryRecord` shape | Easy to read and reset, no schema bump. Moving it into the database later is a copy, not a redesign. |

## 3. The rundown

Each fixture is six stretches of airtime: **preview, filler, recap, post-match interview, the table (after a matchday) or another filler, and a break**. The filler rotates club history, banter, manager file, banter, player file, banter, always taking the subject who has been off air longest. The season is a double round robin of the world's clubs (`schedule.py`); fixtures are simulated for real when their recap is made, with a seed fixed by season and fixture, so a restart replays the same match. The show's own table, form and head-to-heads come from the results it has aired. It never writes back to the world database. Everything here is decided from the bible, so a restarted producer picks up exactly where it stopped. Things someone asks for (a guest, breaking news) take airtime without moving the rundown on (`Plan.off_rundown`).

### Breaks

A break (`breaks.py`) is a slideshow of about 25 seconds with **no model involved**, so it can always be made: an invented sponsor, the table or the latest results, another sponsor, and the next match. The sponsors are a fixed bank of invented brands (Grafters Pies, Old Road Taxis...); everything else comes from the bible.

### Guests and interviews

A guest is a real person of the world: after each match the player of the match, or on alternate matches a manager. They are drawn from their own `Appearance` in their club's colours, in the fourth chair at the end of the desk, and introduced by a lower third ("Player of the match"). The prompt gives the model their career, club standing, the match just played and their personality sliders (`interview_style`, humor, ego, sociability, media openness); the guest speaks in the first person, and a reply in which the guest never speaks is rejected. The hosts remember the interview (an `interview` memory shared with the guest's id and club, so the next time the guest or their club comes up it comes back to mind). A guest never owns memories: only the hosts do.

### Breaking news and triggers

Something outside the show can ask for things by leaving a small JSON file in `<feed>/triggers/` (`uv run channel breaking "..."`, `uv run channel guest NAME`, or the control room on the Channel page, which posts to the viewer server). The running producer checks every second:

- **breaking**: a flash goes on air at once (a flashing BREAKING NEWS slide, with no model), cutting off the segment on air, then the hosts react (model-written from the headline alone: they may not add details, causes or numbers) with the banner across the picture and the headline on the ticker. Everything still to come moves back to make room. If the model is away only the flash airs.
- **guest**: the person is booked, and their interview is made and slotted in after the segment on air. If the model is away the booking stays and is made when it returns.

`triggers.py` holds the trigger format and how a name becomes a person; a new kind of trigger is a new `kind` there and a handler in `cli/channel.py`.

## 4. Facts and the model

Every segment starts as a `SegmentBrief`: a goal, the facts, and the names that may be spoken. Match segments reuse `pack_broadcast_brief` (extensions/pack.py); histories use the club, its rivalry and ground, and the club's record on the desk; stories use career stints (`CareerStint`, `ManagerStint`, wider clubs named); banter is seeded from the latest result and the table.

The prompt gives each host a card (humor, interview style, expertise, hometown, catchphrases not used lately, the memories most likely to come to mind) and asks for JSON: lines, new memories, and (previews only) a pick for every host. `reasoning_effort: none` is sent because reasoning models otherwise spend the whole token budget thinking.

**The model may phrase facts; it may not add to them.** `reply.py` rejects a reply, with a reason the model gets on the retry, if:

- it is not the right shape, or has too few lines or only one speaker;
- a speaker is not at the desk;
- a number appears that is not in the facts (numbers must be written as digits, so this can be checked);
- a name from the world appears that the segment does not involve (a part of an allowed name is fine, so "Seisund" is fine for "Seisund County");
- a line repeats one already on air, or one in the same reply;
- a preview lacks a pick from any host.

Text is made safe for the pixel font (accents folded, markup and emoji dropped). After three bad replies the segment is not made; after three failed attempts at the same slot the rundown moves on. If the model is unreachable the producer waits with a growing pause and retries; nothing fake is aired.

What it cannot check: a plausible invented fact that uses no number and no known name ("they have never won away"). The prompt forbids it; the check does not catch it. This is the honest limit of the approach, and why new memories from the model are stored as the model's (`origin: llm`), not as fact.

## 5. Memory

`bible.json` holds `MemoryRecord`s owned by a host and shared with others through `related_ids`. Strength follows 01 §7: importance times a decay whose half-life grows with importance and with every recall, so a joke that keeps coming up stays vivid and a one-off fades. Time is the show's in-world date, which moves a week per matchday.

| Kind | Written by | Example |
|------|-----------|---------|
| `match_moment` | code, after a recap | "Seisund County 2-0 Gathiški Albion on matchday 1 of season 1" |
| `prediction_result` | code, when the pick is settled | "Yizytz picked a draw for ... and was wrong" (wrong picks stick longer) |
| `running_joke`, `opinion`, `anecdote` | the model, as a proposal | "Every time Jorsen takes a bad decision, someone should step in" |

A repeated proposal is recognised by its key and counted as a recall instead of a new memory. Each prompt carries the top memories per host by strength and relevance to the segment's clubs and people. The bible is bounded (300 memories, three seasons of results).

## 6. The feed, the clock and the replay

`index.json` lists the cast and the schedule; each entry is `{id, file, kind, title, headline, label, guest, air_at, duration_s}`. Segments are scheduled **back to back** from the moment the last one ends; a late segment airs `--lead-seconds` after it is ready. The producer makes another whenever less than `--ahead-minutes` of airtime is queued, so it runs ahead of the clock and mostly waits.

**No spoilers.** Because the producer is minutes ahead, each segment file carries the ticker and the memories *as they stand once that segment has aired*, and the feed's `title` is a teaser ("Match report: A v B", never the score); the real `headline` is only shown for what has already aired. The page shows the ticker and memories of the segment on air (or the nearest earlier one that has any: a slotted-in guest or breaking segment carries none, and a segment made ahead of time never leaks what comes after it).

**Replay.** Segments stay in the feed, and their files on disk, for `--keep-hours` (default 4). The page lists what has aired ("Earlier on VPL News"); choosing one plays it from the start with a pause button and a scrubber, carries on through what aired after it, and goes back to live when it catches up (or on "Back to live"). A replay is the same pure function of time as live, so it shows exactly what went out.

Files are written atomically (a retry on Windows if the web server has one open). Segments older than the keep window are deleted.

## 7. The picture

Pure functions of time, as in the news desk: the same hosts in the same seats for good (looks come from a hash of the speaker id, no two share a hairstyle), a bubble that types at speaking pace, a lower third, and the ticker scrolling on a clock that never rewinds. The left screen shows the segment's topic, "Up next" in the last four seconds of a segment, or "Stand by". The right screen is a score, a table or a fact card from the segment. A break fills the picture with its slides (a wipe between them) above the running ticker; a breaking-news segment puts a flashing banner over the lower third. Joining mid-segment shows the same frame everyone else sees.

## 8. Files

| File | Job |
|------|-----|
| `extensions/show/models.py`, `bible.py`, `ledger.py`, `memory.py` | the vocabulary: segments, the bible, tables and form, memory strength |
| `schedule.py`, `plan.py` | the season and the rundown |
| `breaks.py`, `breaking.py`, `facts_interview.py`, `triggers.py` | breaks and the flash, breaking news, guests, the trigger format |
| `newsroom.py`, `facts.py`, `facts_match.py`, `segment_brief.py` | the world indexed for the show; briefs per kind |
| `prompt.py`, `reply.py`, `textutil.py` | the prompt and the checks |
| `remember.py`, `feed.py`, `producer.py` | memory writes, the feed, making one segment |
| `cli/channel.py`, `channel_store.py`, `channel_matches.py`, `lm_client.py` | the loop, the files, the matches, the HTTP |
| `viewer/src/channel*.ts`, `slides.ts`, `studio*.ts`, `anchor*.ts`, `pixelfont.ts`, `viewer/serve.mjs` | the page, the picture, the break slides, and the one POST endpoint for triggers |

## 9. Open and next

- **Voices.** The talk is text. TTS (doc 12) would give real durations and word timings; today a line's length is estimated at 15 characters a second.
- **The engine.** The producer plays its own matches. A real channel would take the world's schedule from `uv run engine` (13) and show the match itself, with this desk as the programme blocks around it. The segment kinds already match the engine's `pre_match` / `post_match` / `matchday_magazine`.
- **The database.** Memories could become `MemoryRecord` rows (a schema bump and the proposals path in 04 §4.4). Names and facts the show invents about hosts should then go through proposals too.
- **More show.** Transfers and injuries (the `WorldEvent` feed), a rota of hosts, season reviews, a "this day in history" from the show's own past, automatic breaking news from the sim (a shock result, a hat-trick) using the same trigger path, and real ad copy with sponsors drawn from the world.
- **The control room** posts to `viewer/serve.mjs` on this machine only (loopback, one custom header). A shared deployment needs real authentication before it is exposed.
- **Several viewers on one clock** works as it is; a remote viewer needs the producer's clock and the browser's to agree (a header offset would fix drift).
- **Cost.** One local-model call per segment (about 10 to 20 seconds on qwen3.5-9b); a hosted model needs a ceiling set first.
