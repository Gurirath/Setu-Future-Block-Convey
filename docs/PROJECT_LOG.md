# Setu — Project Log

A record of what was decided, what was built, what broke, and what is still open.

- **Project**: Setu, a benefits-eligibility agent that only states what it can prove
- **Repo**: `C:\Lang\ForgeAI`
- **Status as of 2026-09-14**: 182 tests passing; full pipeline verified live against a
  real government source; PRISM tracing live
- **Stack**: Python 3.13 · Gemini / OpenAI / Anthropic (swappable) · PRISM (`prismtrace`)

---

## 1. The one-line idea

> The codebase contains **zero scheme knowledge**. Every threshold, age bar, income cap
> and exclusion is derived at runtime from bytes the system actually fetched, and can be
> traced back to the character range it came from.

This is enforced by a test, not asserted in a README. `tests/test_no_hardcoding.py` fails
the build if a scheme name, government URL, currency amount, eligibility threshold or
placeholder helpline appears anywhere in `setu/`. It includes a meta-test proving the
guard is capable of failing.

---

## 2. Fact-check of the original pitch

Two statistics were checked against primary sources before anything was built.

| Claim | Verdict |
|---|---|
| PM-JAY awareness: 62% aware, 78% of those knew they qualified | **Verified.** Cross-sectional survey, 11,618 households, six states, 2019–20, published in *Health Policy and Planning* (Oxford). |
| "Awareness gap worse specifically in Tamil Nadu" | **Overstated.** The study *excluded Tamil Nadu from the eligibility-awareness analysis entirely* — 664 aware TN households were dropped because that question was not asked there. What is true: awareness *of the scheme* was lower in Tamil Nadu and Meghalaya. |
| Karnataka: "$735 million collected, 2.44% used" | **Could not be verified — dropped.** Neither figure appears in any source found. |

**Replacement figures that are real:**

- Karnataka collected **Rs 5,452.60 crore** (Apr 2014 – Mar 2019); only **Rs 420.72 crore
  (7.7%)** was spent on welfare schemes.
- CAG Performance Audit Report No. 02 of 2025 (Karnataka): Rs 3,861 crore collected,
  Rs 240 crore (6.21%) spent.
- **The strongest stat for this project:** that audit found **71% of construction workers
  were not registered**, attributed to lack of awareness, lengthy procedure and approval
  delays. This is a direct causal link from "didn't know" to "didn't get paid" — the
  unspent-money figures only imply it.

Sources:
- <https://academic.oup.com/heapol/article/38/3/289/6881114> ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10019566/))
- <https://citizenmatters.in/welfare-cess-for-construction-workers-unutilised/>
- <https://cag.gov.in/webroot/uploads/download_audit_report/2025/PA-on-Welfare-of-Building-and-Other-Construction-workers-in-Karnataka-English-068a5aa5c9a9f80.37316414.pdf>

---

## 3. The problem found in the original codebase

`scripts/fetch_schemes.py` **fetched nothing.** It was a Python dict of scheme prose
written by a language model. Its own `SOURCE:` lines admitted it:

> `SOURCE: authored from publicly documented scheme criteria (pmjay.gov.in were not
> fetchable as rendered pages; verify against official source before production use)`

Five of six schemes carried that disclaimer. Everything downstream — the chunker, the
vector index, retrieval, and `verify.py` — treated that text as ground truth. **The
verifier was checking model output against model output**, which proves nothing. This was
precisely the failure mode the pitch deck attacked in competitors.

### Full hardcoding audit

| File | What was hardcoded |
|---|---|
| `scripts/fetch_schemes.py` | ~200 lines of model-authored scheme prose |
| `agent/eligibility.py` | 6 hand-written checkers; thresholds `60`, `10000`, `120000`; hand-typed clause IDs |
| `agent/profile.py` | `SCHEME_NAMES`, `REQUIRED_SLOTS`, `QUESTIONS` |
| `agent/intake.py` | `SCHEME_KEYWORDS`, `STATE_ALIASES`, TN→scheme routing |
| `retrieval/chunk.py` | `SCHEME_CODES` — the 6-scheme registry |
| `agent/pipeline.py` | `OUT_OF_CORPUS_THRESHOLD = 0.4691` (overfit to the golden set), and a **fake helpline `1800-XXX-XXXX` shipped to users** |

