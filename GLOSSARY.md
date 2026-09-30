# PlatformDemo — Glossary

Every term this repo uses, defined in one to three plain sentences, grouped by
theme. Each entry ends with **Why it matters here** — the specific reason the
term exists in *this* proof. Read it before or after `demo/pipeline_demo.py`;
the demo is the artifact, this is the vocabulary.

---

## The systems (the cast)

**PlatformDemo.** A small repo whose only job is to prove that four standalone
portfolio systems compose into one platform. It wires them together, runs one
real request through all of them, and writes down what happened.
*Why it matters here: eight great tools that never talked to each other are
just a collection — this repo is the picture on the box, finally assembled.*

**HVAC-Copilot.** A question-answering service for HVAC technicians: it
retrieves the right chunks from a repair-manual corpus and composes a cited
answer. *Why it matters here: it is the concrete app whose every "think" step
becomes the traffic flowing through the platform.*

**AegisGate.** A gateway that sits between an application and its AI models:
every LLM call passes through rate limiting, feature flags, caching, budget
autopilot, routing, circuit breaking, and metering. *Why it matters here: in
this demo it is embedded as a library, and every one of HVAC-Copilot's LLM
calls is brokered by it — nothing is bypassed.*

**ForensiQ.** A forensics system that reads trace files, classifies failures,
scores stage health, ranks blame, and renders a root-cause report. *Why it
matters here: it consumes the span stream the gateway produced in this very
run, and catches the one real, planted failure.*

**VerdictAI.** An evaluation system that scores model snapshots against a
golden dataset and runs a release gate. *Why it matters here: its gate is the
last stage of the demo — a healthy snapshot passes, a degraded snapshot fails,
and the exit codes are the platform's "do not ship" signal.*

**EchoMockClient.** AegisGate's offline upstream model client: instead of
calling a real provider, it echoes the prompt back inside an
`[echo:<model>] ...` envelope. *Why it matters here: it lets the full
pipeline run with no network and no API keys, while every control stage
around it executes for real.*

**MockModelAdapter.** VerdictAI's programmable stand-in model: it returns
reference answers at a configurable `quality` level, and `degrade()` drops a
deterministic, hash-drawn fraction of the words. *Why it matters here: it
creates a regression (about −19%) that is reproducible run to run — no
randomness, no network.*

**HeuristicJudge.** VerdictAI's labeled, rule-based judge: it scores an answer
against its reference without calling an AI model. *Why it matters here: it
keeps the golden eval offline and deterministic, so the gate verdict is a
property of the wiring, not of a model mood.*

**Tenant.** The identity a caller uses with the gateway; all rate limits,
budgets, and billing attach to it. *Why it matters here: the demo runs as
tenant `hvac-copilot`, so the meter's receipt is attributable to exactly one
caller — the same way production would bill.*

**Redis.** A small in-memory data store that backs AegisGate's rate-limit and
cache stores when the gateway runs as multiple replicas. *Why it matters
here: it appears in the docker-compose topology so the multi-instance path is
one environment variable away, even though the offline proof uses in-memory
stores.*

**docker-compose topology.** A declarative file describing the same platform
as separate containers talking over HTTP: HVAC on :8300, the gateway on :8080,
ForensiQ reading a shared volume. *Why it matters here: it is the production
shape of the composition the offline demo proves as libraries — the wiring
claim exists at both levels.*

---

## The flow (one request through the platform)

**Vertical slice.** A slice of software that touches every layer of a system
for one real use case, instead of testing each layer in isolation. *Why it
matters here: the whole demo is one vertical slice — a technician's question
travels from retrieval through the gateway to a cited answer, a forensics
report, and a release gate.*

**GatewayRoutedLLMClient (the adapter).** This repo's central glue class: it
implements HVAC-Copilot's `LLMClient` interface, but each `complete()` builds
an AegisGate `ChatRequest` and awaits `pipeline.handle()`. *Why it matters
here: HVAC-Copilot does not know it is talking to a gateway — the adapter
swaps the provider without changing a line of the app. That is what
"composes" means.*

