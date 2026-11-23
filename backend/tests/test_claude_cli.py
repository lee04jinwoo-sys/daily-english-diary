"""Review calls go through the local `claude -p` CLI (the user's subscription) instead of the paid Gemini key."""
import json
import tempfile

import pytest

from app.core.config import settings
from app.services import claude_cli
from app.services.claude_cli import ClaudeCliError
from app.services.gemini_service import GeminiError, gemini_service
from tests.fakes import Router
from tests.test_lean_review import CONTENT, review_payload, router_for


def envelope(result, **over):
    body = {"type": "result", "is_error": False, "result": result, "total_cost_usd": 0.001,
            "usage": {"input_tokens": 2, "cache_creation_input_tokens": 300, "cache_read_input_tokens": 50,
                      "output_tokens": 40, "output_tokens_details": {"thinking_tokens": 25}}}
    body.update(over)
    return json.dumps(body)


class FakeRun:
    """Stands in for the subprocess: records the call and answers with a canned (returncode, stdout, stderr)."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    async def __call__(self, args, stdin, cwd, timeout):
        self.calls.append({"args": args, "stdin": stdin, "cwd": cwd, "timeout": timeout})
        return self.answers.pop(0)


# --- claude_cli.generate_json ---------------------------------------------------

@pytest.mark.anyio
async def test_command_is_a_bare_one_shot_call_with_no_tools_or_project_context():
    run = FakeRun((0, envelope('{"ok": 1}'), ""))
    data, _ = await claude_cli.generate_json("PROMPT TEXT", model="claude-haiku-5-5", run=run)
    assert data == {"ok": 1}
    call = run.calls[0]
    args = call["args"]
    assert args[0].endswith("claude") and "-p" in args
    assert args[args.index("--model") + 1] == "claude-haiku-5-5"
    assert args[args.index("--tools") + 1] == ""
    assert args[args.index("--setting-sources") + 1] == ""
    assert "--no-session-persistence" in args
    assert args[args.index("--output-format") + 1] == "json"
    assert call["stdin"] == "PROMPT TEXT"          # not on the command line: essays can be long
    assert "PROMPT TEXT" not in " ".join(args)
    assert call["cwd"].startswith(tempfile.gettempdir())  # outside every project, so no CLAUDE.md is loaded


@pytest.mark.anyio
async def test_usage_sums_all_input_kinds_and_reports_thinking():
    run = FakeRun((0, envelope('{"ok": 1}'), ""))
    _, usage = await claude_cli.generate_json("p", run=run)
    assert usage == {"input_tokens": 2 + 300 + 50, "output_tokens": 40, "thinking_tokens": 25}


@pytest.mark.anyio
async def test_fenced_json_is_parsed():
    run = FakeRun((0, envelope('```json\n{"ok": 2}\n```'), ""))
    data, _ = await claude_cli.generate_json("p", run=run)
    assert data == {"ok": 2}


@pytest.mark.anyio
@pytest.mark.parametrize("answer", [
    (1, "", "not logged in"),
    (0, envelope("boom", is_error=True), ""),
    (0, "not json at all", ""),
])
async def test_cli_failure_raises_claude_cli_error(answer):
    with pytest.raises(ClaudeCliError):
        await claude_cli.generate_json("p", run=FakeRun(answer))


@pytest.mark.anyio
@pytest.mark.parametrize("text", [
    'Here is the result:\n{"ok": 4}\nLet me know if you need more.',
    'Sure.\n```json\n{"ok": 4}\n```\nDone.',
    '{"ok": 4}\n(checked all items)',
])
async def test_json_wrapped_in_prose_is_still_read(text):
    data, _ = await claude_cli.generate_json("p", run=FakeRun((0, envelope(text), "")))
    assert data == {"ok": 4}


@pytest.mark.anyio
async def test_a_bare_json_list_is_read():
    data, _ = await claude_cli.generate_json("p", run=FakeRun((0, envelope('[{"id": 1}]'), "")))
    assert data == [{"id": 1}]


@pytest.mark.anyio
async def test_the_error_shows_the_start_of_what_the_model_said():
    with pytest.raises(json.JSONDecodeError) as e:
        await claude_cli.generate_json("p", run=FakeRun((0, envelope("I cannot do that."), "")))
    assert "I cannot do that." in str(e.value)


@pytest.mark.anyio
async def test_unparseable_model_text_raises_json_error():
    with pytest.raises(json.JSONDecodeError):
        await claude_cli.generate_json("p", run=FakeRun((0, envelope("{bad"), "")))


# --- wiring into GeminiService._generate_json -----------------------------------

def fake_cli(monkeypatch, *outcomes):
    calls = []

    async def fake(prompt, model=None, run=None):
        calls.append(prompt)
        out = outcomes[len(calls) - 1]
        if isinstance(out, Exception):
            raise out
        return out, {"input_tokens": 10, "output_tokens": 5, "thinking_tokens": 3}

    monkeypatch.setattr(claude_cli, "generate_json", fake)
    return calls


@pytest.mark.anyio
@pytest.mark.parametrize("label", ["main", "detect", "verify", "score_content", "score_language"])
async def test_review_calls_use_the_cli_and_never_the_paid_key(monkeypatch, label):
    monkeypatch.setattr(settings, "REVIEW_BACKEND", "claude_cli")
    calls = fake_cli(monkeypatch, {"ok": label})
    paid = Router()
    monkeypatch.setattr(gemini_service, "_client", paid)
    assert await gemini_service._generate_json("p", 0, label=label) == {"ok": label}
    assert calls == ["p"] and paid.calls == []


@pytest.mark.anyio
async def test_cli_failure_is_raised_not_replaced_by_the_paid_model(monkeypatch):
    """A fallback would mix two models' band scores in the same trend."""
    monkeypatch.setattr(settings, "REVIEW_BACKEND", "claude_cli")
    fake_cli(monkeypatch, ClaudeCliError("limit reached"))
    paid = Router()
    monkeypatch.setattr(gemini_service, "_client", paid)
    with pytest.raises(ClaudeCliError):
        await gemini_service._generate_json("p", 0, label="main")
    assert paid.calls == []


