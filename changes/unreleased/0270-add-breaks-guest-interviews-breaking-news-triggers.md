---
id: 0270
date: 2026-10-10
type: added
scope: [cli, extensions, docs]
milestone: design
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Add breaks, guest interviews, breaking news triggers and replay to the channel
---
Adds to the 24/7 channel: breaks (a slideshow of invented sponsor ads, the table or results and the next match, made without the model), post-match interviews with a guest drawn from their own appearance in their club colours (a fourth chair, a lower third, memories of the visit), BREAKING NEWS (a flash that cuts in at once, then the hosts react from the headline alone, with a banner), triggers (uv run channel breaking/guest, or the Channel page control room posting to viewer/serve.mjs), and a replay: the feed and segment files are kept for four hours (--keep-hours), the page lists what aired and replays it with pause and a scrubber. Segment files now carry their own ticker and memories (the feed stays small); segments asked for are slotted in with everything still to come moved back. The rundown is six steps per fixture. Design in docs/design/15-the-channel.md. No engine, schema or sim change. Verified by unit tests (rundown, feed insertion, guests, breaks, breaking news, triggers, the loop, slides and the guest/breaking desk in the viewer) and a live run against qwen3.5-9b.