**LLMClient seam (protocol).** The narrow interface (a `complete()` method
over messages) that HVAC-Copilot defines for anything that can generate text.
*Why it matters here: the demo proves the seam is real — you can replace a
provider with a gateway-routed client at that seam and the app keeps working,
citations and all.*

**Gateway pipeline stages.** The fixed sequence every LLM call traverses:
`rate_limit` (is this tenant over its request budget?) → `flags` (is this
feature/model switched on for this caller?) → `cache_lookup` (have we answered
this exact prompt before?) → `autopilot` (is the tenant's budget healthy, or
should we downgrade?) → `route` (which model serves this call?) → `execute`
(breaker, retry, fallback around the actual call) → `meter` (count tokens and
cost) → `cache_store` (remember the answer). *Why it matters here: the tests
assert every one of these stages ran at least once per query — the pipeline is
executed, not simulated.*

**Circuit breaker.** A guard that stops calling a provider that keeps failing,
giving it time to recover instead of hammering a dead service. *Why it matters
here: it is part of the `execute` stage on every call, so the "resilience is
built in" claim holds even in a four-query demo.*

**Retry / fallback.** Trying a failed call again (retry), or serving the
request with a different model if the first choice is unavailable (fallback).
*Why it matters here: they run inside the gateway's execute stage, so an
answer reaching the technician has already survived — or never needed — these
rescues, invisibly.*

**Metering (tokens billed).** The gateway's cost meter counts prompt tokens,
completion tokens, and dollars per tenant per model per day. *Why it matters
here: the run bills 6,578 tokens / $0.001567 to tenant `hvac-copilot` — a real
receipt from real usage accounting, not a hardcoded number.*

**Trace.** The complete record of one request's journey: an ID plus every
timed step that happened while serving it. *Why it matters here: the demo
produces four traces — one per HVAC query — and trace id is the join key that
lets gateway spans and HVAC's own evidence share one story.*

**Span.** One timed step inside a trace: a name, a stage, a duration, a status,
and attributes (the measurements). *Why it matters here: 44 spans are written
in this run; they are the raw material ForensiQ reasons over.*

**Span schema.** The exact field contract a span must satisfy:
`span_id`, `parent_id`, `name`, `stage`, `duration_ms`, `status`, `attrs`.
*Why it matters here: a test asserts every emitted span matches it — that is
what makes the gateway's output "ForensiQ-ingestable without translation."*

**Span sink.** The gateway's pluggable hook: anywhere spans should go — a
collector, a file, a queue — is injected as a callable at construction time.
*Why it matters here: `SpanCollector` is exactly such a sink; the demo proves
the hook exists and works without patching the gateway.*

**SpanCollector.** The demo's span sink implementation: it collects every span
dict and groups them by `parent_id` (the gateway trace id) into one JSONL
trace record per query. *Why it matters here: it turns a live stream of events
into the durable `spans.jsonl` file ForensiQ later reads.*

**RetrievalSpanProxy.** A thin wrapper around HVAC-Copilot's real retriever
that records measured retrieval evidence — hit count and the dense cosine
scores of the composer's context window — for every search. *Why it matters
here: it guarantees the numbers in the forensics report are measured values
from the actual retrieval, never synthetic ones.*

