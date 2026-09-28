"""PlatformDemo — the vertical integration proof for the AI portfolio.

One offline process proves the "every system composes" claim end to end:

1. **HVAC-Copilot** answers real corpus questions, but its LLM calls do NOT go
   straight to a provider: ``GatewayRoutedLLMClient`` routes every
   ``complete()`` through the **AegisGate** ``GatewayPipeline`` (rate limit ->
   flags -> cache lookup -> autopilot budget -> routing -> breaker/retry ->
   metering -> cache store) with the offline ``EchoMockClient`` upstream.
2. The gateway's pluggable ``span_sink`` collects ForensiQ-compatible span
   dicts; the demo adds two bridge spans per query (retrieval evidence and the
   gateway-routed LLM call) so the operational stream joins ForensiQ's
   canonical stage vocabulary, then writes everything to ``spans.jsonl``.
3. **ForensiQ** ingests the JSONL, runs the deterministic failure classifier,
   the stage-health pass, blame ranking, clustering and drift detection, and
   renders the RCA markdown report.
4. **VerdictAI** runs the golden eval twice with its programmable
   ``MockModelAdapter`` (v1 healthy, v2 deterministically degraded) and the CI
   regression gate: v1-vs-v1 must PASS (exit 0), v1-vs-v2 must FAIL (exit 1).

No network, no API keys, no Docker required: ``python demo/pipeline_demo.py``
or ``python -m pytest -q`` runs the identical flow with assertions.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegisgate.config import AegisGateSettings
from aegisgate.gateway.app import build_pipeline
from aegisgate.llm.base import ChatRequest as GateChatRequest
from aegisgate.llm.base import Message as GateMessage
from aegisgate.pipeline import GatewayPipeline, PipelineResult
from forensiq.attribution.blame import BlameRanker
from forensiq.attribution.health import StageHealth
from forensiq.ingest.loaders import JSONLTraceLoader
from forensiq.patterns.cluster import FailureClusterer
from forensiq.patterns.drift import DriftDetector
from forensiq.report.rca import RCAReportGenerator, ReportInputs
from forensiq.taxonomy.classifier import FailureClassifier
from hvac_copilot.config import REPO_ROOT as HVAC_REPO_ROOT
from hvac_copilot.config import Settings as HVACSettings
from hvac_copilot.qa.compose import Answer
from hvac_copilot.service import HVACCopilot
from verdictai.datasets.schema import DatasetItem, EvalDataset
from verdictai.judges.rubric import HeuristicJudge
from verdictai.regression.gate import run_gate
from verdictai.regression.runner import GoldenRunner, MockModelAdapter, SnapshotStore

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "output"

TENANT_ID = "hvac-copilot"
GATEWAY_MODEL = "gpt-4o-mini"  # must exist in the AegisGate registry (models.yaml)

# Three benign corpus questions (spec lookups + one fault-code direct hit).
# Deliberately non-procedural so HVAC's grounded-refusal guardrail lets every
# question reach the LLM — i.e. through the gateway — instead of escalating.
HEALTHY_QUESTIONS: list[tuple[str, str]] = [
    ("What is the rated electrical supply for the AriaTherm X200 heat pump?", "X200"),
    ("What does fault code E04 indicate on the X200?", "X200"),
    ("What is the cooling capacity of the VeyraCool V9 chiller?", "V9"),
]
# The incident probe: a query for a unit that is NOT in the corpus. The
# metadata filter matches zero chunks, retrieval returns an empty result set,
# and ForensiQ must catch and attribute that real failure (F-RET-001) in the
# RCA report. One honest incident is what makes the forensics half of this
# demo a proof rather than a formality.
INCIDENT_PROBE: tuple[str, str] = (
    "What is the rated electrical supply for the AriaTherm X300 heat pump?",
    "X300",
)
QUESTIONS: list[tuple[str, str]] = HEALTHY_QUESTIONS + [INCIDENT_PROBE]

# ForensiQ's default retrieve-score threshold (0.5) assumes a trained encoder.
# The portfolio's dev-grade hashed TF-IDF embedder yields conservative cosine
# similarities (healthy spec lookups sit around 0.14-0.27 on this corpus), so
# the classifier and health card are calibrated to this backend's score scale
# instead of importing a threshold that would false-fire on every trace.
RETRIEVE_SCORE_THRESHOLD = 0.10
# Repetition-loop threshold: ForensiQ's default (5) assumes free-form prose,
# but grounded prompts repeat the unit breadcrumb once per context block (up
# to 8 blocks -> ~10 repeats of "AriaTherm X200 ..."). Degenerate decode loops
# repeat phrases far beyond that ceiling, so 12 keeps structured prompts quiet
# while real loops still trip the rule.
REPETITION_MIN_REPEAT = 12

GOLDEN_DATASET_VERSION = "platformdemo-golden-1"
# v2 = the same adapter with VerdictAI's deterministic degrade(): each word of
# the reference is hash-drawn, so quality=0.5 keeps ~50% of the words and the
# heuristic judge scores it ~19% lower than v1 — a visible, reproducible
# regression with no network and no randomness.
V2_DEGRADE_QUALITY = 0.5
GATE_THRESHOLD = 0.02  # CI gate: CI-low of mean delta must exceed this ...
GATE_MIN_EFFECT = 0.1  # ... AND paired Cliff's delta must exceed this.

SPAN_KEYS = {"span_id", "parent_id", "name", "stage", "duration_ms", "status", "attrs"}

# The exact stage sequence run_demo() executes; the summary table and the test
# suite both prove every one of them ran.
EXPECTED_STAGES = (
    "aegisgate_pipeline_built",
    "hvac_routed_through_gateway",
    "hvac_queries_via_gateway",
    "spans_jsonl_written",
    "forensiq_analysis_and_rca",
    "verdictai_golden_v1_and_gate_pass",
    "verdictai_golden_v2_and_gate_fail",
)


class LLMRoutingError(RuntimeError):
    """Raised when the gateway pipeline refuses an HVAC LLM call."""


# --------------------------------------------------------------------------- #
# Integration adapters (the glue this repo exists to prove)
# --------------------------------------------------------------------------- #
class SpanCollector:
    """The pluggable AegisGate ``span_sink`` — collects every span dict.

    Gateway spans arrive through the sink during pipeline execution; the demo
    adapters add their bridge spans through :meth:`add` with the same
    ``parent_id`` (the gateway trace id), so grouping by ``parent_id`` yields
    one coherent trace per HVAC query.
    """

    def __init__(self) -> None:
        self.spans: list[dict[str, Any]] = []
        self._first_seen: dict[str, float] = {}

    def add(self, span: dict[str, Any]) -> None:
        parent = str(span.get("parent_id") or "root")
        self._first_seen.setdefault(parent, time.time())
        self.spans.append(span)

    __call__ = add

    def trace_groups(self) -> list[tuple[str, float, list[dict[str, Any]]]]:
        groups: list[tuple[str, float, list[dict[str, Any]]]] = []
        for trace_id in dict.fromkeys(str(s.get("parent_id") or "root") for s in self.spans):
            spans = [s for s in self.spans if str(s.get("parent_id") or "root") == trace_id]
            groups.append((trace_id, self._first_seen[trace_id], spans))
        return groups


class RetrievalSpanProxy:
    """Wraps the HVAC retriever and records real retrieval evidence per search.

    Delegates everything else to the real ``HybridRetriever``; the recorded
    hit scores are the dense-branch cosine similarities the fusion actually
    used — no synthetic numbers.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self._pending: list[dict[str, Any]] = []

    def search(self, query: str, *args: Any, **kwargs: Any) -> Any:
        result = self._inner.search(query, *args, **kwargs)
        # hit_scores = the dense cosines of the composer's context window (the
        # AnswerComposer embeds at most 8 blocks in the prompt); hit_count is
        # everything the retriever returned. Both are measured, not derived.
        window = result.items[:8]
        self._pending.append(
            {
                "query": query,
                "top_k": int(kwargs.get("top_k") or 5),
                "hit_count": len(result.items),
                "hit_scores": [round(float(item.scores.get("dense", 0.0)), 4) for item in window],
                "duration_ms": float(result.trace.get("retrieve_ms", 0.0)),
                "mode": str(result.trace.get("mode", "hybrid")),
            }
        )
        return result

    def drain(self) -> list[dict[str, Any]]:
        pending, self._pending = self._pending, []
        return pending

    def __getattr__(self, name: str) -> Any:  # delegate the rest of the retriever API
        return getattr(self._inner, name)


