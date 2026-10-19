"""Ask a local Ollama model. Any failure becomes LlmUnavailable."""

import http.client
import json
import os
import urllib.request

MAX_RESPONSE = 1_000_000  # bytes read at most from the server


class LlmUnavailable(Exception):
    pass


def generate(prompt, model="qwen3:14b", base_url=None, timeout=60):
    base = base_url or os.environ.get("OLLAMA_URL", "http://localhost:11434")
    req = urllib.request.Request(
        f"{base.rstrip('/')}/api/generate",
        data=json.dumps({"model": model, "prompt": prompt, "stream": False}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        # urlopen raises on non-200 (HTTPError), refusal and timeout (both OSError)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = json.loads(resp.read(MAX_RESPONSE))["response"]
    except (OSError, http.client.HTTPException, ValueError, KeyError, TypeError) as e:
        # Only the error type: the prompt holds private mails, it must not leak into logs.
        raise LlmUnavailable(f"Ollama unavailable ({type(e).__name__})") from None
    if not isinstance(text, str):
        raise LlmUnavailable("Ollama unavailable (invalid response)")
    return text