All of it is now in `legacy/` with a README explaining why. Nothing on the active path
imports it.

---

## 4. Architecture

```
resolve → acquire → anchor → compile → adjudicate → verify
```

| Stage | Module | Guarantee |
|---|---|---|
| Resolve | `setu/resolve.py` | Finds the governing document. A proposed URL is a hypothesis; fetching is the experiment. |
| Acquire | `setu/acquire.py` | Real bytes or an exception. Never substitutes generated text for a failed fetch. |
| Provenance | `setu/provenance.py` | No document exists without a fetch record. Hash-pinned; tampering raises. |
| Anchor | `setu/anchor.py` | A clause identity is a character range, not a label a model invented. |
| Compile | `setu/compile_rule.py` | The model cites excerpts by index; an invented index is rejected. It never decides. |
| Adjudicate | `setu/rules.py` | Pure, deterministic, three-valued. Missing data yields UNKNOWN, never False. |
| Verify | `setu/verify.py` | Citations must resolve to real text at their anchor. No model judges this. |
| Trace | `setu/trace.py` | Every stage emits a span; any verdict replays from its trace. |
| Agent | `setu/agent.py` | Multi-turn loop. Asks only what the rule left unknown, in the user's language. |
| Providers | `setu/providers.py` | Gemini / OpenAI / Anthropic, selected from environment. |
| Guardrails | `setu/guardrails.py` | Redacts identifier shapes; flags instruction-shaped text in sources. |
| Extract | `setu/extract.py` | Field-agnostic. Type inferred from what the rule compares against. |
| PRISM | `setu/prism.py` | Exports spans as trajectory steps. Observability never changes behaviour. |
| Evaluate | `setu/evaluate.py` | Scores behaviour mechanically. No model judges another model. |
| Web | `setu/web.py` | Local interface showing verdict, clause, source URL, fetch time. |

### Three design decisions worth defending

**1. Three-valued (Kleene) logic.** Two-valued logic forces "I don't know" to collapse
into "you don't qualify" — for someone actually entitled to a benefit, the most expensive
possible bug. A definite failure still decides the case even with unknowns present; an
unknown anywhere else suspends the verdict rather than denying it. The unknown leaves also
**tell you which question to ask next**, which is what eliminated the hardcoded
`REQUIRED_SLOTS` table.

**2. `requires_authority` as a first-class node.** Some eligibility is decided by an
official register, not by published criteria — no document can answer it. That node always
evaluates to UNKNOWN and routes the user to the body that can decide. "I cannot determine
this, here is who can" is a correct answer, not a gap.

**3. The rule is data, not code.** A deterministic engine was kept, but its *thresholds*
now come from the fetched document. Determinism was never the hardcoded part.

---

## 5. Live verification

### Acquisition — the PDF discovery win

Government landing pages are dashboards; the actual rules live in a linked PDF.

```
https://pmkisan.gov.in/                          → 6,306 chars (nav chrome)
https://pmkisan.gov.in/Documents/
  RevisedPM-KISANOperationalGuidelines(English).pdf → 27,410 chars → 384 spans
```

Real exclusion clauses anchored at exact offsets, verified:

```
[0.33] 'v) All Persons who paid Income Tax in last assessment year.'
[0.33] 'of the Income Tax Act, 1961 shall be excluded from any benefit under the Scheme.'

fabricated claim ("must own a helicopter and be under 12") → 0% grounded, rejected
```

### Full pipeline, live, end to end

Against `pmkisan.gov.in` with Gemini:

- The model compiled a valid predicate from the real page
- It **discovered the authority gate on its own**:
  `requires_authority: "State Government and UT administration"` — nothing hardcoded
- Turn 1 correctly **refused** on that gate
- Turn 2 returned **not_eligible**, citing the real exclusion verbatim:
  *"All Persons who paid Income Tax in last assessment year"*

