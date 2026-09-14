"""Start the local Setu interface.

    python scripts/serve.py [--port 8000]

Needs a model provider key (ANTHROPIC_API_KEY or GEMINI_API_KEY). PRISM export is
automatic when PRISM_API_KEY, PRISM_HOST and PRISM_PROJECT_ID are set.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from setu.web import serve  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    serve(args.host, args.port)
