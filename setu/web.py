"""Local web interface.

Stdlib only -- no extra server dependency. Serves a single page and one JSON
endpoint that drives a real Session, so what the browser shows is exactly what the
agent produced: the verdict, the clause it rests on, the URL, and the fetch time.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from setu.agent import Session
from setu.prism import PrismExporter, PrismUnconfigured
from setu.providers import get_provider, ProviderUnavailable

PAGE = (Path(__file__).resolve().parent / "static" / "index.html")

_sessions: dict[str, Session] = {}
_lock = threading.Lock()


def _exporter():
    try:
        return PrismExporter.from_env()
    except (PrismUnconfigured, ImportError):
        return None


def _session_for(conversation_id: str) -> Session:
    with _lock:
        if conversation_id not in _sessions:
            _sessions[conversation_id] = Session(get_provider())
        return _sessions[conversation_id]


def handle_turn(payload: dict) -> dict:
    conversation_id = str(payload.get("conversation_id") or "default")
    message = str(payload.get("message") or "").strip()
    if not message:
        return {"error": "empty message"}

    if payload.get("reset"):
        with _lock:
            _sessions.pop(conversation_id, None)

    try:
        session = _session_for(conversation_id)
    except ProviderUnavailable as exc:
        return {"kind": "refusal", "text": str(exc), "refusal_reason": "no model provider",
                "citations": [], "prism": {"status": "skipped"}}

    reply = session.turn(message)

    prism_status = {"status": "not configured"}
    exporter = _exporter()
    if exporter is not None:
        result = exporter.export(
            session.tracer, conversation_id=conversation_id,
            final_status="success" if reply.kind != "refusal" else "refused",
            model=getattr(session.provider, "model", None))
        prism_status = ({"status": "exported", "trajectory_id": result.trajectory_id,
                         "steps": result.step_count} if result.ok
                        else {"status": "failed", "reason": result.reason})

    return {
        "kind": reply.kind,
        "text": reply.text,
        "language": reply.language,
        "outcome": reply.outcome,
        "citations": reply.citations,
        "source_url": reply.source_url,
        "fetched_at": reply.fetched_at,
        "asked_field": reply.asked_field,
        "refusal_reason": reply.refusal_reason,
        "redactions": reply.redactions,
        "trace_id": reply.trace_id,
        "spans": [{"name": s["name"], "status": s["status"],
                   "duration_ms": s.get("duration_ms")} for s in session.tracer.spans],
        "prism": prism_status,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep the console readable

    def _send(self, code, body, content_type="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            if not PAGE.exists():
                return self._send(500, "interface page is missing", "text/plain")
            return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path != "/api/turn":
            return self._send(404, json.dumps({"error": "not found"}))
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, json.dumps({"error": "invalid JSON"}))
        try:
            result = handle_turn(payload)
        except Exception as exc:  # never leak a stack trace to the page
            result = {"kind": "refusal",
                      "text": "Something failed inside the agent; nothing was answered.",
                      "refusal_reason": f"{type(exc).__name__}: {exc}", "citations": []}
        self._send(200, json.dumps(result, ensure_ascii=False, default=str))


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Setu interface on http://{host}:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
