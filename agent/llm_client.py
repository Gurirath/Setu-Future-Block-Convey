import os

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
GEMINI_MODEL = "gemini-3.5-flash-lite"

_ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if _ANTHROPIC_API_KEY:
    ACTIVE_BACKEND = "anthropic"
    MODEL = ANTHROPIC_MODEL
elif _GEMINI_API_KEY:
    ACTIVE_BACKEND = "gemini"
    MODEL = GEMINI_MODEL
else:
    ACTIVE_BACKEND = None
    MODEL = ANTHROPIC_MODEL

_client = None
_client_init_attempted = False


class _GeminiContent:
    def __init__(self, text: str):
        self.text = text


class _GeminiResponse:
    def __init__(self, text: str):
        self.content = [_GeminiContent(text)]


class _GeminiMessages:
    def __init__(self, genai_client, model: str):
        self._genai_client = genai_client
        self._model = model

    def create(self, model: str = None, max_tokens: int = None, messages: list = None):
        from google.genai import types

        prompt = messages[0]["content"]
        config = types.GenerateContentConfig(max_output_tokens=max_tokens) if max_tokens else None
        response = self._genai_client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        return _GeminiResponse(response.text or "")


class _GeminiClientAdapter:
    def __init__(self, genai_client, model: str):
        self.messages = _GeminiMessages(genai_client, model)


def get_client():
    global _client, _client_init_attempted
    if _client_init_attempted:
        return _client
    _client_init_attempted = True

    if ACTIVE_BACKEND == "anthropic":
        from anthropic import Anthropic
        _client = Anthropic(api_key=_ANTHROPIC_API_KEY)
    elif ACTIVE_BACKEND == "gemini":
        from google import genai
        genai_client = genai.Client(api_key=_GEMINI_API_KEY)
        _client = _GeminiClientAdapter(genai_client, GEMINI_MODEL)

    return _client


_prism_client = None
_prism_client_init_attempted = False


def get_prism_client():
    global _prism_client, _prism_client_init_attempted
    if _prism_client_init_attempted:
        return _prism_client
    _prism_client_init_attempted = True

    api_key = os.environ.get("PRISMTRACE_API_KEY")
    project_id = os.environ.get("PRISMTRACE_PROJECT_ID")
    host = os.environ.get("PRISMTRACE_HOST")
    if not (api_key and project_id and host):
        return None

    from prismtrace import PRISMtrace
    _prism_client = PRISMtrace(api_key=api_key, host=host, project_id=project_id)
    return _prism_client


def record_llm_trace(model: str, input_messages: list, output: str, latency_ms: int) -> None:
    prism_client = get_prism_client()
    if prism_client is None:
        return
    try:
        prism_client.trace_llm(
            model=model,
            input_messages=input_messages,
            output=output,
            latency_ms=latency_ms,
        )
    except Exception:
        pass
