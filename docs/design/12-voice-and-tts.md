# 12 — Voice and TTS: what to use, and how to make it not sound like AI

Status: **PROPOSED (revision 4).** TTS itself is **out of scope for this task** — but the `VoiceProfile` schema and the `VoiceSynthesizer` seam are in scope and must not paint us into a corner. This document (a) settles what we *design for now*, (b) lays out the provider options and a decision process for the TTS phase, and (c) lists the techniques that decide whether a commentary channel sounds like a broadcast or like a screen reader.

> Evidence note: provider rankings below come from a handful of secondary web sources (blog benchmarks and comparison pages), fetched in October 2026. They are directionally useful, **not authoritative**; prices, models and licences change monthly. The bake-off in §5 exists precisely so we decide on our own ears and a real quote, not on a blog.

## 1. What "sounds real" actually depends on (more than the vendor)

1. **Expressive control per line.** Football commentary swings from a murmur to a roar within seconds. The engine must accept an *intensity/emotion* instruction per utterance (tags, style prompts or SSML-like controls), not just a voice id.
2. **Text written for speech.** Most "AI sound" is the script, not the voice: perfect grammar, uniform sentence length, no half-sentences. The (future) Narrator prompt must produce broken, rhythmic, reactive speech: fragments, interruptions, repeated names, rising "and it's…", trailing off. The voice layer should receive **punctuation-as-prosody** (ellipses, dashes, caps for shouts) and an `energy` value, not only words.
3. **Two or more people talking to each other.** Real commentary has overlaps, reactions ("oh!"), laughter, handovers. The synthesizer API must support **short interjections, overlap offsets and non-verbal sounds** and the mixer must be able to overlap clips.
4. **Pronunciation of invented names.** Every name in this world is invented. We already generate `Pronunciation{respelling, ipa, stress}`; the TTS layer must apply it (SSML phoneme/lexicon, or respelled text fallback) and be regression-tested (§5 test list).
5. **Broadcast mastering and bed.** Raw TTS sounds like a voice-over booth. Commentary is *in a stadium*: crowd bed that swells on events (driven by `ctx.significance`), a commentator-microphone EQ and compression chain, subtle room, ducking of the crowd under speech, the voice getting hoarse/louder with energy. A decent voice with good mastering beats a great voice dry.
6. **Consistency.** The same character must sound identical across weeks (stable voice id/seed/settings), with only *delivery* changing.
7. **Latency and cadence.** Live feel means sentence-level streaming with a budget (e.g. first audio ≤ 1.2 s after a key event for "live" reactions; replays can be pre-rendered). Because matches are pre-simulated (10 §7) we can **pre-render most commentary** ahead of airtime and reserve low-latency paths for nothing — a major quality and reliability win.
8. **Variety.** Repetition is the second tell. Catchphrases are rate-limited (data in `MediaPersonality.catchphrases`), and the audio layer caches by *(text, voice, settings)* only for truly fixed lines.

## 2. Design now: `VoiceProfile v2` and `VoiceSynthesizer v2`

```python
class VoiceProfile(BaseModel):               # provider-agnostic casting sheet + bindings
    schema_version: int
    casting: VoiceCasting                    # who the character sounds like (ours, stable)
    bindings: dict[ProviderId, VoiceBinding] # which vendor voice currently plays them
    lexicon: list[LexiconEntry]              # name pronunciations (from Person.pronunciation) + overrides
    delivery: DeliveryProfile                # how emotion maps to controls

class VoiceCasting(BaseModel):
    gender: ...; age_range: ...; accent: str          # "northern Kesh, clipped"
    timbre: list[str]                                  # "gravelly", "warm", "bright"
    register: Literal["low","mid","high"]; base_pace_wpm: int; pace_variance: Unit
    energy_range: tuple[Unit, Unit]                    # quietest/loudest the character gets
    delivery_notes: str                                # free text used as a style prompt where supported

class VoiceBinding(BaseModel):
    voice_id: str; model: str; settings: dict[str, JsonValue]   # provider-specific, opaque to the core
    created_on: GameDate; sample_uri: str | None               # reference audio for auditions/regression

class DeliveryProfile(BaseModel):
    emotion_map: dict[Emotion, ProviderHints]     # e.g. "ecstatic" → tag/style/params per provider
    interjections: list[Interjection]             # "oh!", "wow", laugh, sigh — short clips/phrases
    shout_threshold: Unit; whisper_threshold: Unit
```

```python
class VoiceSynthesizer(Protocol):                # async; every real implementation is I/O- or GPU-bound
    capabilities: SynthCapabilities              # ssml, emotion_tags, style_prompt, streaming, word_timestamps, max_chars...
    async def synthesize(self, request: SpeechRequest) -> AudioClip: ...
    def stream(self, request: SpeechRequest) -> AsyncIterator[AudioChunk]: ...   # optional per capabilities

class SpeechRequest(BaseModel):
    line_id: str; text: str; voice: VoiceProfile
    emotion: Emotion; energy: Unit               # from CommentaryLine
    prosody_hints: ProsodyHints                  # emphasis words, pauses, shout spans
    overlaps_with: str | None; interjection: bool
class AudioClip(BaseModel):
    uri: str; format; sample_rate: int; duration_ms: int; word_timings: list[WordTiming] | None; line_id: str
```

Adapters per provider live behind this Protocol (Strategy, 11 §3); a **contract test suite** (10 §1.6) runs against every adapter (including a fake that returns silence), so a provider swap cannot silently break the pipeline. `SynthCapabilities` lets the pipeline degrade gracefully (no emotion tags → use punctuation/casing; no streaming → pre-render).

