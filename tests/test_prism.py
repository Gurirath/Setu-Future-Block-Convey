import pytest

from setu.prism import (PrismExporter, PrismUnconfigured, spans_to_steps,
                        STEP_MAP, ExportResult)
from setu.trace import Tracer


_DEFAULT = object()


class FakePrismClient:
    def __init__(self, response=_DEFAULT, boom=None):
        self.response = ({"trajectory_id": "traj-1", "step_count": 3}
                         if response is _DEFAULT else response)
        self.boom = boom
        self.submitted = None
        self.kwargs = None
        self.flushed = False

    def submit_trajectory(self, steps, **kwargs):
        if self.boom:
            raise self.boom
        self.submitted, self.kwargs = steps, kwargs
        return self.response

    def get_trajectory_evaluation(self, trajectory_id):
        return {"trajectory_id": trajectory_id, "compliance_score": 0.9}

    def flush(self):
        self.flushed = True


def build_tracer():
    tracer = Tracer()
    with tracer.span("turn", language="en"):
        with tracer.span("resolve", query="old age assistance"):
            pass
        with tracer.span("acquire", sha256="abc", chars=4000):
            pass
        with tracer.span("adjudicate", value="true", fired=2):
            pass
    return tracer


def test_every_span_becomes_a_step_in_completion_order():
    steps = spans_to_steps(build_tracer().spans)
    assert len(steps) == 4
    # The reply is what finishes last, so it must be the final step.
    assert steps[-1]["label"].startswith("Reply")
    assert steps[0]["label"].startswith("Locate")


def test_tool_steps_carry_a_tool_name():
    steps = spans_to_steps(build_tracer().spans)
    tool_steps = [s for s in steps if s["step_type"] == "tool_call"]
    assert {s["tool_name"] for s in tool_steps} == {"resolve_source", "fetch_document"}
    assert all("tool_name" in s for s in tool_steps)


def test_reasoning_steps_carry_no_tool_name():
    steps = spans_to_steps(build_tracer().spans)
    for step in steps:
        if step["step_type"] != "tool_call":
            assert "tool_name" not in step


def test_step_types_are_within_the_documented_vocabulary():
    allowed = {"reasoning", "tool_call", "final_answer"}
    assert set(t for t, _ in STEP_MAP.values()) <= allowed
    assert all(s["step_type"] in allowed for s in spans_to_steps(build_tracer().spans))


def test_span_attributes_reach_the_output_summary():
    steps = spans_to_steps(build_tracer().spans)
    adjudicate = next(s for s in steps if s["label"].startswith("Evaluate"))
    assert "value=true" in adjudicate["output_summary"]


def test_failed_span_is_marked_error_and_keeps_its_message():
    tracer = Tracer()
    with pytest.raises(ValueError):
        with tracer.span("compile"):
            raise ValueError("model returned prose")
    step = spans_to_steps(tracer.spans)[0]
    assert step["status"] == "error"
    assert "model returned prose" in step["output_summary"]


def test_export_returns_trajectory_id():
    client = FakePrismClient()
    result = PrismExporter(client).export(build_tracer(), conversation_id="conv-9")
    assert result.ok and result.trajectory_id == "traj-1"
    assert client.kwargs["conversation_id"] == "conv-9"
    assert client.kwargs["agent_name"] == "setu-eligibility-agent"


def test_export_failure_is_reported_not_raised():
    result = PrismExporter(FakePrismClient(boom=RuntimeError("503"))).export(build_tracer())
    assert isinstance(result, ExportResult)
    assert not result.ok and "503" in result.reason


def test_empty_response_is_reported_not_raised():
    result = PrismExporter(FakePrismClient(response=None)).export(build_tracer())
    assert not result.ok


def test_export_with_no_spans_is_refused():
    result = PrismExporter(FakePrismClient()).export(Tracer())
    assert not result.ok and "no spans" in result.reason


ALL_PRISM_VARS = ("PRISM_API_KEY", "PRISM_HOST", "PRISM_PROJECT_ID",
                  "PRISMTRACE_API_KEY", "PRISMTRACE_HOST", "PRISMTRACE_PROJECT_ID")


