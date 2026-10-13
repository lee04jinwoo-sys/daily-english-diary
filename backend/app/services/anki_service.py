import requests
import re
import logging
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.schemas.anki import (
    AnkiStatusResponse, AnkiActionResponse, GrammarCardRequest, SentenceCardRequest, VocabCardRequest,
)

logger = logging.getLogger(__name__)

# Anki Manager card rules (config.py NOTE_COMPLETOR_SYS_INSTRUCT) — the gateway applies them;
# these constants only shape what we send and how we pre-check duplicates.
SENTENCE_DECK, SENTENCE_MODEL = "1. Language::1.1. English::Sentence", "English Sentence"
VOCAB_DECK, VOCAB_MODEL = "1. Language::1.1. English::Vocabulary", "English Vocabulary"
GRAMMAR_DECK, GRAMMAR_MODEL = "1. Language::1.1. English::Grammar", "English Grammar"
ALLOWED_POS = {"n", "v", "adj", "adv", "idiom"}
CARD_TAG = "daily-english-essay"
TUNNEL_DOWN = ("오라클 서버 Anki에 연결할 수 없습니다. SSH 터널(Projects/infra/anki_tunnel)이 "
               "떠 있는지 확인하세요.")


def normalize_meaning(meaning: str) -> str:
    """Anki Manager rule: meanings are comma-separated, never slash-separated."""
    parts = [p.strip() for p in re.split(r"\s*/\s*", (meaning or "").strip()) if p.strip()]
    return ", ".join(parts)


