import requests
import subprocess
import io
import os
import re
import html
import random
import base64
import uuid
import logging
from typing import Optional, Dict, Any, List
import gtts
from google.cloud import texttospeech
from app.core.config import settings
from app.schemas.anki import AnkiStatusResponse, AnkiActionResponse, SentenceCardRequest, VocabCardRequest

logger = logging.getLogger(__name__)

# Anki Manager compatible Chirp3-HD Voice List (10 High-Definition Neural Voices)
VOICE_LIST = [
    "en-US-Chirp3-HD-Vindemiatrix",
    "en-US-Chirp3-HD-Achernar",
    "en-US-Chirp3-HD-Schedar",
    "en-US-Chirp3-HD-Alnilam",
    "en-US-Chirp3-HD-Algenib",
    "en-US-Chirp3-HD-Autonoe",
    "en-GB-Chirp3-HD-Aoede",
    "en-GB-Chirp3-HD-Umbriel",
    "en-AU-Chirp3-HD-Kore",
    "en-AU-Chirp3-HD-Enceladus"
]

def clean_text_for_tts(text: str) -> str:
    """Removes HTML tags and normalizes quotes for clean TTS pronunciation."""
    if not text:
        return ""
    text = html.unescape(text)
    text = text.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
    return re.sub(r'<.*?>', '', text).strip()