class GatewayRoutedLLMClient:
    """HVAC ``LLMClient`` whose ``complete()`` executes the AegisGate pipeline.

    Satisfies ``hvac_copilot.clients.base.LLMClient`` (complete/stream over
    ``hvac_copilot.clients.base.Message``). Every call runs the full gateway
    pipeline — rate limit, flags, cache lookup, autopilot budget, routing,
    breaker/retry, metering — with the offline EchoMockClient upstream, and
    records what happened (trace id, served-by model, usage, cost) so the demo
    loop can emit the ForensiQ bridge spans afterwards.
    """

    provider = "aegisgate"

    def __init__(
        self,
        pipeline: GatewayPipeline,
        *,
        tenant: str = TENANT_ID,
        model: str = GATEWAY_MODEL,
    ) -> None:
        self.pipeline = pipeline
        self.tenant = tenant
        self.model = model
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        messages: list[Any],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        request = GateChatRequest(
            model=self.model,
            messages=[GateMessage(role=m.role, content=m.content) for m in messages],
            temperature=0.1 if temperature is None else temperature,
            max_tokens=max_tokens,
        )
        result: PipelineResult = await self.pipeline.handle(request, self.tenant)
        if result.error is not None or result.response is None:
            error = result.error
            raise LLMRoutingError(
                f"gateway rejected the LLM call ({getattr(error, 'code', 'unknown')}): "
                f"{getattr(error, 'message', 'no response')}"
            )
        usage = result.response.usage
        self.calls.append(
            {
                "gateway_trace_id": result.trace_id,
                "served_by": result.served_by,
                "cache_tier": result.cache_tier,
                "prompt": messages[-1].content if messages else "",
                "output": result.response.content,
                "finish_reason": result.response.finish_reason,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "cost_usd": result.cost_usd,
            }
        )
        return result.response.content

    def stream(self, messages: list[Any], **kwargs: Any) -> Any:
        """Single-chunk stream over the gateway-routed completion."""

        async def _one_chunk() -> Any:
            text = await self.complete(messages, **kwargs)
            yield text

        return _one_chunk()


