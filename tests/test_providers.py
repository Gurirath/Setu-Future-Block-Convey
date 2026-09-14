"""Provider selection is environment-driven. No key or provider is written in source."""
import pytest

from setu.providers import get_provider, ProviderUnavailable, BUILDERS, DEFAULT_MODELS

ALL_VARS = ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
            "SETU_PROVIDER", "SETU_MODEL")


@pytest.fixture
def clean_env(monkeypatch):
    for var in ALL_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


class Recorder:
    """Captures constructor args instead of opening a network client."""

    instances: list = []

    def __init__(self, api_key, model=None):
        self.api_key, self.model = api_key, model
        Recorder.instances.append(self)


@pytest.fixture
def recorded(monkeypatch):
    Recorder.instances = []
    monkeypatch.setitem(BUILDERS, "anthropic", Recorder)
    monkeypatch.setitem(BUILDERS, "gemini", Recorder)
    return Recorder


def test_no_key_anywhere_raises(clean_env):
    with pytest.raises(ProviderUnavailable, match="no model API key found"):
        get_provider()


def test_explicit_provider_without_its_key_raises(clean_env):
    clean_env.setenv("SETU_PROVIDER", "gemini")
    with pytest.raises(ProviderUnavailable, match="its API key is not set"):
        get_provider()


def test_unknown_provider_name_raises(clean_env):
    clean_env.setenv("SETU_PROVIDER", "weather-service")
    with pytest.raises(ProviderUnavailable, match="unknown provider"):
        get_provider()


def test_gemini_selected_by_its_key(clean_env, recorded):
    clean_env.setenv("GEMINI_API_KEY", "test-key-g")
    get_provider()
    assert recorded.instances[-1].api_key == "test-key-g"


def test_google_api_key_is_accepted_for_gemini(clean_env, recorded):
    clean_env.setenv("GOOGLE_API_KEY", "test-key-goog")
    get_provider("gemini")
    assert recorded.instances[-1].api_key == "test-key-goog"


def test_explicit_provider_overrides_autodetection(clean_env, recorded):
    clean_env.setenv("ANTHROPIC_API_KEY", "test-key-a")
    clean_env.setenv("GEMINI_API_KEY", "test-key-g")
    clean_env.setenv("SETU_PROVIDER", "gemini")
    get_provider()
    assert recorded.instances[-1].api_key == "test-key-g"


def test_every_builder_has_a_default_model():
    assert set(BUILDERS) == set(DEFAULT_MODELS)
    assert all(DEFAULT_MODELS.values())


def test_real_providers_satisfy_the_generate_contract():
    """Both adapters must expose generate(prompt, schema) without being constructed."""
    from setu.providers import AnthropicProvider, GeminiProvider
    import inspect
    for cls in (AnthropicProvider, GeminiProvider):
        params = inspect.signature(cls.generate).parameters
        assert "prompt" in params and "schema" in params, cls.__name__


def test_transient_rate_limit_is_retried(monkeypatch):
    import setu.providers as providers
    monkeypatch.setattr(providers.time, "sleep", lambda s: None)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("429 RESOURCE_EXHAUSTED. Please retry in 1.5s")
        return "ok"

    assert providers.with_retries(flaky) == "ok"
    assert len(calls) == 3


def test_non_transient_error_is_not_retried(monkeypatch):
    import setu.providers as providers
    monkeypatch.setattr(providers.time, "sleep", lambda s: None)
    calls = []

    def broken():
        calls.append(1)
        raise ValueError("401 invalid api key")

    with pytest.raises(ValueError):
        providers.with_retries(broken)
    assert len(calls) == 1


def test_retry_gives_up_and_reraises(monkeypatch):
    import setu.providers as providers
    monkeypatch.setattr(providers.time, "sleep", lambda s: None)

    def always():
        raise RuntimeError("503 overloaded")

    with pytest.raises(RuntimeError, match="503"):
        providers.with_retries(always)


def test_openai_selected_by_its_key(clean_env, recorded, monkeypatch):
    from setu.providers import BUILDERS
    monkeypatch.setitem(BUILDERS, "openai", Recorder)
    clean_env.setenv("OPENAI_API_KEY", "test-key-o")
    get_provider("openai")
    assert recorded.instances[-1].api_key == "test-key-o"


def test_openai_generate_contract():
    from setu.providers import OpenAIProvider
    import inspect
    params = inspect.signature(OpenAIProvider.generate).parameters
    assert "prompt" in params and "schema" in params


def test_json_mode_only_requested_for_structured_calls():
    """Plain-text prompts must not come back as quoted JSON strings."""
    from setu.providers import OpenAIProvider
    captured = {}

    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.model = "test-model"

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            msg = type("M", (), {"content": "hi"})()
            return type("R", (), {"choices": [type("C", (), {"message": msg})()]})()

    provider._client = type("C", (), {
        "chat": type("Chat", (), {"completions": FakeCompletions()})()})()

    provider.generate("plain question")
    assert "response_format" not in captured
    provider.generate("structured", schema={"type": "object"})
    assert captured["response_format"] == {"type": "json_object"}
