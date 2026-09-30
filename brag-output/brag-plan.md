# Brag Plan: PlatformDemo — whiteboard lecture

## What is this app?

PlatformDemo is the vertical integration proof for an eight-repo AI portfolio:
one offline command takes a real technician question through HVAC-Copilot,
AegisGate, ForensiQ and VerdictAI and writes the evidence to disk — proving
that four standalone systems compose into one platform.

## The angle

A patient senior-engineer whiteboard lecture (NOT a launch video). The hook is
the uncomfortable question every portfolio owner must answer: eight great
tools that never talked to each other are just a collection — so, do they work
together? The video follows ONE request end to end (HVAC question → gateway
metering → spans → ForensiQ catching the planted retrieval failure →
VerdictAI's gate exit 0 then exit 1), defines every keyword on screen the
moment it first appears, and closes on the measured numbers and a 30-second
recap the viewer could repeat to a colleague.

## Hook (first 3 seconds)

"You've built eight AI systems. Each one passes its own tests. So — do they
work together?" — over a whiteboard sketch of eight disconnected toolboxes.

## Key moments (the middle)

- The gateway toll road: one sketch, eight labeled stages
  (rate limit → flags → cache lookup → autopilot → route → execute → meter →
  cache store) with the real receipt: 6,578 tokens / $0.001567 billed to
  tenant `hvac-copilot`.
- The flight recorder: 4 queries become 4 traces / 44 spans in
  `spans.jsonl`, via the gateway's pluggable `span_sink`.
- The planted failure: the X300 probe retrieves zero hits; ForensiQ names it
  F-RET-001 "empty retrieval set", marks `retrieve` WARN, writes the RCA
  report.
- The exam board: golden dataset v1 vs v1 → exit 0; deterministically degraded
  v2 → −19.2% → verdict `regressed`, exit 1.

## Outro / punchline

The recap board: "The collection became a platform — proven, offline." Plus
the pointer to GLOSSARY.md (54 terms) and the success metric: "now explain it
to someone else."

## User flow worth showing

The demo's flow IS the video: `python demo/pipeline_demo.py` → stages table
PASS×7 → artifacts (`spans.jsonl`, `rca_report.md`, `e2e_summary.json`).
Recreated as whiteboard sketches per scene; the artifacts board (scene 9)
shows the three real artifact filenames and the summary's numbers.

## Voiceover script

See `voiceover-script.txt` (10 scene-delimited paragraphs). Voice: Kokoro
`af_heart`. Numbers written for TTS; exact figures appear on screen. ~965
words → ~6:30 at natural pace. Scene durations flex to the measured WAV
lengths.

## Tone

- Preset: `polished` (long holds, confidence through restraint — lecture
  pacing)
- Creative direction: TUTOR_BRIEF `--tone` — patient senior engineer at a
  whiteboard teaching ONE system to a smart junior who knows almost nothing
  about AI. No hype adjectives. Calm, precise, friendly.
- Interpretation: every scene is one concept with one sketch; definitions ride
  in a right-hand rail card the moment the term is first spoken; text holds
  long enough to read; motion is quiet (fade/slide, no bouncing).

## Format: landscape — 1920x1080
## Duration: ~390 seconds (voice-set; target 4–7 min)

## Visual identity (whiteboard, marker on board — distinct from the dark
chalkboard used by sibling episodes)

- Background: warm whiteboard `#f6f4ec` with a faint cool vignette
- Text (ink): `#1d2733`
- Accent blue (marker): `#1e5aa8`
- Accent green (pass): `#1a7f37`
- Accent red (fail/planted): `#b42318`
- Accent amber (highlight): `#8a5a00` on light chips `#ffe9b8`
- Display font: "Ink Free" (local TTF, handwriting feel)
- Body font: system-ui / sans-serif
- Strongest visual element: the hand-drawn gateway toll road with its meter
  receipt, and the exit-0/exit-1 gate board

Contrast: all text is dark ink on the light board or white cards (≥ 7:1);
marker colors chosen dark enough for AA on `#f6f4ec`; chips use near-black
text on light fills.

## Share copy (draft)

"Eight AI systems that never talked are just a collection. I wired four of
mine into one offline end-to-end proof — one request, metered by the gateway,
recorded as 44 spans, the planted failure caught by forensics, and the
degraded model failed by the release gate (exit 0, then exit 1). This is the
whiteboard lecture on how PlatformDemo proves 'it composes'."

## Audio direction

- Role: warm quiet bed under a lecture voice — sparse professional accents
- Music: `happy-beats-business-moves-vol-12-by-ende-dot-app.mp3` (steady and
  clean), looped back-to-back, volume 0.12–0.14 under narration
- Music treatment: constant low bed; final instance fades under the recap
  close
- Music cue guidance: natural timing chosen for readability (lecture pacing;
  sequential text holds to reading floors, not to a beat grid). No strong-cue
  locks — deliberate, documented choice.
- Audio-reactive treatment: none — intentional. A lecture bed sits at
  −18 dB under speech; reactive motion would draw the eye away from
  definition cards. Restraint rule: audio must never compete with narration.
- SFX posture: sparse — one drop cue per major sketch reveal, one soft error
  buzz when the planted failure lands, one soft bell for the exit-code board
- Audio-coupled moments: stage chips appearing one by one on the toll road;
  the F-RET-001 stamp; exit 0 / exit 1 chips

## Storyboard

