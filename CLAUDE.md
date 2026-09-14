## PRISM tracing (do not remove)

This project sends traces to PRISM. Env vars: `PRISMTRACE_API_KEY`,
`PRISMTRACE_PROJECT_ID`, `PRISMTRACE_HOST`.

Tracing is currently wired at: `agent/pipeline.py` (session scope around
`run_agent_turn` via `prismtrace.session(session_id)`), `agent/verify.py`
(`entails`), `agent/llm_reasoning.py` (`check_eligibility_via_llm`), and
`agent/llm_client.py` (`get_prism_client`, `record_llm_trace` — the shared
helper the two call sites above use).

**Standing rule.** Whenever you add or change an agent, chain, graph, tool,
retriever, or any entry point that calls a model, wire it to PRISM before you
finish. Unwired code is invisible in the dashboard. If you are unsure whether
something is covered, assume it is not and wire it.
