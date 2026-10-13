import logging
from fastapi import APIRouter, HTTPException, status
from starlette.concurrency import run_in_threadpool
from app.schemas.anki import (
    AnkiStatusResponse,
    AnkiActionResponse,
    GrammarCardRequest,
    SentenceCardRequest,
    VocabCardRequest,
    CardPreviewRequest,
    CardPreviewResponse,
    CheckExistingCardsRequest,
    CheckExistingCardsResponse,
)
from app.services.anki_service import anki_service
from app.services.gemini_service import gemini_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/anki", tags=["Anki"])

# Anki calls are blocking HTTP round trips through the SSH tunnel (~0.6 s each). They run in
# the threadpool so opening or switching essays never waits behind them.

@router.post("/check-existing", response_model=CheckExistingCardsResponse)
async def check_existing_cards(req: CheckExistingCardsRequest):
    """Fast batch check if sentences or words exist in Anki."""
    return await run_in_threadpool(anki_service.check_existing_cards, req.sentences, req.words)

@router.get("/status", response_model=AnkiStatusResponse)
async def get_anki_status():
    """Checks if Anki is connected and retrieves available decks."""
    return await run_in_threadpool(anki_service.get_status)

@router.post("/preview", response_model=CardPreviewResponse)
async def preview_card(req: CardPreviewRequest):
    """Enriches a sentence or vocab with AI to preview in the card creation modal."""
    return await gemini_service.generate_anki_card_preview(
        card_type=req.card_type,
        text=req.text,
        context=req.context or ""
    )

@router.post("/add-sentence", response_model=AnkiActionResponse)
async def add_sentence_card(req: SentenceCardRequest):
    """Adds a sentence card to Anki with gTTS audio."""
    res = await run_in_threadpool(anki_service.add_sentence_card, req)
    if not res.success and not res.duplicate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.error or "Anki 문장 카드 등록에 실패했습니다."
        )
    return res

@router.post("/add-vocab", response_model=AnkiActionResponse)
async def add_vocab_card(req: VocabCardRequest):
    """Adds a vocabulary card to Anki with gTTS audio."""
    res = await run_in_threadpool(anki_service.add_vocab_card, req)
    if not res.success and not res.duplicate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.error or "Anki 단어 카드 등록에 실패했습니다."
        )
    return res


@router.post("/add-grammar", response_model=AnkiActionResponse)
async def add_grammar_card(req: GrammarCardRequest):
    """Adds a grammar multiple-choice card (blanked answer, my mistake as a wrong option)."""
    res = await run_in_threadpool(anki_service.add_grammar_card, req)
    if not res.success and not res.duplicate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.error or "Anki 문법 카드 등록에 실패했습니다."
        )
    return res
