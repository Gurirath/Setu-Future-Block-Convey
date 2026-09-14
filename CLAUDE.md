## PRISM tracing (do not remove)

This project sends traces to PRISM. Env vars: `PRISMTRACE_API_KEY`,
`PRISMTRACE_PROJECT_ID`, `PRISMTRACE_HOST`. The shorter `PRISM_*` spelling is
also accepted. SDK: `prismtrace` (`pip install prismtrace-sdk`).

**Standing rule.** Whenever you add or change an agent, chain, graph, tool,
retriever, or any entry point that calls a model, wire it to PRISM before you
finish. Unwired code is invisible in the dashboard. If you are unsure whether
something is covered, assume it is not and wire it.

### Where tracing is wired now

The previous inventory in this file pointed at `agent/pipeline.py`,
`agent/verify.py`, `agent/llm_reasoning.py` and `agent/llm_client.py`. Those
modules were retired to `legacy/` when the fabricated-corpus pipeline was
replaced; nothing on the active path imports them. Current wiring:

**Per-call LLM traces** — `setu/providers.py`, in `_traced()`.
Every model call in the project funnels through `Provider.generate`, so this one
chokepoint covers all of them, including call sites added later. It calls
`setu.prism.record_llm`, which is a silent no-op when PRISM is unconfigured.
`tests/test_prism.py::test_every_model_call_goes_through_the_traced_chokepoint`
fails if a provider stops using it.

**Trajectory exports** — one per agent run:

| Entry point | Exports via |
|---|---|
| `setu/web.py` (`handle_turn`) | `PrismExporter.from_env()` per turn |
| `scripts/evaluate.py` | one trajectory per golden-set case |
| `scripts/live_check.py` | `setu.pipeline.export_trace` |
| `setu/pipeline.py` | `export_trace()` helper |

**Span → step mapping** lives in `setu/prism.py` (`STEP_MAP`, `LABELS`,
`CONCLUSIONS`). Steps are ordered by the `seq` counter that `setu/trace.py`
assigns when a span closes — not by wall clock, which rounds to 0 ms on Windows
and puts the final answer first.

### Two rules for the tracing code itself

1. **Observability must never change behaviour.** If PRISM is unconfigured, down,
   or rejects a payload, the agent still answers. Export failures are reported,
   never raised.
2. **Nothing invented.** A step reports what its span actually recorded.

### When adding a new model call site

Call it through a `Provider` from `setu/providers.py` and it is traced
automatically. If you add a new *entry point* (a script, server route, or job),
also export its trajectory — see the table above for the pattern.
