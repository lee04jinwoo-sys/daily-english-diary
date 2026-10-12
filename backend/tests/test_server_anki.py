"""Anki and Anki Manager run on the Oracle server (oracle-quant) since 2026-10-11.

The Mac reaches them through the SSH tunnel in Projects/infra/anki_tunnel:
localhost:8011 -> Anki Manager, localhost:18765 -> AnkiConnect. AnkiConnect and the
gateway are faked here; nothing reaches a real collection.
"""
import pytest
import requests

from app.core.config import Settings
from app.services import anki_service as anki_module
from app.services.anki_service import anki_service


def test_defaults_point_at_the_server_tunnel(monkeypatch):
    monkeypatch.delenv("ANKI_URL", raising=False)
    monkeypatch.delenv("ANKI_GATEWAY_URL", raising=False)
    s = Settings()
    assert s.ANKI_URL == "http://127.0.0.1:18765"
    assert s.ANKI_GATEWAY_URL == "http://127.0.0.1:8011"


def test_existing_cards_lookup_is_one_round_trip(monkeypatch):
    # Each call through the tunnel costs ~0.6 s; one findNotes per sentence was
    # 10 s+ for a long essay.
    calls = []

    def invoke(action, **params):
        calls.append((action, params))
        if action == "version":
            return 6
        if action == "multi":
            # sentence 1 exists, sentence 2 does not, word exists
            return [[1], [], [7]]
        raise AssertionError(f"unexpected call: {action}")

    monkeypatch.setattr(anki_service, "invoke", invoke)
    res = anki_service.check_existing_cards(["I agree.", "New one."], ["salient"])
    assert res == {"existing_sentences": ["I agree."], "existing_words": ["salient"]}
    assert [c[0] for c in calls if c[0] != "version"] == ["multi"]
    actions = calls[-1][1]["actions"]
    assert [a["action"] for a in actions] == ["findNotes"] * 3


class _Resp:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


def _anki_down(monkeypatch):
    def invoke(action, **params):
        raise ConnectionError("refused")
    monkeypatch.setattr(anki_service, "invoke", invoke)


def test_status_reports_tunnel_down(monkeypatch):
    _anki_down(monkeypatch)

    def get(url, timeout):
        raise requests.exceptions.ConnectionError("refused")
    monkeypatch.setattr(anki_module.requests, "get", get)
    st = anki_service.get_status()
    assert st.connected is False and st.reason == "tunnel_down"


def test_status_reports_server_anki_down(monkeypatch):
    _anki_down(monkeypatch)
    monkeypatch.setattr(anki_module.requests, "get", lambda url, timeout: _Resp({"anki_connected": False}))
    st = anki_service.get_status()
    assert st.connected is False and st.reason == "anki_down"


def test_status_ok(monkeypatch):
    monkeypatch.setattr(anki_service, "invoke", lambda action, **p: 6 if action == "version" else ["Default"])
    st = anki_service.get_status()
    assert st.connected is True and st.reason == "ok"


def test_launch_is_gone_from_the_frontend():
    from pathlib import Path
    src = Path(__file__).resolve().parents[2] / "frontend/src"
    for path in src.rglob("*.ts*"):
        assert "launchAnki" not in path.read_text(), path