@pytest.mark.anyio
async def test_malformed_json_is_retried_once_then_raises(monkeypatch):
    monkeypatch.setattr(settings, "REVIEW_BACKEND", "claude_cli")
    err = json.JSONDecodeError("bad", "{", 0)
    calls = fake_cli(monkeypatch, err, {"ok": 1})
    assert await gemini_service._generate_json("p", 0, label="main") == {"ok": 1}
    assert len(calls) == 2
    calls = fake_cli(monkeypatch, err, err)
    with pytest.raises(json.JSONDecodeError):
        await gemini_service._generate_json("p", 0, label="main")


@pytest.mark.anyio
async def test_cli_call_is_recorded_in_the_metrics_file(monkeypatch, tmp_path):
    path = tmp_path / "m.jsonl"
    monkeypatch.setattr(settings, "REVIEW_METRICS_PATH", path)
    monkeypatch.setattr(settings, "REVIEW_BACKEND", "claude_cli")
    monkeypatch.setattr(settings, "CLAUDE_REVIEW_MODEL", "claude-haiku-5-5")
    fake_cli(monkeypatch, {"ok": 1})
    await gemini_service._generate_json("p", 0, label="detect", essay_id="e1")
    row = json.loads(path.read_text().splitlines()[0])
    assert (row["label"], row["essay_id"], row["model"]) == ("detect", "e1", "claude-haiku-5-5")
    assert (row["input_tokens"], row["output_tokens"], row["thinking_tokens"]) == (10, 5, 3)


@pytest.mark.anyio
async def test_backend_gemini_keeps_the_paid_path(monkeypatch):
    monkeypatch.setattr(settings, "REVIEW_BACKEND", "gemini")
    calls = fake_cli(monkeypatch, {"ok": "cli"})
    paid = Router(main={"ok": "paid"})
    monkeypatch.setattr(gemini_service, "_client", paid)
    assert await gemini_service._generate_json("p", 0, label="main") == {"ok": "paid"}
    assert calls == []


@pytest.mark.anyio
async def test_unlabelled_calls_do_not_use_the_cli(monkeypatch):
    """Word lookups and card previews stay on the free-first / paid path."""
    monkeypatch.setattr(settings, "REVIEW_BACKEND", "claude_cli")
    calls = fake_cli(monkeypatch, {"ok": "cli"})
    paid = Router(main={"ok": "paid"})
    monkeypatch.setattr(gemini_service, "_client", paid)
    assert await gemini_service._generate_json("p", 0.2) == {"ok": "paid"}
    assert calls == []


@pytest.mark.anyio
async def test_whole_review_runs_on_the_cli_backend(client, monkeypatch):
    monkeypatch.setattr(settings, "REVIEW_BACKEND", "claude_cli")
    router = router_for(review_payload())
    paid = Router()
    monkeypatch.setattr(gemini_service, "_client", paid)

    async def via_router(prompt, model=None, run=None):
        r = await router.aio.models.generate_content(contents=prompt)
        return json.loads(r.text), {"input_tokens": 1, "output_tokens": 1, "thinking_tokens": 0}

    monkeypatch.setattr(claude_cli, "generate_json", via_router)
    e = (await client.post("/api/essays", json={"prompt": "Work?", "essay_type": "free"})).json()
    res = await client.post("/api/review", json={"essay_id": e["id"], "content": CONTENT})
    assert res.status_code == 200, res.text
    assert res.json()["rubric"]["overall_band"] is not None
    assert paid.calls == [] and len(router.calls) >= 5
