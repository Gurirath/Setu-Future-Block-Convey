"""Acquisition ladder.

Tries progressively heavier strategies to obtain the real bytes of a source.
If every rung fails, it raises. It never substitutes generated text for a fetch.
"""
import io
from dataclasses import dataclass, field

import requests

from setu.provenance import Document, make_document

USER_AGENT = "SetuEligibilityAgent/0.1 (+research prototype; contact via repo)"
TIMEOUT = 30


class AcquisitionFailure(Exception):
    def __init__(self, url: str, attempts: list[dict]):
        self.url = url
        self.attempts = attempts
        detail = "; ".join(f"{a['rung']}: {a['outcome']}" for a in attempts)
        super().__init__(f"could not acquire {url} -> {detail}")


@dataclass
class LadderResult:
    document: Document | None = None
    attempts: list[dict] = field(default_factory=list)


def _html_to_text(raw: bytes, encoding: str | None) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw.decode(encoding or "utf-8", errors="replace"), "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return "\n".join(
        line for line in (ln.strip() for ln in soup.get_text("\n").splitlines()) if line
    )


def _pdf_to_text(raw: bytes) -> str:
    import pdfplumber
    out = []
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text() or "")
    return "\n".join(ln for ln in "\n".join(out).splitlines() if ln.strip())


def rung_http_static(url: str) -> Document:
    resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    ctype = resp.headers.get("content-type", "")
    raw = resp.content
    if "pdf" in ctype.lower() or url.lower().endswith(".pdf"):
        text = _pdf_to_text(raw)
        method = "http_static+pdf"
    else:
        text = _html_to_text(raw, resp.encoding)
        method = "http_static+html"
    return make_document(raw, text, url, resp.status_code, ctype, method)


def rung_headless(url: str) -> Document:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("playwright not installed (pip install playwright && playwright install chromium)") from exc
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT)
        response = page.goto(url, timeout=TIMEOUT * 1000, wait_until="networkidle")
        html = page.content()
        status = response.status if response else 0
        browser.close()
    raw = html.encode("utf-8")
    return make_document(raw, _html_to_text(raw, "utf-8"), url, status, "text/html", "headless+html")


RUNGS = (
    ("http_static", rung_http_static),
    ("headless", rung_headless),
)


def acquire(url: str, sufficient=None, tracer=None, rungs=RUNGS) -> Document:
    """Return the first Document that satisfies `sufficient`, else raise AcquisitionFailure."""
    attempts: list[dict] = []
    for name, fn in rungs:
        try:
            doc = fn(url)
        except Exception as exc:
            attempts.append({"rung": name, "outcome": f"{type(exc).__name__}: {exc}"[:180]})
            continue
        if sufficient is not None and not sufficient(doc):
            attempts.append({
                "rung": name,
                "outcome": f"fetched {len(doc.text)} chars but content was not sufficient",
            })
            continue
        attempts.append({"rung": name, "outcome": "ok", "chars": len(doc.text),
                         "sha256": doc.sha256})
        if tracer is not None:
            tracer.attempts = attempts
        return doc
    raise AcquisitionFailure(url, attempts)
