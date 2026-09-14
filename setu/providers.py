"""Model providers.

The model is a swappable reader, never the decider. Nothing here knows anything
about schemes; it only turns a prompt into raw text for the compiler to validate.

Selection is by environment, never by a key written in source:
    SETU_PROVIDER = anthropic | gemini   (optional; auto-detected from keys present)
    ANTHROPIC_API_KEY / GEMINI_API_KEY   (or GOOGLE_API_KEY)
    SETU_MODEL                           (optional; overrides the provider default)
"""
import os
from typing import Protocol, runtime_checkable

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5",
    "gemini": "gemini-2.5-flash",
}


class ProviderUnavailable(Exception):
    """No usable model backend. Callers must refuse, never fall back to built-in rules."""


@runtime_checkable
class Provider(Protocol):
    name: str
    model: str

    def generate(self, prompt: str, schema: dict | None = None) -> str:
        """Return raw model text. Must not interpret or decide anything."""
        ...


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str | None = None):
        from anthropic import Anthropic
        self._client = Anthropic(api_key=api_key)
        self.model = model or os.environ.get("SETU_MODEL") or DEFAULT_MODELS["anthropic"]

    def generate(self, prompt: str, schema: dict | None = None) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str | None = None):
        from google import genai
        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self.model = model or os.environ.get("SETU_MODEL") or DEFAULT_MODELS["gemini"]

    def generate(self, prompt: str, schema: dict | None = None) -> str:
        from google.genai import types
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0,
        )
        if schema is not None:
            # Constrain generation to the grammar where the backend supports it.
            try:
                config.response_json_schema = schema
            except Exception:
                pass
        response = self._client.models.generate_content(
            model=self.model, contents=prompt, config=config,
        )
        return response.text or ""


def _key_for(provider_name: str) -> str | None:
    if provider_name == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY")
    if provider_name == "gemini":
        return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    return None


BUILDERS = {"anthropic": AnthropicProvider, "gemini": GeminiProvider}


def get_provider(name: str | None = None, model: str | None = None) -> Provider:
    """Resolve a provider from the environment. Raises if none is usable."""
    requested = name or os.environ.get("SETU_PROVIDER")

    if requested:
        requested = requested.strip().lower()
        if requested not in BUILDERS:
            raise ProviderUnavailable(
                f"unknown provider {requested!r}; expected one of {sorted(BUILDERS)}"
            )
        key = _key_for(requested)
        if not key:
            raise ProviderUnavailable(f"SETU_PROVIDER={requested} but its API key is not set")
        return BUILDERS[requested](key, model)

    for candidate in BUILDERS:
        key = _key_for(candidate)
        if key:
            return BUILDERS[candidate](key, model)

    raise ProviderUnavailable(
        "no model API key found (set ANTHROPIC_API_KEY or GEMINI_API_KEY). "
        "Refusing rather than falling back to built-in rules."
    )
