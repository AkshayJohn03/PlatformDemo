# Hyperframes Composition Brief: PlatformDemo — whiteboard lecture

## Objective
Create a long-form whiteboard explainer lecture video (NOT a launch video)
for PlatformDemo — the offline end-to-end integration proof for the AI
portfolio. Narration on. Tutor tone per TUTOR_BRIEF.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: voice-set, ~6–7 minutes (do NOT constrain to 15–25 s; the
  TUTOR_BRIEF overrides brag's default duration for this series)

## Source Material
- Project root: `D:\aria\Projects\PlatformDemo`
- Primary files read: `demo/pipeline_demo.py`, `tests/test_e2e.py`,
  `README.md`, `output/e2e_summary.json`, `output/rca_report.md`,
  `docker-compose.yml`
- Product name: PlatformDemo
- Tagline / strongest claim: "the picture on the box, finally assembled —
  four standalone systems, one end-to-end run, fully offline"
- Key UI or visual moment to recreate: the gateway toll road (8 pipeline
  stages) with the meter receipt; the exit-0/exit-1 gate board; the RCA
  report card
- Copy that must appear verbatim:
  - `python demo/pipeline_demo.py`
  - `rate limit → flags → cache lookup → autopilot → route → execute → meter → cache store`
  - `6,578 tokens · $0.001567 · tenant hvac-copilot`
  - `44 spans · 4 traces · spans.jsonl`
  - `F-RET-001 — empty retrieval set`
  - `exit 0` / `exit 1` · `no_change` / `regressed` · `−19.2%`
  - `11 tests · offline · CI`
  - `spans.jsonl · rca_report.md · e2e_summary.json`
  - `GLOSSARY.md — 54 terms`

## Creative Direction
- Tone preset: `polished`
- Creative direction: patient senior engineer at a whiteboard; calm, precise,
  friendly; no hype adjectives; every keyword defined on screen at first use
  (right-hand definition card rail, one plain sentence).
- Angle: eight great tools that never talked are just a collection — follow
  ONE request through the whole platform, then show why an offline e2e test
  makes the architecture claim credible.
- Hook: "You've built eight AI systems. Each one passes its own tests. So —
  do they work together?"
- Outro / punchline: "The collection became a platform — proven, offline."
- Avoid: hype language, launch energy, fast-cut montage, abstract filler,
  waveform/equalizer visuals.

## Visual Identity
- Background: `#f6f4ec` warm whiteboard (subtle vignette)
- Ink text: `#1d2733`
- Marker blue: `#1e5aa8` · Marker green (pass): `#1a7f37` · Marker red
  (fail): `#b42318` · Marker amber (highlight): `#8a5a00` on `#ffe9b8`
- Display font: "Ink Free" — local `assets/fonts/Inkfree.ttf` via @font-face
- Body font: system-ui, sans-serif
- Visual references: hand-drawn boxes with 2–3 px ink borders, slight marker
  underlines, dashed connector arrows; definition cards on the right rail
  with colored left border per role (blue = concept, green = proof, red =
  failure, amber = highlight)

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract.
Scene summary (durations flex to measured voiceover WAVs; scene k starts at
the cumulative end of the previous scene):

1. eight tools, one question — hook; 8 toolboxes pop in
2. the claim — jigsaw assembles; command types on; vertical slice + e2e test
   defined
3. the cast — 4 system boxes; adapter defined
4. one request — E04 question → retrieval → cited answer; LLM seam wired to
   gateway; "a fourth question is planted"
5. the gateway toll road — 8 stage chips one by one; meter receipt counts up
6. the flight recorder — span fields exploded; 44 spans / 4 traces; span sink
   defined
7. the planted failure — X300 ZERO HITS; F-RET-001 stamp; retrieve WARN; RCA
   report card
8. the exam board — golden dataset; v1-vs-v1 exit 0; degraded v2 −19.2% exit
   1
9. why this is credible — 3 artifacts; CI loop; offline determinism + mock
   transport defined
10. recap — 6 numbered rows; closing line; GLOSSARY.md pointer

## Audio
- Audio role: warm quiet bed under a lecture voice; sparse professional
  accents
- Audio arc: bed starts under the hook, stays constant and low, swells
  slightly at the exit-code payoff, fades under the recap close
- Music: `assets/music/happy-beats-business-moves-vol-12-by-ende-dot-app.mp3`
  (117.384 s), looped back-to-back as sequential `<audio>` elements at volume
  0.13 (track 10)
- Music treatment: constant 0.13; no automation needed; final loop trimmed to
  composition end
- Music cue guidance: natural timing chosen for readability — lecture pacing
  puts reading floors first; no strong-cue locks (deliberate, documented)
- Audio-reactive treatment: none — intentional restraint (lecture bed at
  −18 dB under speech; reactive motion would compete with definition cards)
- Audio-coupled moments:
  - scene 1 — toolboxes pop in with soft drop cues
  - scene 2 — command type-on with subtle ticks
  - scene 5 — stage chips reveal in VO order; receipt counter ticks
  - scene 7 — F-RET-001 stamp with `interface/error_005.ogg` (low volume)
  - scene 8 — `interface/bong_001.ogg` (soft) on exit-0 chip;
    `impact/impactSoft_medium_000.ogg` on exit-1 chip
- SFX selection guidance: files already staged under
  `assets/sfx/{interface,impact}/`; use at 0.4–0.6 volume; align to the start
  of the visual event
- Voiceover: 10 WAVs at `assets/voiceover/voice_01.wav` … `voice_10.wav`,
  generated via `npx hyperframes tts --voice af_heart`; one per scene; scene
  clip `data-start`/`data-duration` MUST be derived from the measured WAV
  durations (scene start = previous scene start + duration; VO starts ~0.35 s
  into its scene; scene ends ~0.5 s after VO ends)

## Hyperframes Instructions
Load `hyperframes-core`, `hyperframes-animation`, `hyperframes-creative`,
`hyperframes-keyframes`, `hyperframes-cli`. Standalone composition (no
`<template>` wrapper). Requirements:
- One root `data-composition-id="platform-lecture"`, 1920x1080, root
  `data-duration` = computed total (static, from WAV math)
- One paused GSAP timeline registered at `window.__timelines["platform-lecture"]`
- One `.clip` per scene; never tween the clip itself — animate inner wrappers
- All text readable; no `<br>` in body copy; no CSS-transform + GSAP-transform
  conflicts (use fromTo); every `<audio>` needs an id; music on track 10, VO
  on tracks 3–9/11–13, SFX 14+
- Definition cards land when the term is first spoken (reading floor: ~0.3 s
  per word, min 1.2 s hold)
- Motion: quiet fades/slides (0.4–0.6 s), scale-x underline draws, count-up
  numbers via a tweened object with onUpdate writing textContent
- Run `npx hyperframes check` before render — fix every error including WCAG
  contrast; then `npx hyperframes render --quality delivery`
