"""A minimal Ollama client.

Ollama is entirely optional. Nothing in the default pipeline touches it, and
every caller is expected to handle :class:`OllamaUnavailable` by falling back to
a deterministic local implementation.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from resumex.config import OllamaConfig
from resumex.exceptions import ResumexError
from resumex.logging import get_logger

logger = get_logger(__name__)


class OllamaUnavailable(ResumexError):
    """Ollama is not running, not reachable, or refused the request."""


class OllamaClient:
    def __init__(self, config: OllamaConfig) -> None:
        self.config = config

    @property
    def base_url(self) -> str:
        return self.config.url.rstrip("/")

    def is_available(self) -> bool:
        """True if the daemon answers. Never raises."""
        try:
            self.list_models()
        except OllamaUnavailable:
            return False
        return True

    def list_models(self) -> list[str]:
        payload = self._request("/api/tags", None, timeout=5.0)
        models = payload.get("models") or []
        return [str(m.get("name", "")) for m in models if m.get("name")]

    def generate(self, prompt: str, *, json_mode: bool = False) -> str:
        body: dict[str, object] = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
        }
        if json_mode:
            body["format"] = "json"
        payload = self._request("/api/generate", body, timeout=self.config.timeout)
        return str(payload.get("response", "")).strip()

    def _request(self, path: str, body: dict | None, *, timeout: float) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise OllamaUnavailable(
                f"Ollama returned HTTP {exc.code} for {path}: {detail.strip()[:200]}",
                hint=(
                    f"Check that the model {self.config.model!r} is pulled: "
                    f"ollama pull {self.config.model}"
                ),
            ) from exc
        except urllib.error.URLError as exc:
            raise OllamaUnavailable(
                f"Could not reach Ollama at {self.base_url}: {exc.reason}",
                hint="Start it with `ollama serve`, or set ollama.enabled = false.",
            ) from exc
        except (TimeoutError, json.JSONDecodeError) as exc:
            raise OllamaUnavailable(f"Ollama request to {path} failed: {exc}") from exc