def test_missing_credentials_raises_unconfigured(monkeypatch):
    for var in ALL_PRISM_VARS:
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(PrismUnconfigured, match="API_KEY"):
        PrismExporter.from_env()


def test_partial_credentials_names_what_is_missing(monkeypatch):
    for var in ALL_PRISM_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("PRISMTRACE_API_KEY", "k")
    with pytest.raises(PrismUnconfigured) as exc:
        PrismExporter.from_env()
    assert "HOST" in str(exc.value) and "API_KEY" not in str(exc.value)


def test_both_env_spellings_are_accepted(monkeypatch):
    """The SDK's own naming and the shorter form must both work."""
    from setu.prism import PrismExporter as PE
    for var in ALL_PRISM_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("PRISM_API_KEY", "k")
    monkeypatch.setenv("PRISM_HOST", "https://h.test")
    monkeypatch.setenv("PRISM_PROJECT_ID", "p")
    captured = {}
    monkeypatch.setattr("prismtrace.PRISMtrace",
                        lambda **kw: captured.update(kw) or object())
    PE.from_env()
    assert captured["api_key"] == "k"


def test_evaluation_is_read_back():
    exporter = PrismExporter(FakePrismClient())
    assert exporter.evaluation("traj-1")["compliance_score"] == 0.9


def test_evaluation_failure_returns_none():
    class Broken(FakePrismClient):
        def get_trajectory_evaluation(self, trajectory_id):
            raise RuntimeError("gone")
    assert PrismExporter(Broken()).evaluation("traj-1") is None


def test_final_answer_is_the_last_step_not_the_first():
    """The outer turn span starts first but finishes last; PRISM must see it last."""
    steps = spans_to_steps(build_tracer().spans)
    assert steps[-1]["step_type"] == "final_answer"
    assert steps[0]["step_type"] != "final_answer"


def test_reasoning_steps_state_their_conclusion():
    steps = spans_to_steps(build_tracer().spans)
    adjudicate = next(s for s in steps if s["label"].startswith("Evaluate"))
    assert "deterministic verdict" in adjudicate["output_summary"]


def test_tool_steps_describe_what_they_retrieved():
    steps = spans_to_steps(build_tracer().spans)
    acquire = next(s for s in steps if s.get("tool_name") == "fetch_document")
    assert "content hash" in acquire["output_summary"]


def test_ordering_survives_a_zero_duration_clock():
    """On a coarse timer every span can measure 0 ms; order must still hold."""
    tracer = build_tracer()
    for span in tracer.spans:
        span["duration_ms"] = 0.0
    steps = spans_to_steps(tracer.spans)
    assert steps[-1]["step_type"] == "final_answer"
    assert steps[0]["label"].startswith("Locate")


def test_ordering_falls_back_when_seq_is_absent():
    tracer = build_tracer()
    for span in tracer.spans:
        span.pop("seq", None)
    assert len(spans_to_steps(tracer.spans)) == 4


def test_record_llm_is_a_silent_noop_without_credentials(monkeypatch):
    """Tracing must never break a run when PRISM is not configured."""
    import setu.prism as prism
    for var in ALL_PRISM_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(prism, "_llm_client", [])
    assert prism.record_llm("m", "prompt", "out", 12) is False


def test_record_llm_sends_the_call(monkeypatch):
    import setu.prism as prism
    captured = {}

    class Client:
        def trace_llm(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(prism, "_llm_client", [Client()])
    assert prism.record_llm("gpt-x", "hello", "world", 42) is True
    assert captured["model"] == "gpt-x"
    assert captured["output"] == "world"
    assert captured["latency_ms"] == 42


def test_record_llm_swallows_transport_errors(monkeypatch):
    import setu.prism as prism

    class Broken:
        def trace_llm(self, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(prism, "_llm_client", [Broken()])
    assert prism.record_llm("m", "p", "o", 1) is False


def test_every_model_call_goes_through_the_traced_chokepoint():
    """If a provider stops using _traced, per-call tracing silently disappears."""
    import inspect
    from setu import providers
    for cls in (providers.AnthropicProvider, providers.GeminiProvider,
                providers.OpenAIProvider):
        source = inspect.getsource(cls.generate)
        assert "_traced(" in source, f"{cls.__name__}.generate is not traced"
