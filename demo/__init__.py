"""PlatformDemo: vertical integration proof for the AI portfolio.

The integration adapters live in :mod:`demo.pipeline_demo`:
``GatewayRoutedLLMClient`` (HVAC-Copilot LLM calls through the AegisGate
pipeline), ``RetrievalSpanProxy`` (real retrieval evidence for ForensiQ) and
``SpanCollector`` (the gateway ``span_sink`` that feeds spans.jsonl).
"""
