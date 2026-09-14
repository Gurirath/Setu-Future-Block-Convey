"""Run the full pipeline against a live official source.

The URL is supplied by the caller. Nothing about any scheme is stored in this repo.

    python scripts/live_check.py <url> [--age 70] [--term eligibility --term farmer]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from setu.pipeline import answer  # noqa: E402
from setu.trace import Tracer  # noqa: E402
from setu.pipeline import export_trace  # noqa: E402


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="official source URL to read")
    parser.add_argument("--term", action="append", default=[],
                        help="query term used to locate relevant passages (repeatable)")
    parser.add_argument("--field", action="append", default=[], metavar="NAME=VALUE",
                        help="a known fact about the applicant (repeatable)")
    return parser.parse_args(argv)


def build_profile(pairs):
    profile = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--field expects NAME=VALUE, got {pair!r}")
        name, _, value = pair.partition("=")
        if value.lower() in ("true", "false"):
            parsed = value.lower() == "true"
        else:
            try:
                parsed = int(value)
            except ValueError:
                try:
                    parsed = float(value)
                except ValueError:
                    parsed = value
        profile[name.strip()] = parsed
    return profile


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    terms = args.term or ["eligibility", "eligible", "criteria", "exclusion"]
    profile = build_profile(args.field)

    tracer = Tracer()
    result = answer(args.url, profile, terms, tracer=tracer)

    print(f"\nsource   : {result.source_url}")
    print(f"fetched  : {result.fetched_at or '(not fetched)'}")
    print(f"outcome  : {result.outcome.upper()}")
    print(f"message  : {result.message}")
    if result.ask_for:
        print(f"asks for : {result.ask_for}")
    if result.refusal_reason:
        print(f"reason   : {result.refusal_reason}")
    for citation in result.citations:
        print(f"\n  condition : {citation['condition']}")
        print(f"  your value: {citation['your_value']}  satisfied={citation['satisfied']}")
        print(f"  source    : offsets {citation['anchor']['start']}..{citation['anchor']['end']}")
        print(f"  quote     : {citation['quote'][:160]!r}")

    path = tracer.flush()
    print(f"\ntrace    : {result.trace_id}  ->  {path}")
    for span in tracer.spans:
        attrs = {k: v for k, v in span["attrs"].items() if k != "url"}
        print(f"  [{span['status']}] {span['name']:<11} {span['duration_ms']:>8.1f}ms  "
              f"{json.dumps(attrs, default=str)[:110]}")
    return 0 if result.outcome != "refused" else 1


if __name__ == "__main__":
    raise SystemExit(main())
