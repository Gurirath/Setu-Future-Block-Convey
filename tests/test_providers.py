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