def emit_bridge_spans(
    router_client: GatewayRoutedLLMClient,
    retriever_proxy: RetrievalSpanProxy,
    collector: SpanCollector,
    answer: Answer,
    wall_ms: float,
) -> None:
    """Map one finished HVAC query onto ForensiQ's canonical stage vocabulary.

    Two measured, real-data bridge spans join the gateway's operational spans
    under the same trace id so ForensiQ can reason over both views:

    - ``hvac_retrieve`` (stage ``retrieve``): the dense-cosine evidence of the
      composer's context window, recorded by :class:`RetrievalSpanProxy`.
    - ``hvac_compose`` (stage ``generate``): the answer the pipeline returned,
      grounded in the prompt that went through the gateway, with the gateway's
      own usage/cost attached.

    The EchoMock envelope tag (``[echo:<model>] ``) is transport metadata the
    mock prepends, not model output, so the compose span records the body.
    """
    if not router_client.calls:
        return  # HVAC query cache short-circuited composition; nothing to map
    call = router_client.calls[-1]  # sequential demo: one gateway call per ask
    trace_id = call["gateway_trace_id"]
    for i, rec in enumerate(retriever_proxy.drain()):
        collector.add(
            {
                "span_id": f"{trace_id}-ret-{i}",
                "parent_id": trace_id,
                "name": "hvac_retrieve",
                "stage": "retrieve",
                "duration_ms": rec["duration_ms"],
                "status": "ok",
                "attrs": {
                    "query": rec["query"],
                    "top_k": rec["top_k"],
                    "hit_count": rec["hit_count"],
                    "hit_scores": rec["hit_scores"],
                    "mode": rec["mode"],
                },
            }
        )
    output = call["output"]
    if output.startswith("[") and "] " in output[:64]:
        output = output.split("] ", 1)[1]
    collector.add(
        {
            "span_id": f"{trace_id}-compose",
            "parent_id": trace_id,
            "name": "hvac_compose",
            "stage": "generate",
            "duration_ms": round(wall_ms, 3),
            "status": "ok",
            "tokens_in": call["prompt_tokens"],
            "tokens_out": call["completion_tokens"],
            "cost": call["cost_usd"],
            "attrs": {
                "model": call["served_by"],
                "gateway_trace_id": trace_id,
                "prompt_chars": len(call["prompt"]),
                "finish_reason": call["finish_reason"],
                "output": output,
                "context": call["prompt"],
                "cache_tier": call["cache_tier"] or "miss",
                "answer_citations": len(answer.citations),
            },
        }
    )