**Nothing in the sim/league/event layers depends on any of this** — voice is a leaf layer downstream of `CommentaryLine`.

## 3. Provider landscape (as of Oct 2026, from secondary sources — verify)

| Option | Why consider | Watch-outs |
|--------|-------------|-----------|
| **ElevenLabs** | Repeatedly ranks at/near the top for naturalness, prosody and context awareness in third-party blind comparisons; strong expressive control and large voice library; voice design/cloning | Cost at 24/7 volume; terms around cloned voices; vendor lock-in risk → mitigated by the binding layer |
| **OpenAI TTS (gpt-4o-mini-tts class)** | Steerable by natural-language "style instructions" (good for per-line energy); inexpensive per minute | Third-party comparisons rank prosody/context awareness below the top specialists; limited stock voices |
| **Google Gemini TTS / Cloud TTS (Chirp class)** | Low per-token price; multi-speaker generation (useful for two-commentator exchanges in one pass); style prompts | Multi-speaker consistency over long runs unproven for us; quotas |
| **Azure / AWS neural & HD voices** | Mature SSML (phoneme, prosody), predictable enterprise SLAs, pricing | Typically less expressive than the top specialists; "broadcast-announcer" energy needs testing |
| **Specialists (Cartesia, Hume, PlayHT, Rime, Inworld, LMNT …)** | Low latency (Cartesia), emotion-aware models (Hume), strong "human fooling" scores in some benchmarks (PlayHT) | Smaller vendors: roadmap/pricing/continuity risk |
| **Self-hosted open models (Orpheus, Sesame CSM, Chatterbox, Kokoro, Higgs Audio, XTTS/F5 families)** | No per-minute fees (fixed GPU cost), full control, emotion tags in some (Orpheus), permissive licences on several; ideal for batch **pre-rendering** | Quality and consistency vary by model and voice; GPU ops burden; per-model licence/voice-rights must be checked; long-session voice drift |

A realistic end state is **hybrid**: a top expressive vendor for the main play-by-play and colour voices (the ones carrying emotion), a cheaper/self-hosted voice for pitch-side/studio segments and bulk filler, selected per character through `bindings`. That is exactly what the profile design allows.

## 4. Cost and capacity sizing (to fill in with real quotes)

Assume commentary speech ≈ 40–60% of air time → roughly 10–14 h of synthesized speech per day ≈ 300–420 h per month. Per-minute vendor pricing therefore differs by **orders of magnitude** between premium voice APIs, mid-tier APIs and a self-hosted GPU. Because matches are pre-simulated, commentary can be **pre-rendered in batch** (cheaper tiers, no latency pressure, retries, human QA sampling). The bake-off records: price per audio minute, real-time factor, concurrency limits, and monthly cost at 24/7 volume.

## 5. Decision process for the TTS phase (a bake-off we can run on day one of that phase)

1. **Script set (≈ 12 lines per voice type):** a calm analysis paragraph, a rising build-up, a goal shout, a near-miss groan, a red-card disbelief line, a halftime wrap, a two-commentator exchange with interruption, a joke, a long name-heavy lineup read, and **10 invented names** from our world (pronunciation stress test).
2. **Candidates:** 2–3 top commercial + 2 open-source models, each cast to the same 4 character briefs from our `VoiceCasting`.
3. **Scoring:** blind listening panel (you + a few others) rating *naturalness, energy appropriateness, name pronunciation, consistency across 3 re-renders, "does it sound like a broadcast?"* on 1–5; automatic metrics (latency, real-time factor, cost per minute, determinism of voice identity).
4. **Mastering test:** run the same clips through the broadcast chain (crowd bed, EQ/compression) — the chain often narrows the gap between vendors.
5. **Decide per character**, record the decision as an ADR (`docs/adr/`), and write the adapter + contract tests.

**What I'd bet on before testing (hypothesis, not a decision):** premium vendor voices for the two lead commentators, with a self-hosted/cheaper model evaluated for the supporting cast and a pre-render pipeline; strongest levers for realism are script style, interjections/overlaps, and mastering.

## 6. Other considerations to track (not decisions)

- **Voice rights & licensing:** only use stock/designed voices or voices we have explicit rights to; never clone a real person. Keep provenance per `VoiceBinding`.
- **Platform policy:** streaming platforms have rules about synthetic/AI-generated audio disclosure and about repetitive or mass-produced content on 24/7 channels. Check the current policy of the target platform before launch (the broadcast layer should make disclosure and variety easy: rotating segments, rich variation, original commentary).
- **Accessibility:** captions/subtitles from `CommentaryLine.text` are free and useful.
- **Safety of the stream:** voice layer failures degrade to captions + crowd bed (10 §7 item 8); never block the event feed.

## 7. What this means for Phase 2 (this task)

- `VoiceProfile v2` and `VoiceSynthesizer v2` models/Protocols + stubs (`NullVoice` returning silence of the estimated duration) and contract tests — in M1 (models) and M13 (Protocols, stubs, contract tests) scope.
- The seed generator emits `casting` for each commentator consistent with persona/gender/age (e.g. the "Old Hand" has a low register, slow pace, narrow energy range; the "Firecracker" a high register, fast pace, wide range) with empty `bindings`.
- Lexicon entries are generated from `Pronunciation` for every name that appears in lineups.
- No provider is chosen or integrated in this task.
