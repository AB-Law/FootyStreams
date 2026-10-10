---
id: 0268
date: 2026-10-09
type: changed
scope: [docs]
milestone: design
breaking: false
schema_version_impact: none
sim_version_impact: none
config_impact: false
migration: false
summary: Redo the news desk as a broadcast scene with anchors, speech bubbles and a ticker
---
Replaces the side-view footballer sprites and HTML caption of the first news desk. The desk is now one 480x270 pixel canvas: front-facing seated anchors dressed from a hash of the speaker id, speech bubbles that type at speaking pace (paged when long), a lower third, ticker, wall screens (beat and score read from the intro line), ON AIR sign and a night-skyline window with the stadium. New proportional mixed-case pixel font (src/pixelfont.ts); transcript with click-to-seek beside the picture. Viewer-only: no engine, schema or sim change. Verified by viewer unit tests (font, bubble timing, script helpers, looks, anchor pixels, and a smoke test that every studio draw call lands on a whole pixel) and by viewing it in the browser.