# --------------------------------------------------------------------------- #
# VerdictAI golden dataset (references quoted from the HVAC corpus)
# --------------------------------------------------------------------------- #
def build_golden_dataset() -> EvalDataset:
    references = {
        "x200-electrical": (
            "The AriaTherm X200 requires a 230 V single phase 50 Hz electrical supply "
            "with MCA 19.6 A and a maximum breaker of 25 A type C."
        ),
        "x200-refrigerant": (
            "The X200 uses R32 refrigerant, safety class A2L, with a factory charge of 1.35 kg."
        ),
        "x200-cop": "The X200 has a COP of 4.8 at A7/W35, EN 14825 average.",
        "x200-e04": (
            "E04 means the evaporator coil is iced and heating capacity is reduced. "
            "Likely causes are low airflow from a dirty filter or failed indoor fan, "
            "or low refrigerant charge."
        ),
        "x200-envelope": (
            "The heating operating envelope is outdoor -25 C to +35 C and water 20 C to 65 C."
        ),
        "v9-capacity": (
            "The VeyraCool V9 delivers 20 to 140 kW of cooling capacity on a twin circuit "
            "at W7/G25."
        ),
        "v9-electrical": (
            "The V9 requires a 400 V three phase 50 Hz supply rated 62 A with phase "
            "sequence L1-L2-L3 required."
        ),
        "v9-maintenance": (
            "The suction strainer is cleaned and the condenser coil is washed quarterly "
            "per the maintenance schedule."
        ),
    }
    items = [
        DatasetItem(
            item_id="x200-electrical",
            prompt="What electrical supply does the AriaTherm X200 require?",
            reference=references["x200-electrical"],
            capability="specs",
            topic="hvac-x200",
            persona="field_technician",
            difficulty="easy",
            edge_case="none",
        ),
        DatasetItem(
            item_id="x200-refrigerant",
            prompt="Which refrigerant and factory charge does the X200 use?",
            reference=references["x200-refrigerant"],
            capability="specs",
            topic="hvac-x200",
            persona="field_technician",
            difficulty="easy",
            edge_case="none",
        ),
        DatasetItem(
            item_id="x200-cop",
            prompt="What is the COP of the X200 heat pump?",
            reference=references["x200-cop"],
            capability="specs",
            topic="hvac-x200",
            persona="field_technician",
            difficulty="easy",
            edge_case="none",
        ),
        DatasetItem(
            item_id="x200-e04",
            prompt="What does fault code E04 indicate on the X200?",
            reference=references["x200-e04"],
            capability="fault_code_lookup",
            topic="hvac-x200",
            persona="field_technician",
            difficulty="medium",
            edge_case="none",
        ),
        DatasetItem(
            item_id="x200-envelope",
            prompt="What is the heating operating envelope of the X200?",
            reference=references["x200-envelope"],
            capability="specs",
            topic="hvac-x200",
            persona="commissioning_engineer",
            difficulty="medium",
            edge_case="none",
        ),
        DatasetItem(
            item_id="v9-capacity",
            prompt="What is the cooling capacity of the VeyraCool V9?",
            reference=references["v9-capacity"],
            capability="specs",
            topic="hvac-v9",
            persona="field_technician",
            difficulty="easy",
            edge_case="none",
        ),
        DatasetItem(
            item_id="v9-electrical",
            prompt="What electrical supply does the VeyraCool V9 chiller need?",
            reference=references["v9-electrical"],
            capability="specs",
            topic="hvac-v9",
            persona="commissioning_engineer",
            difficulty="easy",
            edge_case="none",
        ),
        DatasetItem(
            item_id="v9-maintenance",
            prompt="How often is the V9 suction strainer cleaned?",
            reference=references["v9-maintenance"],
            capability="maintenance",
            topic="hvac-v9",
            persona="field_technician",
            difficulty="medium",
            edge_case="none",
        ),
    ]
    dataset = EvalDataset(
        version=GOLDEN_DATASET_VERSION,
        generator_version="platformdemo-1.0",
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        config_digest="platformdemo-manual-bank",
        items=items,
    )
    dataset.validate_items()
    return dataset


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
@dataclass
class StageResult:
    ok: bool = True
    ms: float = 0.0
    error: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": self.ok, "ms": round(self.ms, 3)}
        if self.error:
            out["error"] = self.error
        out.update(self.detail)
        return out


