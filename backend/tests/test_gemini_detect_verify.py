"""Error detection and verification can run on the paid Gemini key at temperature 0 (GEMINI_REVIEW_LABELS),
while the rest of the review stays on the Claude CLI. Off by default."""
import pytest

from app.core.config import Settings, settings
from app.services.gemini_service import gemini_service
from tests.fakes import Router
from tests.test_claude_cli import fake_cli


def test_default_is_off(monkeypatch):
    monkeypatch.delenv("GEMINI_REVIEW_LABELS", raising=False)
    assert Settings().GEMINI_REVIEW_LABELS == set()


def test_labels_are_read_from_a_comma_list(monkeypatch):
    monkeypatch.setenv("GEMINI_REVIEW_LABELS", " detect, verify ,")
    assert Settings().GEMINI_REVIEW_LABELS == {"detect", "verify"}


@pytest.mark.anyio
@pytest.mark.parametrize("label", ["detect", "verify"])
async def test_listed_labels_use_gemini_at_temperature_zero(monkeypatch, label):
    monkeypatch.setattr(settings, "REVIEW_BACKEND", "claude_cli")
    monkeypatch.setattr(settings, "GEMINI_REVIEW_LABELS", {"detect", "verify"})
    calls = fake_cli(monkeypatch, {"ok": "cli"})
    paid = Router(main={"ok": "paid"})
    monkeypatch.setattr(gemini_service, "_client", paid)
    assert await gemini_service._generate_json("p", 0, label=label) == {"ok": "paid"}
    assert calls == []
    assert paid.calls[0][1]["config"].temperature == 0


@pytest.mark.anyio
@pytest.mark.parametrize("label", ["main", "score_content", "score_language"])
async def test_other_review_labels_stay_on_the_cli(monkeypatch, label):
    monkeypatch.setattr(settings, "REVIEW_BACKEND", "claude_cli")
    monkeypatch.setattr(settings, "GEMINI_REVIEW_LABELS", {"detect", "verify"})
    calls = fake_cli(monkeypatch, {"ok": "cli"})
    paid = Router(main={"ok": "paid"})
    monkeypatch.setattr(gemini_service, "_client", paid)
    assert await gemini_service._generate_json("p", 0, label=label) == {"ok": "cli"}
    assert paid.calls == []
