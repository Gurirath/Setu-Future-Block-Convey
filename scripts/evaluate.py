"""Run the golden set and print a scorecard.

    python scripts/evaluate.py [--prism] [--json report.json]

Every metric is checked mechanically. No model judges another model's output.
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

from setu.agent import Session            # noqa: E402
from setu.evaluate import evaluate        # noqa: E402
from setu.providers import get_provider, ProviderUnavailable  # noqa: E402
from setu.prism import PrismExporter, PrismUnconfigured       # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prism", action="store_true", help="export each case to PRISM")
    parser.add_argument("--json", help="write the full report to this path")
    args = parser.parse_args()

    try:
        provider = get_provider()
    except ProviderUnavailable as exc:
        print(f"cannot evaluate: {exc}")
        return 2

    exporter = None
    if args.prism:
        try:
            exporter = PrismExporter.from_env()
        except (PrismUnconfigured, ImportError) as exc:
            print(f"PRISM export unavailable: {exc}")

    sessions = []

    def factory():
        session = Session(provider)
        sessions.append(session)
        return session

    summary, results = evaluate(factory, live=True)

    print(f"\n  cases {summary['passed']}/{summary['cases']} passed")
    print("  " + "-" * 44)
    for name, value in summary["metrics"].items():
        shown = "n/a" if value is None else f"{value:.0%}"
        print(f"  {name:<20} {shown:>6}")
    print("  " + "-" * 44)
    overall = summary["overall"]
    print(f"  {'overall':<20} {('n/a' if overall is None else f'{overall:.0%}'):>6}\n")

    for result in results:
        if result.skipped:
            print(f"  SKIP {result.case_id:<5} [{result.category}] needs a live provider")
        elif not result.passed:
            print(f"  FAIL {result.case_id:<5} [{result.category}] {result.kind}")
            for failure in result.failures:
                print(f"        - {failure}")

    if exporter:
        exported = 0
        for session, result in zip(sessions, results):
            outcome = exporter.export(
                session.tracer, conversation_id=f"eval-{result.case_id}",
                final_status="success" if result.passed else "failure",
                model=getattr(provider, "model", None))
            exported += 1 if outcome.ok else 0
        exporter.flush()
        print(f"\n  exported {exported}/{len(results)} trajectories to PRISM")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "summary": summary,
            "results": [vars(r) for r in results],
        }, indent=2, default=str), encoding="utf-8")
        print(f"  report written to {args.json}")

    return 0 if summary["passed"] == summary["scored"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