def metered_totals(pipeline: GatewayPipeline, tenant: str) -> dict[str, float]:
    """Token/cost totals the gateway meter recorded for one tenant.

    Reads the meter's day bucket (documented internal layout:
    ``_daily[tenant][day][model] -> Totals``); the demo owns the meter
    instance, so there are no concurrent writers.
    """
    prompt = completion = 0
    cost = 0.0
    for day_models in getattr(pipeline.meter, "_daily", {}).get(tenant, {}).values():
        for totals in day_models.values():
            prompt += totals.prompt_tokens
            completion += totals.completion_tokens
            cost += totals.cost_usd
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
        "cost_usd": round(cost, 6),
    }


def write_spans_jsonl(collector: SpanCollector, path: Path) -> int:
    records = [
        {
            "trace_id": trace_id,
            "ts": ts,
            "pipeline_name": "hvac_via_aegisgate",
            "spans": spans,
        }
        for trace_id, ts, spans in collector.trace_groups()
    ]
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8"
    )
    return len(records)


async def run_demo(out_dir: Path | None = None) -> dict[str, Any]:
    """Run the full offline end-to-end proof and return the summary dict."""
    out = Path(out_dir) if out_dir else OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    stages: dict[str, dict[str, Any]] = {}
    started_all = time.perf_counter()

    async def record(name: str, fn: Any) -> Any:
        """Run one stage, await it if it is async, and record ok/ms/error."""
        stage = StageResult()
        start = time.perf_counter()
        try:
            value = fn(stage)
            if inspect.isawaitable(value):
                value = await value
        except Exception as exc:  # noqa: BLE001 - the summary must show the failure
            stage.ok, stage.error = False, f"{type(exc).__name__}: {exc}"
            value = None
        stage.ms = (time.perf_counter() - start) * 1000
        stages[name] = stage.as_dict()
        return value

    # -- stage 1: AegisGate pipeline with a collecting span sink ---------------
    collector = SpanCollector()

    def build_gateway(stage: StageResult) -> GatewayPipeline:
        pipeline = build_pipeline(
            AegisGateSettings(),
            span_sink=collector,  # the pluggable sink hook this demo exists to use
        )
        upstream = type(pipeline.client).__name__
        stage.detail.update(
            {
                "upstream_client": upstream,
                "tenant": TENANT_ID,
                "model": GATEWAY_MODEL,
                "stages_instrumented": 9,
            }
        )
        return pipeline

    pipeline = await record("aegisgate_pipeline_built", build_gateway)

    # -- stage 2: HVAC-Copilot wired so every LLM call goes through the gateway
    def build_hvac(
        stage: StageResult,
    ) -> tuple[HVACCopilot, GatewayRoutedLLMClient, RetrievalSpanProxy]:
        hvac_settings = HVACSettings(
            index_dir=out / ".index",  # keep the sibling repo checkout clean
            corpus_dir=HVAC_REPO_ROOT / "corpus",
        )
        svc = HVACCopilot(hvac_settings)
        stats = svc.ingest(corpus_dir=HVAC_REPO_ROOT / "corpus")
        retriever_proxy = RetrievalSpanProxy(svc.retriever)
        svc.retriever = retriever_proxy  # type: ignore[assignment]
        svc.composer.retriever = retriever_proxy
        router_client = GatewayRoutedLLMClient(pipeline)
        svc.composer.llm = router_client
        svc.llm = router_client  # type: ignore[assignment]
        stage.detail.update(
            {
                "indexed_chunks": stats.total_chunks,
                "llm_provider": "aegisgate-pipeline (EchoMock upstream)",
                "hvac_llm_provider_setting": "mock (client object replaced in-process)",
            }
        )
        return svc, router_client, retriever_proxy

    wired = await record("hvac_routed_through_gateway", build_hvac)

    # -- stage 3: real HVAC queries whose LLM hops traverse the gateway --------
    answers: list[Answer] = []
    kinds: list[str] = []

    async def ask_all(stage: StageResult) -> list[Answer]:
        svc, router_client, retriever_proxy = wired
        plan = [("healthy", q) for q in HEALTHY_QUESTIONS]
        plan.append(("incident_probe", INCIDENT_PROBE))
        for kind, (question, unit_model) in plan:
            t0 = time.perf_counter()
            answer = await svc.ask(question, unit_model=unit_model)
            emit_bridge_spans(
                router_client,
                retriever_proxy,
                collector,
                answer,
                (time.perf_counter() - t0) * 1000,
            )
            answers.append(answer)
            kinds.append(kind)
        stage.detail.update(
            {
                "queries": len(answers),
                "gateway_calls": len(router_client.calls),
                "answers_with_citations": sum(
                    1
                    for a, kind in zip(answers, kinds, strict=True)
                    if kind == "healthy" and a.citations
                ),
            }
        )
        return answers

    await record("hvac_queries_via_gateway", ask_all)

    # -- stage 4: persist the sink stream as ForensiQ-ingestable JSONL ---------
    spans_path = out / "spans.jsonl"

    def write_spans(stage: StageResult) -> int:
        n_traces = write_spans_jsonl(collector, spans_path)
        stage_counts: dict[str, int] = {}
        for span in collector.spans:
            stage_counts[span["name"]] = stage_counts.get(span["name"], 0) + 1
        stage.detail.update(
            {
                "path": str(spans_path),
                "traces": n_traces,
                "spans": len(collector.spans),
                "span_stage_counts": stage_counts,
            }
        )
        return n_traces

    await record("spans_jsonl_written", write_spans)

    # -- stage 5: ForensiQ ingest -> classify -> health -> blame -> drift -> RCA
    def forensiq(stage: StageResult) -> ReportInputs:
        loader = JSONLTraceLoader()
        traces = loader.load(spans_path)
        classifier = FailureClassifier(
            low_score_threshold=RETRIEVE_SCORE_THRESHOLD,
            repetition_min_repeat=REPETITION_MIN_REPEAT,
        )
        failures = classifier.classify_cohort(traces)
        health = StageHealth(low_score_threshold=RETRIEVE_SCORE_THRESHOLD).score(traces)
        blame_distribution: dict[str, dict[str, float]] = {}
        clusters: list[Any] = []
        if failures:  # nothing to blame or cluster in a clean cohort
            ranker = BlameRanker.from_traces(traces, failures)
            blame_distribution = ranker.cohort_blame(traces, failures)
            clusters = FailureClusterer().fit(traces, failures)
        drift = DriftDetector().detect(traces, failures)
        inputs = ReportInputs(
            failures=failures,
            health=health,
            blame_distribution=blame_distribution,
            clusters=clusters,
            drift=drift,
        )
        report = RCAReportGenerator().generate(
            traces,
            inputs,
            title="PlatformDemo E2E — hvac_via_aegisgate",
        )
        report_path = out / "rca_report.md"
        report_path.write_text(report, encoding="utf-8")
        stage.detail.update(
            {
                "ingested_traces": len(traces),
                "ingest_warnings": len(loader.warnings),
                "failure_records": len(failures),
                "failure_taxonomy": sorted({f.taxonomy_id for f in failures}),
                "stage_health": {card.stage: card.status for card in health.stages},
                "drift_alerts": len(drift.alerts),
                "report_path": str(report_path),
                "report_bytes": len(report),
            }
        )
        return inputs

    forensiq_inputs = await record("forensiq_analysis_and_rca", forensiq)

    # -- stage 6: VerdictAI golden eval v1 (healthy) + gate v1-vs-v1 -----------
    dataset = build_golden_dataset()
    answers_bank = {item.item_id: item.reference for item in dataset.items}
    store_path = out / "verdictai_snapshots.jsonl"

    async def golden_v1(stage: StageResult) -> tuple[Any, Any]:
        store = SnapshotStore(store_path)
        judge = HeuristicJudge()
        runner_a = GoldenRunner(
            MockModelAdapter(quality=1.0, answers=answers_bank, model_version="platformdemo-v1"),
            judge=judge,
            store=store,
        )
        snapshot_a = await runner_a.run(dataset)
        runner_b = GoldenRunner(
            MockModelAdapter(quality=1.0, answers=answers_bank, model_version="platformdemo-v1"),
            judge=judge,
            store=store,
        )
        snapshot_b = await runner_b.run(dataset)
        gate = run_gate(
            snapshot_a, snapshot_b, threshold=GATE_THRESHOLD, min_effect=GATE_MIN_EFFECT
        )
        stage.detail.update(
            {
                "dataset_version": dataset.version,
                "dataset_items": len(dataset.items),
                "model_version": snapshot_a.model_version,
                "mean_score": round(snapshot_a.mean(), 4),
                "gate_verdict": gate.verdict,
                "gate_passed": gate.passed,
                "gate_exit_code": gate.exit_code,
            }
        )
        return snapshot_a, gate

    snapshot_v1, gate_v1 = await record("verdictai_golden_v1_and_gate_pass", golden_v1)

    # -- stage 7: VerdictAI degraded v2 + gate v1-vs-v2 (must FAIL) ------------
    async def golden_v2(stage: StageResult) -> tuple[Any, Any]:
        runner = GoldenRunner(
            MockModelAdapter(
                quality=V2_DEGRADE_QUALITY,
                answers=answers_bank,
                model_version="platformdemo-v2",
            ),
            judge=HeuristicJudge(),
            store=SnapshotStore(store_path),
        )
        snapshot_v2 = await runner.run(dataset)
        gate = run_gate(
            snapshot_v1, snapshot_v2, threshold=GATE_THRESHOLD, min_effect=GATE_MIN_EFFECT
        )
        mean_delta = snapshot_v1.mean() - snapshot_v2.mean()
        stage.detail.update(
            {
                "model_version": snapshot_v2.model_version,
                "degrade_quality": V2_DEGRADE_QUALITY,
                "mean_score": round(snapshot_v2.mean(), 4),
                "mean_score_drop": round(mean_delta, 4),
                "drop_percent": round(100 * mean_delta / max(snapshot_v1.mean(), 1e-9), 1),
                "gate_verdict": gate.verdict,
                "gate_passed": gate.passed,
                "gate_exit_code": gate.exit_code,
            }
        )
        return snapshot_v2, gate

    snapshot_v2, gate_v2 = await record("verdictai_golden_v2_and_gate_fail", golden_v2)

    # -- summary ---------------------------------------------------------------
    router_client = wired[1] if wired else None
    metering = (
        metered_totals(pipeline, TENANT_ID)
        if pipeline is not None
        else {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
    )
    all_ok = all(stage["ok"] for stage in stages.values())
    calls = router_client.calls if router_client else []
    answer_rows: list[dict[str, Any]] = []
    for i, answer in enumerate(answers):
        # Sequential asks: the i-th answer maps to the i-th gateway call when
        # the HVAC query cache did not short-circuit composition.
        call = calls[i] if i < len(calls) else {}
        kind = kinds[i] if i < len(kinds) else "unknown"
        answer_rows.append(
            {
                "kind": kind,
                "question": answer.question,
                "answer_chars": len(answer.answer),
                "citations": len(answer.citations),
                "escalation": answer.escalation,
                "cache_hit": answer.cache_hit,
                "gateway_trace_id": call.get("gateway_trace_id"),
                "served_by": call.get("served_by"),
            }
        )
    summary: dict[str, Any] = {
        "meta": {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "mode": "offline (EchoMock upstream, no network)",
            "tenant": TENANT_ID,
            "gateway_model": GATEWAY_MODEL,
        },
        "stages": stages,
        "hvac": {"answers": answer_rows},
        "gateway": {
            "spans_total": len(collector.spans),
            "metering": metering,
            "budget_level": (
                pipeline.meter.status(TENANT_ID).level.value
                if pipeline is not None
                else None
            ),
        },
        "forensiq": {
            "failure_records": len(forensiq_inputs.failures) if forensiq_inputs else 0,
            "failure_taxonomy": (
                sorted({f.taxonomy_id for f in forensiq_inputs.failures}) if forensiq_inputs else []
            ),
            "stage_health": stages.get("forensiq_analysis_and_rca", {}).get("stage_health", {}),
            "drift_alerts": stages.get("forensiq_analysis_and_rca", {}).get("drift_alerts", 0),
        },
        "verdictai": {
            "v1_mean": stages.get("verdictai_golden_v1_and_gate_pass", {}).get("mean_score"),
            "v2_mean": stages.get("verdictai_golden_v2_and_gate_fail", {}).get("mean_score"),
            "gate_v1_vs_v1_exit_code": stages.get("verdictai_golden_v1_and_gate_pass", {}).get(
                "gate_exit_code"
            ),
            "gate_v1_vs_v2_exit_code": stages.get("verdictai_golden_v2_and_gate_fail", {}).get(
                "gate_exit_code"
            ),
            "v2_snapshot_mean_ref": round(snapshot_v2.mean(), 4) if snapshot_v2 else None,
        },
        "totals": {
            "ok": all_ok,
            "ms": round((time.perf_counter() - started_all) * 1000, 1),
        },
    }
    (out / "e2e_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def print_summary_table(summary: dict[str, Any]) -> None:
    meta = summary["meta"]
    print("=" * 72)
    print("PlatformDemo - offline end-to-end integration proof")
    print(f"mode: {meta['mode']} | tenant: {meta['tenant']} | model: {meta['gateway_model']}")
    print("=" * 72)
    for name, stage in summary["stages"].items():
        marker = "PASS" if stage["ok"] else "FAIL"
        extras = " ".join(
            f"{key}={stage[key]}"
            for key in ("queries", "traces", "spans", "failure_records", "gate_exit_code")
            if key in stage
        )
        print(f"[{marker}] {name:<38} {stage['ms']:>9.1f} ms  {extras}")
    gateway = summary["gateway"]
    verdictai = summary["verdictai"]
    print("-" * 72)
    print(
        f"metering: {gateway['metering']['total_tokens']} tokens, "
        f"${gateway['metering']['cost_usd']} for tenant {meta['tenant']}"
    )
    print(
        f"verdict gate: v1-vs-v1 exit {verdictai['gate_v1_vs_v1_exit_code']} (expect 0), "
        f"v1-vs-v2 exit {verdictai['gate_v1_vs_v2_exit_code']} (expect 1)"
    )
    print(f"TOTAL: {'OK' if summary['totals']['ok'] else 'FAILED'} "
          f"in {summary['totals']['ms']} ms")


def main() -> int:
    summary = asyncio.run(run_demo())
    print_summary_table(summary)
    return 0 if summary["totals"]["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
