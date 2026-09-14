"""Model providers.

The model is a swappable reader, never the decider. Nothing here knows anything
about schemes; it only turns a prompt into raw text for the compiler to validate.

Selection is by environment, never by a key written in source:
    SETU_PROVIDER = anthropic | gemini | openai  (optional; auto-detected from keys)
    ANTHROPIC_API_KEY / GEMINI_API_KEY / OPENAI_API_KEY
    SETU_MODEL                                   (optional; overrides the default)
"""
import os
import random
import re
import time
from typing import Protocol, runtime_checkable

# Free tiers are strict (Gemini's is 5 requests/minute). Without pacing, a batch
# run dies partway through on a 429 instead of simply taking longer.
MAX_RPM = int(os.environ.get("SETU_MAX_RPM", "0"))          # 0 disables pacing
MAX_RETRIES = int(os.environ.get("SETU_MAX_RETRIES", "4"))
RETRY_DELAY = re.compile(r"retry in ([\d.]+)s", re.I)

_last_call = [0.0]


def _pace():
    if MAX_RPM <= 0:
        return
    interval = 60.0 / MAX_RPM
    wait = interval - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.monotonic()


def _traced(model: str, prompt: str, call):
    """Run a model call and record it to PRISM. Tracing never alters the result."""
    started = time.monotonic()
    output = call()
    try:
        from setu.prism import record_llm
        record_llm(model, prompt, output, (time.monotonic() - started) * 1000)
    except Exception:
        pass
    return output


def with_retries(call):
    """Retry transient rate limits, honouring the delay the API asks for."""
    last = None
    for attempt in range(MAX_RETRIES):
        _pace()
        try:
            return call()
        except Exception as exc:
            last = exc
            message = str(exc)
            transient = ("429" in message or "RESOURCE_EXHAUSTED" in message
                         or "503" in message or "overloaded" in message.lower())
            if not transient or attempt == MAX_RETRIES - 1:
                raise
            match = RETRY_DELAY.search(message)
            delay = float(match.group(1)) if match else min(2 ** attempt, 30)
            time.sleep(min(delay, 65) + random.uniform(0, 1.5))
    raise last

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5",
    "gemini": "gemini-3.6-flash",
    "openai": "gpt-5",
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
        return _traced(self.model, prompt, lambda: with_retries(
            lambda: self._client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )).content[0].text)


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str | None = None):
        from google import genai
        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self.model = model or os.environ.get("SETU_MODEL") or DEFAULT_MODELS["gemini"]

    def generate(self, prompt: str, schema: dict | None = None) -> str:
        from google.genai import types
        # JSON mode only when a schema is asked for. Forcing it on every call
        # wraps plain-text answers in quotes, so a question comes back as
        # '"How old are you?"' rather than the question itself.
        config = types.GenerateContentConfig(temperature=0)
        if schema is not None:
            config.response_mime_type = "application/json"
            try:
                config.response_json_schema = schema
            except Exception:
                pass
        return _traced(self.model, prompt, lambda: (with_retries(
            lambda: self._client.models.generate_content(
                model=self.model, contents=prompt, config=config,
            )).text or ""))


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str | None = None):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)
        self.model = model or os.environ.get("SETU_MODEL") or DEFAULT_MODELS["openai"]

    def generate(self, prompt: str, schema: dict | None = None) -> str:
        kwargs = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if schema is not None:
            # JSON mode only for structured calls. Forcing it on plain-text prompts
            # returns a quoted JSON string instead of the sentence itself.
            kwargs["response_format"] = {"type": "json_object"}
        return _traced(self.model, prompt, lambda: (with_retries(
            lambda: self._client.chat.completions.create(**kwargs)
        ).choices[0].message.content or ""))


def _key_for(provider_name: str) -> str | None:
    if provider_name == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY")
    if provider_name == "gemini":
        return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if provider_name == "openai":
        return os.environ.get("OPENAI_API_KEY")
    return None


BUILDERS = {"anthropic": AnthropicProvider, "gemini": GeminiProvider,
            "openai": OpenAIProvider}


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