**Bridge spans.** The two extra spans emitted per query (`hvac_retrieve` with
stage `retrieve`, `hvac_compose` with stage `generate`) that map HVAC's domain
steps onto ForensiQ's canonical stage vocabulary under the gateway's trace id.
*Why it matters here: they join the operational view (the gateway's spans) and
the domain view (what the app actually did) into one trace, so forensics can
reason over both.*

**EchoMock envelope tag.** The `[echo:<model>] ` prefix the mock prepends to
its output; it is transport metadata, not model content. *Why it matters
here: the compose span strips it before recording, a small honesty detail that
keeps the recorded answer clean.*

**JSONL.** JSON Lines: one JSON object per line, a format you can stream and
append to. *Why it matters here: `spans.jsonl` is written this way so both
humans and ForensiQ's loader can consume it line by line.*

**ForensiQ ingestion.** ForensiQ's first step: a loader (`JSONLTraceLoader`)
reads the trace file and validates it into internal trace objects — counting
any records that fail validation as warnings. *Why it matters here: the run
ingests 4 traces with 0 warnings, proving the span contract between two
independent repos actually holds.*

**Failure classification.** ForensiQ's rules engine inspects each trace and,
when something is wrong, names it with a taxonomy id and a confidence. *Why it
matters here: it correctly finds exactly one failure in the cohort — the one
the demo planted on purpose.*

**Failure taxonomy (F-RET-001).** ForensiQ's named catalogue of failure types;
`F-RET-001` means "empty retrieval set — search returned zero hits for a
legitimate query." *Why it matters here: the incident probe asks about a unit
(X300) that is not in the corpus, so retrieval genuinely returns nothing, and
the classifier must catch and name that real failure.*

**Incident probe.** The deliberately failing query planted in the question
list, alongside three healthy questions. *Why it matters here: a clean cohort
would prove nothing about forensics — one honest incident is what turns the
RCA report into a demonstration rather than a formality.*

**Stage health.** Per-stage scorecards ForensiQ computes over the cohort:
error rate, hit rate, groundedness, latency percentiles. *Why it matters here:
the report marks `retrieve` as WARN (hit rate 0.75) and `generate` OK — the
system pinpoints where the trouble is, not just that it exists.*

**Blame ranking.** ForensiQ's statistical pass that weights stages by how
abnormal their behavior is during failures. *Why it matters here: the report
honestly shows the blame landing on `generate` (the algorithm's real output)
even though the classifier pinned the failure to `retrieve` — this repo does
not massage results it finds inconvenient.*

**Drift detection.** A statistical check for whether the failure mix has
shifted more than luck would allow, compared to a baseline window. *Why it
matters here: it correctly stays quiet (0 alerts — one day of data is below
its 3-day baseline minimum), showing the detector does not cry wolf.*

**RCA report.** Root-Cause Analysis: ForensiQ's markdown deliverable with an
executive summary, failure mix, blame graph, stage health, drift, and a mapped
fix playbook. *Why it matters here: `output/rca_report.md` is one of the three
artifacts — the platform's answer to "why did this request go wrong?"*

---

## The proof (why the claim is credible)

**Integration test.** A test that verifies two or more real components work
together through their actual interfaces — not a mock of either side. *Why it
matters here: the suite's 11 tests assert the real HVAC, gateway, forensics,
and eval code composing through their real seams.*

**End-to-end test (e2e).** An integration test that covers the whole path a
real request would take, from entry point to final artifacts. *Why it matters
here: `tests/test_e2e.py` runs the identical flow as the demo script and
asserts every stage executed and every contract held.*

**Offline determinism.** The property that the whole run needs no network, no
API keys, no services, and produces the same verdict every time. *Why it
matters here: it is what lets CI in GitHub Actions rerun the proof on every
push — a flaky, network-dependent demo would prove nothing.*

**Mock transport.** Using a stand-in at the transport boundary (the model
provider, the network) while everything above that boundary runs for real.
*Why it matters here: EchoMock and the hashed TF-IDF embedder are the mocks;
rate limiting, caching, routing, metering, classification, and the gate are
not — the demo is honest about which is which.*

**Golden dataset.** A fixed set of questions with reference answers, versioned
and frozen, used to score model snapshots. *Why it matters here: the demo
builds `platformdemo-golden-1` — 8 items quoted from the HVAC corpus — so both
gate runs grade the same exam.*

**Golden runner.** The component that executes a model snapshot over the
golden dataset and writes a scored snapshot record. *Why it matters here:
VerdictAI's `GoldenRunner` runs twice in the demo — once for v1, once for v2 —
producing comparable snapshots.*

**Baseline vs candidate.** The two snapshots a regression gate compares: the
known-good baseline (v1) and the new candidate (v2). *Why it matters here:
v1-vs-v1 establishes "a healthy model passes its own bar" (exit 0);
v1-vs-v2 asks "did the candidate get worse?" (exit 1).*

**Regression verdict.** The gate's decision: `no_change`, `regressed`, or
similar, computed from the score delta between baseline and candidate. *Why it
matters here: v1-vs-v1 yields `no_change`, v1-vs-v2 yields `regressed` with a
−19.2% drop — both verdicts are asserted by tests.*

**Gate threshold and effect guard.** The two conditions the VerdictAI gate
applies: the paired bootstrap confidence lower bound of the score delta must
exceed `threshold` (0.02), and the effect size (Cliff's delta) must exceed
`min_effect` (0.1). *Why it matters here: requiring both a statistically
significant drop and a meaningfully large one is the documented noise-alarm
protection — the gate cannot be tripped by luck.*

**Exit code semantics.** The convention that a program's exit code carries
meaning: 0 = success/pass, 1 = failure. CI systems act on it. *Why it matters
here: the demo's headline — gate exit 0 for the healthy snapshot, exit 1 for
the degraded one — is the mechanism that would block a bad release in a real
pipeline.*

**Snapshot store.** VerdictAI's append-only record of scored snapshots
(`verdictai_snapshots.jsonl`), so runs can be compared later. *Why it matters
here: it makes the eval auditable — the receipts for both gate verdicts are on
disk.*

**Calibration.** Documented adjustment of thresholds to the actual backend, so
defaults built for trained models do not false-fire on dev-grade components.
*Why it matters here: two ForensiQ thresholds are re-tuned for the hashed
TF-IDF embedder (retrieve score 0.10, repetition 12) and commented in the
demo — tuning is shown, not hidden.*

**Hashed TF-IDF embedder.** The dev-grade text vectorizer the demo uses
instead of a trained neural encoder: cheap, deterministic, offline. *Why it
matters here: it keeps the retrieval branch of the proof network-free while
still producing real cosine scores the proxy records.*

**Hybrid retrieval.** HVAC-Copilot's search combining keyword matching with
semantic vector similarity. *Why it matters here: it is the real machinery
behind every `hvac_retrieve` span — and its empty result on the X300 probe is
the planted failure ForensiQ must catch.*

**Citations.** The pointers from a composed answer back to the exact corpus
chunks it drew from. *Why it matters here: a test asserts every healthy answer
carries at least one citation, and the incident probe carries zero — evidence
that "nothing retrieved" has a visible, checkable consequence.*

**Grounded safety refusal (escalation).** HVAC-Copilot's guardrail: when no
safety-tagged source supports a procedural question, it refuses and escalates
to a certified technician instead of answering. *Why it matters here: the demo
questions are deliberately non-procedural so every one of them reaches the LLM
— i.e., through the gateway — instead of being refused.*

**Machine-checkable proof (e2e_summary.json).** The JSON summary recording
every stage's ok/ms/detail after a run. *Why it matters here: humans read the
RCA report; the test suite and CI read this file — the same proof in two
languages.*

**Session-scoped pytest fixture.** A pytest fixture that runs once per test
session and shares its result across tests. *Why it matters here: the 11 tests
all assert against one shared e2e run — the expensive proof executes once and
is then interrogated from every angle.*

**CI (continuous integration) workflow.** The GitHub Actions pipeline that
checks out the four sibling repos, installs them editable, lints, and runs the
offline suite plus the demo on every push. *Why it matters here: it is the
standing guarantee that "the four systems compose" is re-proven, not just
claimed once.*