That is a correct answer, derived from a live source, with no scheme knowledge in the
codebase. PM-KISAN does exclude income-tax payers.

### Source reachability (from this machine)

| Source | Result |
|---|---|
| `pmkisan.gov.in` | 200, fetchable |
| `myscheme.gov.in` | 200 but returns *"Something went wrong"* even under headless — actively refusing, likely geo-blocking a non-India IP |
| `nsap.nic.in`, `pmayg.nic.in` | DNS failure for the **whole `.nic.in` zone including the apex**, while `.gov.in` resolves — likely sandbox DNS policy. **Verify from your own network.** |

---

## 6. PRISM

### Status: live and working

- SDK: `prismtrace` → `PRISMtrace(api_key, host, project_id)`
- Verified: `submit_trajectory` returns real trajectory IDs;
  `get_trajectory_evaluation` returns full scorecards
- Per-call LLM traces wired at the `Provider.generate` chokepoint, so every model call
  is covered including future ones

### PRISM caught a real bug in our exporter

First submission scored `plan_quality: 2/10`, `goal_alignment: 2/10`:

> *"The workflow terminates with a final_answer at Step 0 before any substantive work
> occurs, creating a logical sequencing problem."*

It was right. Spans were sorted by **start** time, and the `turn` span wraps everything —
so it started first and was mapped to `final_answer`. PRISM saw a final answer before the
work. Fixed by ordering on completion.

| Dimension | Before | After |
|---|---|---|
| plan_quality | 8.0 | **16.0** |
| goal_alignment | 8.0 | **20.0** |
| reasoning_quality | 6.0 | **15.0** |
| tool_use_quality | 9.0 | **15.0** |
| overall | 97.78 | **98.89** |

> *"poor structural planning and logical sequencing issues"*
> → *"excellent governance-aligned AI execution … exemplifies PRISM-appropriate"*

This is a genuine, measured before/after driven by PRISM's own root-cause output.

### Why the dashboard still showed 48.3%

**Pushing to git does not send traces.** Trajectories only arrive when the agent *runs*
with the PRISM env vars set. The dashboard read "3 traces, 0 agents registered" — so
48.3% was still computed over three old traces from the pre-rewrite system, whose corpus
is now in `legacy/`.

Individual new trajectories score 97–99. Expect the aggregate to climb as new ones land
rather than jump, since it blends with the old three. If PRISM supports filtering, scope
to agent name `setu-eligibility-agent` for a clean read.

---

## 7. Evaluation

The old 52-case golden set asserted clause IDs (`pmkisan-3.1`) generated from the
fabricated corpus — it could not survive the corpus being replaced. The new set asserts
**behaviour**, which stays true as documents change.

Six metrics, all checked mechanically — no model judges another model:

`grounding` · `refusal_accuracy` · `injection_defence` · `pii_containment` ·
`language_fidelity` · `no_open_spans`

**Offline scorecard (stub provider): 19/19 scored cases pass, 1 correctly skipped.**

An important honesty note: the first run scored 82% with three failures. Two were the test
double returning English regardless of requested language; one was a case a stub
structurally cannot test. Rather than tune them away, the harness now marks *"cannot judge
offline"* separately from *"failed"* — counting them either way would have been a lie in
one direction or the other.

---

## 8. Bugs found and fixed

Every one of these was caught by a test or by live running, not by inspection.

