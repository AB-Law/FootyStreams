"""Extension seams for future layers (narration, memory, voice, event sinks, manager policy).

May import: domain, events. Protocols, shared types and null stubs only; no provider code.
Design: docs/design/04-architecture.md section 5, docs/design/12-voice-and-tts.md.

Prototype (news desk): ``brief``, ``pack``, ``template_narrator``, ``protocols``. The LM Studio
adapter lives in ``cli`` (I/O). Full M13 seam expansion still ahead.
"""