class AnkiService:
    def __init__(self):
        self.url = settings.ANKI_URL

    def invoke(self, action: str, **params) -> Any:
        """Invokes an action on AnkiConnect via HTTP POST."""
        try:
            response = requests.post(
                self.url,
                json={"action": action, "version": 6, "params": params},
                timeout=5
            )
            response.raise_for_status()
            res_json = response.json()
            if res_json.get("error"):
                raise RuntimeError(res_json["error"])
            return res_json.get("result")
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"AnkiConnect에 연결할 수 없습니다 ({self.url}). {TUNNEL_DOWN}")
        except Exception as e:
            raise RuntimeError(f"AnkiConnect 호출 오류 ({action}): {str(e)}")

    def check_connection(self) -> bool:
        try:
            res = self.invoke("version")
            return res is not None
        except Exception:
            return False

    def _precheck(self, deck: str, model: str, fields: dict, duplicate_msg: str) -> Optional[AnkiActionResponse]:
        """Ask Anki whether the note can be added before spending TTS / Gemini calls on it."""
        try:
            result = self.invoke("canAddNotesWithErrorDetail", notes=[{
                "deckName": deck, "modelName": model, "fields": fields,
                "options": {"allowDuplicate": False}}])[0]
        except Exception:
            return None  # older AnkiConnect: fall through and let addNote decide
        if result.get("canAdd"):
            return None
        err = result.get("error", "")
        if "duplicate" in err.lower():
            return AnkiActionResponse(success=True, duplicate=True, message=duplicate_msg)
        return AnkiActionResponse(success=False, error=f"카드 추가 불가: {err}")

    def _gateway_add(self, kind: str, payload: dict) -> AnkiActionResponse:
        """Create the card through the Anki Manager gateway, which owns the card rules
        (fields, enrichment prompts, zero synonyms, audio, link indexing)."""
        url = f"{settings.ANKI_GATEWAY_URL}/api/cards/{kind}"
        try:
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code == 400:  # the gateway refused the card and says why
                try:
                    reason = resp.json().get("detail")
                except Exception:
                    reason = None
                if reason:
                    return AnkiActionResponse(success=False, error=str(reason))
            resp.raise_for_status()
            body = resp.json()
        except requests.exceptions.ConnectionError:
            return AnkiActionResponse(success=False, error=f"서버 Anki Manager({settings.ANKI_GATEWAY_URL})에 연결할 수 없습니다. {TUNNEL_DOWN}")
        except Exception as e:
            return AnkiActionResponse(success=False, error=f"Anki Manager 카드 추가 오류: {e}")
        if body.get("duplicate"):
            return AnkiActionResponse(success=True, duplicate=True, message="이미 Anki에 등록된 카드입니다.")
        if not body.get("success"):
            return AnkiActionResponse(success=False, error=body.get("error") or "Anki Manager가 카드를 추가하지 못했습니다.")
        note_id = body.get("note_id")
        if note_id:
            try:
                self.invoke("addTags", notes=[note_id], tags=CARD_TAG)
            except Exception as e:
                logger.warning(f"Tagging note {note_id} failed: {e}")
        return AnkiActionResponse(success=True, note_id=note_id, message="Anki 카드가 등록되었습니다! (Anki Manager 규칙 적용)")

    def add_sentence_card(self, req: SentenceCardRequest) -> AnkiActionResponse:
        """Adds a sentence card via the Anki Manager gateway."""
        if not self.check_connection():
            return AnkiActionResponse(success=False, error=TUNNEL_DOWN)
        sentence = req.sentence.strip()
        if not sentence:
            return AnkiActionResponse(success=False, error="문장이 비어있습니다.")
        blocked = self._precheck(SENTENCE_DECK, SENTENCE_MODEL, {"문장": sentence, "해설": req.translation.strip()},
                                 "이미 Anki에 등록된 문장입니다.")
        if blocked:
            return blocked
        return self._gateway_add("sentence", {"sentence": sentence, "translation": req.translation.strip()})

    def add_vocab_card(self, req: VocabCardRequest) -> AnkiActionResponse:
        """Adds a vocabulary card via the Anki Manager gateway.

        Only word, meaning and POS are sent; the gateway writes example and explanation
        under its own rules. Synonyms are always empty there.
        """
        if not self.check_connection():
            return AnkiActionResponse(success=False, error=TUNNEL_DOWN)
        from app.services.gemini_service import normalize_vocab_placeholders
        word = normalize_vocab_placeholders(req.word.strip())
        if not word:
            return AnkiActionResponse(success=False, error="단어가 비어있습니다.")
        meaning = normalize_meaning(req.meaning)
        blocked = self._precheck(VOCAB_DECK, VOCAB_MODEL, {"단어": word, "뜻": meaning}, "이미 Anki에 등록된 단어입니다.")
        if blocked:
            return blocked
        pos = (req.pos or "").strip().lower()
        return self._gateway_add("vocab", {
            "word": word,
            "meaning": meaning,
            "pos": pos if pos in ALLOWED_POS else "",
            "auto_enrich": True,
            "generate_audio": True,
        })

    def add_grammar_card(self, req: GrammarCardRequest) -> AnkiActionResponse:
        """Grammar multiple-choice card via the gateway: the answer is blanked, my mistake is a wrong option.

        The gateway checks the blank, fills translation/explanation/other options under its rules,
        and refuses cards whose four options are not distinct.
        """
        sentence, answer = req.sentence.strip(), req.answer.strip()
        if not sentence or not answer:
            return AnkiActionResponse(success=False, error="문장과 정답이 모두 필요합니다.")
        blocked = self._precheck(GRAMMAR_DECK, GRAMMAR_MODEL, {"문장": sentence, "정답": answer},
                                 "이미 Anki에 등록된 문법 문장입니다.")
        if blocked:
            return blocked
        mistake = req.mistake.strip()
        return self._gateway_add("grammar", {
            "sentence": sentence,
            "answer": answer,
            "distractors": [mistake] if mistake else [],
        })

    def _reason_when_down(self) -> str:
        """AnkiConnect did not answer: is the tunnel down, or only the server's Anki?"""
        try:
            res = requests.get(f"{settings.ANKI_GATEWAY_URL}/api/cards/status", timeout=5)
            res.raise_for_status()
            return "anki_down" if not res.json().get("anki_connected") else "ok"
        except Exception:
            return "tunnel_down"

    def get_status(self) -> AnkiStatusResponse:
        # deckNames doubles as the connection check: one round trip instead of two.
        try:
            available_decks: List[str] = self.invoke("deckNames") or []
            connected = True
        except Exception:
            available_decks, connected = [], False

        return AnkiStatusResponse(
            connected=connected,
            reason="ok" if connected else self._reason_when_down(),
            anki_url=self.url,
            sentence_deck=SENTENCE_DECK,
            vocab_deck=VOCAB_DECK,
            available_decks=available_decks
        )

    def check_existing_cards(self, sentences: List[str], words: List[str]) -> Dict[str, List[str]]:
        """Which sentences/words are already in Anki, in one AnkiConnect `multi` round trip."""
        from app.services.gemini_service import normalize_vocab_placeholders

        def quote(text: str) -> str:
            return text.replace('"', '\\"')

        lookups = []  # (kind, original, normalized, query)
        for s in sentences:
            clean_s = s.strip()
            if clean_s:
                lookups.append(("s", clean_s, clean_s, f'note:"English Sentence" "문장:{quote(clean_s)}"'))
        for w in words:
            clean_w = w.strip()
            if clean_w:
                norm_w = normalize_vocab_placeholders(clean_w)
                lookups.append(("w", clean_w, norm_w, f'note:"English Vocabulary" "단어:{quote(norm_w)}"'))

        existing: Dict[str, List[str]] = {"existing_sentences": [], "existing_words": []}
        if not lookups:
            return existing
        try:
            results = self.invoke("multi", actions=[
                {"action": "findNotes", "params": {"query": q}} for *_, q in lookups])
        except Exception as e:
            logger.warning(f"Existing-card lookup failed: {e}")
            return existing

        for (kind, original, norm, _), found in zip(lookups, results or []):
            if isinstance(found, dict):  # per-action {"result", "error"} on some AnkiConnect versions
                found = found.get("result")
            if not found:
                continue
            if kind == "s":
                existing["existing_sentences"].append(original)
            else:
                existing["existing_words"].append(original)
                if norm != original:
                    existing["existing_words"].append(norm)
        return existing

anki_service = AnkiService()