| # | Bug | Why it mattered |
|---|---|---|
| 1 | `\w` excludes combining marks — `"2 लाख"` truncated to `"ल"` | Silently lost a ×100,000 scale: a 5-order-of-magnitude income error |
| 2 | `"I'm not sure"` parsed as a denial (contains "not") | Uncertainty must never read as No |
| 3 | Phone numbers matched the 9–18 digit account pattern first | Ordering must be most-specific-first |
| 4 | Tokenizer was `[a-z0-9]+` — **Tamil/Hindi tokenized to nothing** | Non-English queries could never match anything |
| 5 | Relevance scored against a fixed term list | Rejected genuinely relevant pages at 25% |
| 6 | Function words inflating relevance | A page looked relevant for being in English |
| 7 | JSON mode forced on every call | Questions returned as `"How old are you?"` **with quotes** |
| 8 | Span order derived from a clock that rounds to 0 ms on Windows | Silently reverted the ordering fix |
| 9 | Provider rate limit **crashed the whole harness** | Must become a refusal, never an exception |
| 10 | `_is_usable` checked length only | Ladder stopped at a nav-only landing page |
| 11 | Guard regex `rs\.?[\d,]+` matched "answe**rs,** asks" | Our own no-hardcoding guard cried wolf |
| 12 | Test double's `response=None` hit its own default fallback | Needed a sentinel |
| 13 | `gemini-2.5-flash` retired; API says use `gemini-3.6-flash` | Caught by testing rather than assuming |
| 14 | Exclusion citations displayed as "condition met" | A matched exclusion read as *good news* when it was the reason for rejection |

---

## 9. Configuration

`.env` (gitignored — never commit):

```bash
# PRISM
PRISMTRACE_API_KEY=...
PRISMTRACE_PROJECT_ID=...
PRISMTRACE_HOST=https://prism-api-prod.up.railway.app

# Model provider — any one of these
OPENAI_API_KEY=...
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=...

SETU_PROVIDER=openai        # optional; auto-detected from whichever key is present
SETU_MODEL=                 # optional; overrides the provider default
SETU_MAX_RPM=5              # pace requests (Gemini free tier is 5/min); 0 = no pacing
SETU_OFFICIAL_SUFFIXES=     # authority policy, e.g. gov.in,nic.in
SETU_ANCHOR_HINTS=          # eligibility vocabulary; overridable per deployment
```

### Commands

```bash
pip install -r requirements.txt
playwright install chromium          # enables the headless rung

python -m pytest tests/ -q           # 182 tests
python scripts/serve.py              # http://127.0.0.1:8000
python scripts/evaluate.py --prism   # golden set + PRISM export
python scripts/live_check.py <url> --term eligibility --field age=70
```

---

## 10. Still open

| Item | Note |
|---|---|
| **Rotate all keys** | Gemini and PRISM credentials were pasted into a chat transcript |
| **Full 20-case live run** | Needs the OpenAI key in `.env`; ~2–3 min on paid tier vs ~15 min paced on Gemini free tier |
| **`gpt-5` model id unverified** | Default guess; the API will correct it, as happened with Gemini. Override with `SETU_MODEL` |
| **`.nic.in` reachability** | Test from your own network — the failure here may be sandbox DNS policy |
| **`myscheme.gov.in` geo-blocking** | Refuses even under headless; needs testing from an India IP |
| **Cross-verification** | Two independent sources agreeing before shipping an answer — designed, not built |
| **Content-hash churn** | Dynamic pages change hash per fetch; cache compiled rules by clause span, not whole document |
| **OCR rung** | Scanned circulars are not yet readable |

### Honest scorecard against the original PoC vision

Foundation ≈ 85/100 (provenance, determinism, refusal, verification, the non-hardcoding
guarantee — the expensive-to-retrofit parts). Agent layer moved from ≈20 to functional:
resolver, multi-turn loop, live compile, PRISM all now work. The main remaining gaps are
cross-verification, broader source coverage, and a full live evaluation baseline.

---

## 11. Working principles

These held throughout and are worth keeping.

1. **Never author what you failed to fetch.** The original bug was authoring scheme text
   when the fetch failed. If acquisition fails, refuse.
2. **A proposal is a hypothesis; fetching is the experiment.** The model may suggest a
   URL. Reality decides whether it is used.
3. **Verify mechanically, not with a model.** A quote must literally appear at its anchor
   in a hash-pinned document.
4. **Unknown is not False.** Especially when someone's benefit depends on it.
5. **Observability must never change behaviour.** If PRISM is down, the agent still
   answers.
6. **Test what you can, and mark what you can't.** Don't let a stub's limitation inflate
   or deflate a score.
7. **Check, don't assume.** `gemini-2.5-flash` was retired; live probing found it, and the
   same habit found the PDF guidelines, the geo-blocking, and the DNS asymmetry.
