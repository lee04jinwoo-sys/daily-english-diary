"""Free-tier LLMs tried in order for work that does not affect scoring; the caller falls back to the paid key.

Same design as Anki Manager's core/llm_router.py, made async. Every route is an OpenAI-compatible
/chat/completions endpoint. A route whose key is not in the environment is skipped without a request,
so with no keys set nothing changes. 429, 5xx, timeouts, connection errors and broken JSON all move on
to the next route.

The default model names were not checked against each provider's docs (unverified); adjust after
comparing quality.
"""
import json
import logging
import os
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

ROUTE_TIMEOUT_SEC = 25


@dataclass(frozen=True)
class Route:
    name: str
    url: str
    model: str
    key_env: str


GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

DEFAULT_ROUTES = [
    Route("gemini-free", GEMINI_OPENAI_URL, "gemini-2.5-flash", "GEMINI_FREE_API_KEY"),
    Route("gemini-free-lite", GEMINI_OPENAI_URL, "gemini-2.5-flash-lite", "GEMINI_FREE_API_KEY"),
    Route("groq", "https://api.groq.com/openai/v1/chat/completions", "openai/gpt-oss-120b", "GROQ_API_KEY"),
    Route("cerebras", "https://api.cerebras.ai/v1/chat/completions", "gpt-oss-120b", "CEREBRAS_API_KEY"),
]


class AllRoutesFailed(Exception):
    pass


_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _parse_json(text):
    if text is None:
        raise ValueError("empty content")
    m = _FENCE.match(text)
    if m:
        text = m.group(1)
    return json.loads(text, strict=False)


async def _httpx_post(url, headers, json, timeout):
    async with httpx.AsyncClient() as client:
        return await client.post(url, headers=headers, json=json, timeout=timeout)


async def generate_json(prompt: str, temperature: float, routes=None, post=None, env=None):
    """Returns (parsed JSON, name of the route that answered); raises AllRoutesFailed otherwise."""
    routes = DEFAULT_ROUTES if routes is None else routes
    post = _httpx_post if post is None else post
    env = os.environ if env is None else env

    failures = []
    for route in routes:
        key = env.get(route.key_env)
        if not key:
            failures.append(f"{route.name}: no key")
            continue
        try:
            resp = await post(
                route.url,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": route.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "response_format": {"type": "json_object"},
                },
                timeout=ROUTE_TIMEOUT_SEC,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}")
            data = _parse_json(resp.json()["choices"][0]["message"]["content"])
        except Exception as e:  # any failure moves on to the next route
            logger.warning("LLM route %s failed: %s", route.name, e)
            failures.append(f"{route.name}: {e}")
            continue
        logger.info("LLM route %s (%s) answered", route.name, route.model)
        return data, route.name

    raise AllRoutesFailed("; ".join(failures) or "no routes")