### Scene 1 — eight tools, one question — ~33s
Whiteboard: eight small toolboxes in a loose grid, none connected. Title:
"eight great tools that never talked". Rail card defines **portfolio**. VO:
the uncomfortable question — each tool passes its own tests, but do they work
together?
Sequential/interaction: toolboxes pop in one by one (0.5s apart), stay.
Audio intent: neutral curiosity; quiet bed starts.
Audio-coupled idea: soft drop cue per toolbox.
Music: vol-12 at 0.13. Transition mood: clean fade → Scene 2.

### Scene 2 — the claim: the picture on the box — ~37s
Sketch: jigsaw pieces clicking into one picture; the one-command terminal
line `python demo/pipeline_demo.py`. Rail cards define **vertical slice** and
**end-to-end test**. VO: one command, offline, one real request through every
system.
Sequential/interaction: pieces slide together; terminal line types on.
Audio intent: confident, calm.
Audio-coupled idea: type-on with subtle ticks; pieces land with drop cues.
Transition mood: clean → Scene 3.

### Scene 3 — the cast of four — ~35s
Four labeled boxes in a row: HVAC-Copilot (the app), AegisGate (the gateway),
ForensiQ (the detective), VerdictAI (the exam board). Rail card defines
**adapter** — this repo's actual glue. VO: one line per system.
Sequential/interaction: boxes arrive left to right with captions.
Audio intent: steady introduction rhythm.
Transition mood: clean → Scene 4.

### Scene 4 — one request, end to end — ~43s
Sketch: technician question card "What does fault code E04 indicate on the
X200?" → retrieval (manual chunks) → cited answer. The LLM seam highlighted:
the copilot's client plug is wired to the gateway, not a provider. Rail cards
define **LLM seam** and **hybrid retrieval**. VO: three healthy questions go
through; a fourth is planted on purpose.
Sequential/interaction: question → chunks → answer arrow flow; seam glows.
Audio intent: narrative momentum.
Transition mood: clean → Scene 5.

### Scene 5 — the gateway toll road — ~48s
The centerpiece sketch: a horizontal toll road of eight stage chips
(rate limit → flags → cache lookup → autopilot → route → execute → meter →
cache store), one line each on screen as VO names them; then the meter
receipt card: 6,578 tokens · $0.001567 · tenant `hvac-copilot`. Rail cards
define **rate limit**, **circuit breaker**, **metering**, **tenant**.
Sequential/interaction: stage chips reveal one by one (reading-floor holds);
receipt counts up.
Audio intent: methodical, toll-booth rhythm.
Audio-coupled idea: chip per beat of the VO list; counter ticks on receipt.
Transition mood: clean → Scene 6.

### Scene 6 — the flight recorder — ~40s
Sketch: the toll road draining into a recorder box: `spans.jsonl`. One span
exploded into its fields (name, stage, duration_ms, status, attrs); four
traces grouped. Rail cards define **span**, **trace**, **span sink**. VO: 44
spans, 4 traces — the evidence file. "Now, who reads it?"
Sequential/interaction: span fields label one by one; counter to 44.
Audio intent: quieter, setup for the detective.
Transition mood: clean → Scene 7.

### Scene 7 — the planted failure — ~50s
Sketch: the X300 question card stamped ZERO HITS; ForensiQ box ingests the
file (4 traces, 0 warnings), then the taxonomy stamp: **F-RET-001 — empty
retrieval set**; stage health card marks `retrieve` WARN; RCA report card on
the right with its real section names. Rail cards define **failure
taxonomy**, **stage health**, **RCA report**. VO: the honest incident is what
makes forensics a proof, not a formality.
Sequential/interaction: ingest → classify → stamp lands (soft error buzz);
health card flips to WARN.
Audio intent: tension then release into the report.
Audio-coupled idea: stamp + error_005 at the same instant.
Transition mood: clean → Scene 8.

### Scene 8 — the exam board — ~50s
Sketch: golden dataset card (8 items, references quoted from the corpus);
baseline vs candidate snapshot cards; the gate box. Exam 1: v1 vs v1 →
verdict `no_change` → green chip **exit 0**. Exam 2: v2 degraded (every other
word dropped) → −19.2% → verdict `regressed` → red chip **exit 1**. Rail
cards define **golden dataset**, **regression gate**, **exit code**. VO: CI
acts on that number — a degraded model can never silently ship.
Sequential/interaction: two exam rows resolve one after the other; chips slam
in.
Audio intent: the payoff beat; bed swells slightly.
Audio-coupled idea: soft bell on exit 0, heavier on exit 1.
Transition mood: clean → Scene 9.

### Scene 9 — why this is credible — ~40s
Sketch: three artifact cards (`spans.jsonl`, `rca_report.md`,
`e2e_summary.json`) and the CI loop arrow (push → install siblings → 11
tests). Rail cards define **offline determinism** and **mock transport**. VO:
only the transport is mocked; everything above it is real; the claim reruns
on every push in ~200 ms.
Sequential/interaction: artifact cards arrive; loop arrow draws.
Audio intent: reasoned, settled.
Transition mood: clean → Scene 10.

### Scene 10 — the 30-second recap — ~46s
Six numbered recap rows (the request, the meter, the recorder, the catch, the
gate, the artifacts), then the closing line: "The collection became a
platform — proven, offline." and the pointer card: GLOSSARY.md — 54 terms —
"now explain it to someone else."
Sequential/interaction: rows land one by one; closing line fades up last.
Audio intent: warm close; music fades under the last line.
Audio-coupled idea: none — let the recap breathe.
Transition mood: soft fade to end.

**Music mood for this video:** steady/clean bed (polished restraint)
**Audio summary:** a quiet constant bed under ten narration scenes, sparse
drop cues on sketch reveals, one error buzz on the planted failure, one soft
bell on the exit-code board, fade under the closing line.
