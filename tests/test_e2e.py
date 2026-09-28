"""Offline end-to-end proof: pytest port of demo/pipeline_demo.py.

Runs the identical flow the demo script runs — HVAC queries through the
AegisGate pipeline, span export, ForensiQ forensics, VerdictAI golden gate —
fully offline, then asserts every stage actually executed and the integration
contracts hold. No network, no API keys, no services.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from demo.pipeline_demo import (
    EXPECTED_STAGES,
    HEALTHY_QUESTIONS,
    QUESTIONS,
    SPAN_KEYS,
    TENANT_ID,
    run_demo,
)

RUN_TIMEOUT_S = 300


@pytest.fixture(scope="session")
def e2e(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict[str, Any], Path]:
    out_dir = tmp_path_factory.mktemp("platformdemo_e2e")
    summary = asyncio.run(run_demo(out_dir))
    return summary, out_dir


# --------------------------------------------------------------------------- #
# Stage execution
# --------------------------------------------------------------------------- #
def test_every_stage_executed_and_ok(e2e: tuple[dict[str, Any], Path]) -> None:
    summary, _ = e2e
    stages = summary["stages"]
    missing = [name for name in EXPECTED_STAGES if name not in stages]
    assert not missing, f"stages never ran: {missing}"
    failed = {name: stage for name, stage in stages.items() if not stage["ok"]}
    assert not failed, f"failed stages: {failed}"
    assert summary["totals"]["ok"] is True


def test_summary_artifact_written(e2e: tuple[dict[str, Any], Path]) -> None:
    summary, out_dir = e2e
    path = out_dir / "e2e_summary.json"
    assert path.exists()
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["totals"]["ok"] is True
    assert on_disk["meta"]["tenant"] == TENANT_ID


# --------------------------------------------------------------------------- #
# HVAC-Copilot through the gateway
# --------------------------------------------------------------------------- #
def test_hvac_answers_carry_citations(e2e: tuple[dict[str, Any], Path]) -> None:
    summary, _ = e2e
    answers = summary["hvac"]["answers"]
    assert len(answers) == len(QUESTIONS)
    healthy = [row for row in answers if row["kind"] == "healthy"]
    assert len(healthy) == len(HEALTHY_QUESTIONS)
    for row in healthy:
        assert row["answer_chars"] > 0
        assert row["citations"] >= 1, f"answer without citations: {row['question']}"
        assert row["escalation"] is False  # benign questions must compose, not refuse
        assert row["gateway_trace_id"], "answer did not record a gateway trace id"


def test_gateway_metering_recorded_tokens_for_tenant(
    e2e: tuple[dict[str, Any], Path],
) -> None:
    summary, _ = e2e
    metering = summary["gateway"]["metering"]
    assert metering["total_tokens"] > 0
    assert metering["prompt_tokens"] > 0 and metering["completion_tokens"] > 0
    assert metering["cost_usd"] > 0


def test_gateway_pipeline_ran_every_control_stage(
    e2e: tuple[dict[str, Any], Path],
) -> None:
    summary, _ = e2e
    counts = summary["stages"]["spans_jsonl_written"]["span_stage_counts"]
    # The honest gateway path on every query: limit -> flags -> cache -> route
    # -> execute -> meter -> store. (Autopilot/shadow emit spans too but are
    # not asserted: shadow is a no-op without a configured shadow target.)
    for stage_name in (
        "rate_limit",
        "flags",
        "cache_lookup",
        "autopilot",
        "route",
        "execute",
        "meter",
        "cache_store",
    ):
        assert counts.get(stage_name, 0) >= len(QUESTIONS), (
            f"gateway stage {stage_name!r} ran {counts.get(stage_name, 0)}x, "
            f"expected >= {len(QUESTIONS)}"
        )


# --------------------------------------------------------------------------- #
# Span export schema
# --------------------------------------------------------------------------- #
def test_spans_jsonl_schema_valid(e2e: tuple[dict[str, Any], Path]) -> None:
    _, out_dir = e2e
    lines = (out_dir / "spans.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) >= len(QUESTIONS)
    seen_statuses: set[str] = set()
    for line in lines:
        record = json.loads(line)
        assert record["trace_id"] and record["spans"]
        for span in record["spans"]:
            assert SPAN_KEYS.issubset(span), f"span missing keys: {sorted(span)}"
            assert isinstance(span["duration_ms"], (int, float)) and span["duration_ms"] >= 0
            assert span["status"] in {"ok", "error", "timeout"}
            assert isinstance(span["attrs"], dict)
            seen_statuses.add(span["status"])
    assert seen_statuses == {"ok"}  # a healthy run: every span ok


# --------------------------------------------------------------------------- #
# ForensiQ forensics
# --------------------------------------------------------------------------- #
def test_forensiq_ingest_classify_report(e2e: tuple[dict[str, Any], Path]) -> None:
    summary, out_dir = e2e
    stage = summary["stages"]["forensiq_analysis_and_rca"]
    assert stage["ok"]
    assert stage["ingested_traces"] >= len(QUESTIONS)
    assert stage["ingest_warnings"] == 0  # every span dict must ingest cleanly
    assert stage["failure_records"] >= 0  # classifier ran without error
    assert "retrieve" in stage["stage_health"] and "generate" in stage["stage_health"]
    report = (out_dir / "rca_report.md").read_text(encoding="utf-8")
    assert "Executive summary" in report and "Blame graph" in report
    assert len(report) > 500


def test_forensiq_catches_the_incident_probe(e2e: tuple[dict[str, Any], Path]) -> None:
    """The empty-retrieval probe is a real failure and must be classified."""
    summary, _ = e2e
    stage = summary["stages"]["forensiq_analysis_and_rca"]
    assert stage["failure_records"] == 1
    assert stage["failure_taxonomy"] == ["F-RET-001"]  # empty retrieval set
    assert stage["stage_health"]["retrieve"] in {"warn", "crit"}  # hit_rate dropped
    probe = next(
        row for row in summary["hvac"]["answers"] if row["kind"] == "incident_probe"
    )
    assert probe["citations"] == 0  # nothing retrieved -> nothing to cite
    assert probe["gateway_trace_id"]  # the gateway still serviced the LLM call


def test_rca_report_is_deterministic_shape(e2e: tuple[dict[str, Any], Path]) -> None:
    _, out_dir = e2e
    report = (out_dir / "rca_report.md").read_text(encoding="utf-8")
    for section in ("Failure mix", "Top root causes", "Stage health", "Mapped fixes"):
        assert section in report


# --------------------------------------------------------------------------- #
# VerdictAI golden gate
# --------------------------------------------------------------------------- #
def test_gate_passes_for_v1_vs_v1(e2e: tuple[dict[str, Any], Path]) -> None:
    summary, _ = e2e
    stage = summary["stages"]["verdictai_golden_v1_and_gate_pass"]
    assert stage["ok"]
    assert stage["gate_exit_code"] == 0
    assert stage["gate_passed"] is True
    assert stage["mean_score"] > 0


def test_gate_fails_for_degraded_v2(e2e: tuple[dict[str, Any], Path]) -> None:
    summary, _ = e2e
    stage = summary["stages"]["verdictai_golden_v2_and_gate_fail"]
    assert stage["ok"]
    assert stage["gate_exit_code"] == 1
    assert stage["gate_verdict"] == "regressed"
    assert stage["mean_score_drop"] > 0
    v1_mean = summary["stages"]["verdictai_golden_v1_and_gate_pass"]["mean_score"]
    assert stage["mean_score"] < v1_mean
