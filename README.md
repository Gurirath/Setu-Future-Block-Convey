# Setu

An eligibility agent that only states what it can prove against a source it actually fetched.

## The invariant

> No scheme name, URL, threshold, or eligibility rule is written in source code.
> Every scheme fact is derived at runtime from bytes the system actually fetched,
> and is traceable to the character range it came from.

This is enforced, not claimed. `tests/test_no_hardcoding.py` scans `setu/` and fails
if a scheme name, government URL, currency amount, eligibility threshold, or
placeholder helpline appears in it. That suite includes a meta-test proving the
guard is capable of failing.

## Pipeline

| Stage | Module | What it guarantees |
|---|---|---|
| Acquire | `setu/acquire.py` | Real bytes or an exception. Tries HTTP, then headless render. Never substitutes generated text for a failed fetch. |
| Provenance | `setu/provenance.py` | A document cannot exist without a fetch record. Content is hash-pinned; tampering raises. |
| Anchor | `setu/anchor.py` | A clause identity is a character range into the stored text, not a label a model invented. |
| Compile | `setu/compile_rule.py` | The model reads excerpts and emits a predicate. It cites excerpts by index; an invented index is rejected. It never decides eligibility. |
| Adjudicate | `setu/rules.py` | Pure, deterministic, three-valued. Missing data yields UNKNOWN, never False. |
| Verify | `setu/verify.py` | Every citation must resolve to real text at its anchor in a document whose bytes still match their hash. No model judges this. |
| Trace | `setu/trace.py` | Every stage emits a span. Any verdict is replayable from its trace. |
| Providers | `setu/providers.py` | Anthropic or Gemini, selected from environment. The model is a swappable reader, never the decider. |
| Extract | `setu/extract.py` | Field-agnostic. Parses a reply into whatever type the compiled rule implies, across Indic scripts and digits. |
| Guardrails | `setu/guardrails.py` | Redacts identifier shapes from user input; flags instruction-shaped text in fetched sources. |
| Resolve | `setu/resolve.py` | Finds the governing document. A proposed URL is a hypothesis; fetching is the experiment. |
| Agent | `setu/agent.py` | The multi-turn loop. Asks only what the compiled rule left unknown, in the user's language. |
| PRISM | `setu/prism.py` | Exports spans as PRISM trajectory steps. Observability never changes behaviour. |
| Evaluate | `setu/evaluate.py` | Scores behaviour mechanically. No model judges another model. |
| Web | `setu/web.py` | Local interface showing verdict, clause, source URL and fetch time. |

## Running the interface

```bash
python scripts/serve.py            # http://127.0.0.1:8000
python scripts/evaluate.py --prism # golden set scorecard, exported to PRISM
python scripts/live_check.py <url> --term eligibility --field age=70
```

## PRISM

```bash
# .env
PRISM_API_KEY=...
PRISM_HOST=...
PRISM_PROJECT_ID=...
```

All three are required. Without them export is skipped and the agent runs unchanged --
traces are written locally to `traces/` either way. Compliance score only moves once
trajectories actually reach PRISM; committing code does not send anything.

## Choosing a model provider

```bash
# .env (gitignored)
GEMINI_API_KEY=...          # or ANTHROPIC_API_KEY=...
SETU_PROVIDER=gemini        # optional; auto-detected from whichever key is present
SETU_MODEL=gemini-2.5-flash # optional; overrides the provider default
```

With Gemini the predicate grammar is passed as `response_json_schema`, constraining
generation to the grammar itself. The `_bind_spans` guard still runs regardless --
no schema prevents a model citing an excerpt that was never offered.

## Why three-valued logic

Two-valued logic forces "I don't know" to collapse into "you don't qualify" — which,
for someone entitled to a benefit, is the most expensive possible bug. `evaluate()`
returns TRUE / FALSE / UNKNOWN under Kleene semantics:

- a definite failure still decides the case, even with unknowns present
- an unknown anywhere else suspends the verdict rather than denying it
- the unknown leaves tell you **which question to ask next**, derived from the
  compiled rule rather than from a hardcoded per-scheme slot list

## Rules that no document can answer

Some eligibility is decided by an official register, not by published criteria.
The grammar has a first-class `requires_authority` node for this. It always
evaluates to UNKNOWN and routes the user to the body that can actually decide.
"I cannot determine this, here is who can" is a correct answer.

## Running it

```bash
pip install -r requirements.txt
python -m pytest tests/ -q

# read a live official source; the URL is yours to supply
python scripts/live_check.py <url> --term eligibility --term criteria --field age=70
```

Rule compilation needs `ANTHROPIC_API_KEY`. Without it the pipeline **refuses** at
the compile stage rather than falling back to built-in rules — that refusal is the
designed behaviour, not a missing feature.

Optional: `pip install playwright && playwright install chromium` enables the
headless rung, which JS-rendered government portals require.

## `legacy/`

The previous implementation, quarantined. See `legacy/README.md` for why. Short
version: its corpus was written by a language model, not fetched, so its verifier
was checking model output against model output.
