# Quarantined — do not import from here

These files are kept for reference and are **not** on the active code path.

## Why they were removed

### `fetch_schemes.py`
Despite the name it fetched nothing. It contained a Python dict of scheme prose
that had been **written by a language model**, not retrieved from any government
source. Its own `SOURCE:` lines admitted this:

> `SOURCE: authored from publicly documented scheme criteria (pmjay.gov.in were not
> fetchable as rendered pages; verify against official source before production use)`

Five of the six schemes carried that disclaimer. Everything downstream — the
chunker, the vector index, the retrieval layer, and `verify.py` — treated that
text as ground truth. The verifier therefore checked model output against model
output, which proves nothing.

### `eligibility.py`
Six hand-written checker functions with thresholds typed in by a developer
(`age < 60`, `monthly_income > 10000`, `income * 12 >= 120000`) and clause IDs
typed by hand (`"pmkisan-3.1"`). If a scheme changed, the code was silently wrong.

### `raw/*.txt`
The generated output of `fetch_schemes.py`. Same problem: synthetic text presented
as a source corpus.

## What replaced them

The `setu/` package. A rule is now compiled at runtime from bytes actually fetched
from a live source, anchored to exact character offsets in that document, and
evaluated deterministically. If the source cannot be fetched or a rule cannot be
compiled from it, the system **refuses** instead of falling back to built-in
knowledge.

`tests/test_no_hardcoding.py` enforces this: it fails if a scheme name, government
URL, currency amount, or eligibility threshold appears anywhere in `setu/`.
