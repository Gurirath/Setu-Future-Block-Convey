import os

MODEL = "claude-haiku-4-5-20251001"

_client = None
_client_init_attempted = False


def get_client():
    global _client, _client_init_attempted
    if _client_init_attempted:
        return _client
    _client_init_attempted = True
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    from anthropic import Anthropic
    _client = Anthropic(api_key=api_key)
    return _client
