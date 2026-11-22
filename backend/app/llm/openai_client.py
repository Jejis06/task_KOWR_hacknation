"""Minimalny klient OpenAI Chat Completions (httpx, bez dodatkowej zależności) – odpowiedź zawsze w JSON."""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings
from app.core.http import get_client

log = logging.getLogger(__name__)
URL = "https://api.openai.com/v1/chat/completions"


def enabled() -> bool:
    return bool(settings.openai_api_key)


async def complete_json(system: str, messages: list[dict[str, str]], max_tokens: int = 1400) -> dict[str, Any] | None:
    """Zwraca sparsowany JSON albo None (brak klucza, timeout, błąd API, niepoprawny JSON) – wtedy wołający użyje szablonu."""
    if not enabled():
        return None
    model = settings.openai_model
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, *messages],
        "response_format": {"type": "json_object"},
        "max_completion_tokens": max_tokens,
    }
    if model.startswith(("gpt-5", "o3", "o4")):
        body["reasoning_effort"] = "low"   # krótka odpowiedź < 15 s; jakość wystarcza do wyjaśnień
    try:
        r = await get_client().post(URL, json=body, timeout=httpx.Timeout(settings.llm_timeout_s, connect=5.0),
                                    headers={"Authorization": f"Bearer {settings.openai_api_key}"})
        if r.status_code != 200:
            log.warning("OpenAI HTTP %s: %s", r.status_code, r.text[:200])
            return None
        content = r.json()["choices"][0]["message"]["content"] or ""
        return json.loads(content)
    except Exception as e:  # noqa: BLE001 – każdy błąd LLM = zapas z szablonu, nigdy 500 dla rolnika
        log.warning("OpenAI: %s", e)
        return None
