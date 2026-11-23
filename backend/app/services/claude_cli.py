"""One-shot JSON calls through the local `claude -p` CLI, which runs on the user's Claude subscription.

Used for the essay review so it costs no API money. The call is bare: no tools, no settings, no saved
session, and it runs from the temp dir so no project CLAUDE.md is picked up. The prompt goes in on stdin.
"""
import asyncio
import json
import re
import shutil
import tempfile
from typing import Optional

from app.core.config import settings

TIMEOUT_SEC = 300
MAX_PARALLEL = 4  # a review runs several calls at once; this keeps the CLI processes bounded

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)
_limit: Optional[asyncio.Semaphore] = None


class ClaudeCliError(RuntimeError):
    """The CLI exited with an error, timed out, or printed something that is not its JSON envelope."""


async def _run(args, stdin: str, cwd: str, timeout: float):
    proc = await asyncio.create_subprocess_exec(
        *args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(stdin.encode()), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise ClaudeCliError(f"claude CLI timed out after {timeout:.0f}s") from None
    return proc.returncode, out.decode(), err.decode()


async def generate_json(prompt: str, model: Optional[str] = None, run=None):
    """Returns (parsed JSON, usage). usage input_tokens counts fresh, cache-written and cache-read input."""
    global _limit
    if _limit is None:
        _limit = asyncio.Semaphore(MAX_PARALLEL)
    run = _run if run is None else run
    args = [
        shutil.which("claude") or "claude", "-p", "--model", model or settings.CLAUDE_REVIEW_MODEL,
        "--tools", "", "--no-session-persistence", "--setting-sources", "", "--output-format", "json",
    ]
    async with _limit:
        code, out, err = await run(args, prompt, tempfile.gettempdir(), TIMEOUT_SEC)
    if code != 0:
        raise ClaudeCliError(f"claude CLI exit {code}: {(err or out).strip()[:300]}")
    try:
        envelope = json.loads(out)
    except json.JSONDecodeError as e:
        raise ClaudeCliError(f"claude CLI printed no JSON envelope: {out[:200]}") from e
    if envelope.get("is_error"):
        raise ClaudeCliError(f"claude CLI error: {str(envelope.get('result'))[:300]}")
    u = envelope.get("usage") or {}
    usage = {
        "input_tokens": (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
                        + (u.get("cache_read_input_tokens") or 0),
        "output_tokens": u.get("output_tokens") or 0,
        "thinking_tokens": (u.get("output_tokens_details") or {}).get("thinking_tokens") or 0,
    }
    return parse_json_text(envelope.get("result") or ""), usage


def parse_json_text(text: str):
    """The JSON in a model answer: the whole text, a fenced block, or the first object/list inside prose
    (long answers sometimes start with a sentence). The error carries the start of the answer."""
    t = text.strip()
    m = _FENCE.match(t)
    if m:
        t = m.group(1)
    try:
        return json.loads(t, strict=False)
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder(strict=False)
    for i, ch in enumerate(t):
        if ch in "{[":
            try:
                return decoder.raw_decode(t, i)[0]
            except json.JSONDecodeError:
                continue
    raise json.JSONDecodeError(f"no JSON in the model answer: {t[:200]!r}", t, 0)