class AnkiService:
    def __init__(self):
        self.url = settings.ANKI_URL
        self._tts_client: Optional[texttospeech.TextToSpeechClient] = None

    @property
    def tts_client(self) -> Optional[texttospeech.TextToSpeechClient]:
        if self._tts_client is None:
            try:
                self._tts_client = texttospeech.TextToSpeechClient()
            except Exception as e:
                logger.warning(f"GCP TextToSpeechClient initialization failed (will fallback to gTTS): {e}")
                self._tts_client = None
        return self._tts_client

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
            raise ConnectionError(f"AnkiConnect에 연결할 수 없습니다 ({self.url}). Anki가 실행 중인지 확인하세요.")
        except Exception as e:
            raise RuntimeError(f"AnkiConnect 호출 오류 ({action}): {str(e)}")

    def check_connection(self) -> bool:
        try:
            res = self.invoke("version")
            return res is not None
        except Exception:
            return False

    def generate_gcp_tts(self, text: str) -> str:
        """
        Generates ultra-high-fidelity Chirp3-HD native voice audio using Google Cloud TTS.
        Picks randomly from US, GB, AU native speakers with 1.1x natural speaking rate.
        """
        clean = clean_text_for_tts(text)
        if not clean or not self.tts_client:
            return ""

        try:
            selected_voice = random.choice(VOICE_LIST)
            lang_code = "-".join(selected_voice.split("-")[:2])
            synthesis_input = texttospeech.SynthesisInput(text=clean)
            voice = texttospeech.VoiceSelectionParams(
                language_code=lang_code,
                name=selected_voice
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.1
            )

            res = self.tts_client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )

            filename = f"anki_gcp_{selected_voice}_{uuid.uuid4().hex[:8]}.mp3"
            b64_audio = base64.b64encode(res.audio_content).decode("utf-8")
            self.invoke("storeMediaFile", filename=filename, data=b64_audio)
            logger.info(f"Generated Chirp3-HD audio ({selected_voice}): {filename}")
            return f"[sound:{filename}]"

        except Exception as e:
            logger.warning(f"GCP Chirp3-HD TTS failed, falling back to gTTS: {e}")
            return ""

    def generate_and_store_gtts(self, text: str) -> str:
        """Generates gTTS MP3 audio (for vocab or fallback), stores it into Anki via storeMediaFile."""
        clean = clean_text_for_tts(text)
        if not clean:
            return ""
        try:
            tts = gtts.gTTS(clean, lang="en", tld="com")
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            buf.seek(0)
            b64_audio = base64.b64encode(buf.read()).decode("utf-8")
            fname = f"anki_gtts_{uuid.uuid4().hex[:8]}.mp3"
            self.invoke("storeMediaFile", filename=fname, data=b64_audio)
            return f"[sound:{fname}]"
        except Exception as e:
            logger.warning(f"gTTS audio generation warning for '{text}': {e}")
            return ""

    def generate_sentence_audio(self, text: str) -> str:
        """Tries Google Cloud Chirp3-HD first; falls back to gTTS if GCP is unavailable."""
        sound_tag = self.generate_gcp_tts(text)
        if not sound_tag:
            sound_tag = self.generate_and_store_gtts(text)
        return sound_tag

    def add_sentence_card(self, req: SentenceCardRequest) -> AnkiActionResponse:
        """Adds a sentence card to Anki with Chirp3-HD high-fidelity audio (Anki Manager format)."""
        if not self.check_connection():
            return AnkiActionResponse(success=False, error="Anki가 실행되어 있지 않습니다. Anki 앱을 켜주세요.")

        clean_sentence = req.sentence.strip()
        if not clean_sentence:
            return AnkiActionResponse(success=False, error="문장이 비어있습니다.")

        # Generate Chirp3-HD (or fallback to gTTS)
        sound_tag = self.generate_sentence_audio(clean_sentence)

        fields = {
            "문장": clean_sentence,
            "해설": req.translation.strip(),
            "소리": sound_tag
        }

        # Check actual model fields in Anki
        try:
            actual_fields = self.invoke("modelFieldNames", modelName=req.model_name) or []
            if actual_fields and "해설" not in actual_fields:
                if len(actual_fields) >= 2:
                    fields = {actual_fields[0]: clean_sentence, actual_fields[1]: req.translation.strip()}
                    if len(actual_fields) >= 3:
                        fields[actual_fields[2]] = sound_tag
        except Exception:
            pass

        note = {
            "deckName": req.deck_name,
            "modelName": req.model_name,
            "fields": fields,
            "tags": ["daily-english-diary"],
            "options": {"allowDuplicate": False}
        }

        try:
            note_id = self.invoke("addNote", note=note)
            return AnkiActionResponse(success=True, note_id=note_id, message="Anki 문장 카드가 등록되었습니다!")
        except Exception as e:
            err_msg = str(e)
            if "duplicate" in err_msg.lower():
                return AnkiActionResponse(success=True, duplicate=True, message="이미 Anki에 등록된 문장입니다.")
            return AnkiActionResponse(success=False, error=f"카드 추가 오류: {err_msg}")

    async def add_vocab_card(self, req: VocabCardRequest) -> AnkiActionResponse:
        """Adds a vocabulary card to Anki (Anki Manager format with gTTS). Auto-enriches with 3-step formula if missing."""
        if not self.check_connection():
            return AnkiActionResponse(success=False, error="Anki가 실행되어 있지 않습니다. Anki 앱을 켜주세요.")

        from app.services.gemini_service import normalize_vocab_placeholders, clean_vocab_example, gemini_service

        clean_word = normalize_vocab_placeholders(req.word.strip())
        if not clean_word:
            return AnkiActionResponse(success=False, error="단어가 비어있습니다.")

        meaning = req.meaning.strip()
        pos = req.pos.strip()
        synonyms = req.synonyms.strip()
        example = clean_vocab_example(req.example.strip())
        explanation = req.explanation.strip()

        # If explanation does not have the 3-step formula or is too short, enrich it using Gemini!
        if not explanation or len(explanation) < 30 or not synonyms:
            try:
                enriched = await gemini_service.lookup_word(clean_word, example or meaning)
                if enriched:
                    clean_word = enriched.get("word") or clean_word
                    meaning = meaning or enriched.get("meaning", "")
                    pos = pos or enriched.get("pos", "idiom")
                    synonyms = synonyms or enriched.get("synonyms", "")
                    explanation = enriched.get("explanation") or explanation
                    if not example:
                        example = clean_vocab_example(enriched.get("example", ""))
            except Exception as e:
                logger.warning(f"Vocab auto-enrichment warning: {e}")

        sound_tag = self.generate_and_store_gtts(clean_word)

        fields = {
            "단어": clean_word,
            "뜻": meaning,
            "품사": pos or "idiom",
            "유의어": synonyms,
            "예문": example,
            "설명": explanation,
            "소리": sound_tag
        }

        note = {
            "deckName": req.deck_name,
            "modelName": req.model_name,
            "fields": fields,
            "tags": ["daily-english-diary", "vocab"],
            "options": {"allowDuplicate": False}
        }

        try:
            note_id = self.invoke("addNote", note=note)
            return AnkiActionResponse(success=True, note_id=note_id, message="Anki 단어 카드가 등록되었습니다!")
        except Exception as e:
            err_msg = str(e)
            if "duplicate" in err_msg.lower():
                return AnkiActionResponse(success=True, duplicate=True, message="이미 Anki에 등록된 단어입니다.")
            return AnkiActionResponse(success=False, error=f"단어 카드 추가 오류: {err_msg}")

    def get_status(self) -> AnkiStatusResponse:
        connected = self.check_connection()
        available_decks: List[str] = []
        if connected:
            try:
                available_decks = self.invoke("deckNames") or []
            except Exception:
                pass

        return AnkiStatusResponse(
            connected=connected,
            anki_url=self.url,
            sentence_deck=settings.DEFAULT_ANKI_SENTENCE_DECK,
            vocab_deck=settings.DEFAULT_ANKI_VOCAB_DECK,
            available_decks=available_decks
        )

    def check_existing_cards(self, sentences: List[str], words: List[str]) -> Dict[str, List[str]]:
        """Fast lookup checking if sentences or words are already in Anki."""
        existing_sentences: List[str] = []
        existing_words: List[str] = []
        if not self.check_connection():
            return {"existing_sentences": [], "existing_words": []}

        for s in sentences:
            clean_s = s.strip()
            if not clean_s:
                continue
            escaped = clean_s.replace('"', '\\"')
            try:
                res = self.invoke("findNotes", query=f'note:"English Sentence" "문장:{escaped}"')
                if res and len(res) > 0:
                    existing_sentences.append(clean_s)
            except Exception:
                pass

        for w in words:
            clean_w = w.strip()
            if not clean_w:
                continue
            from app.services.gemini_service import normalize_vocab_placeholders
            norm_w = normalize_vocab_placeholders(clean_w)
            escaped = norm_w.replace('"', '\\"')
            try:
                res = self.invoke("findNotes", query=f'note:"English Vocabulary" "단어:{escaped}"')
                if res and len(res) > 0:
                    existing_words.append(clean_w)
                    if norm_w != clean_w:
                        existing_words.append(norm_w)
            except Exception:
                pass

        return {
            "existing_sentences": existing_sentences,
            "existing_words": existing_words
        }

    def launch_anki(self) -> bool:
        """Opens the Anki desktop app (macOS)."""
        try:
            result = subprocess.run(["open", "-a", "Anki"], capture_output=True, timeout=10)
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"Failed to launch Anki: {e}")
            return False

anki_service = AnkiService()
