import logging
from fastapi import APIRouter, HTTPException, Path, status
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
    UndoCardRequest,
    SimilarSentencesRequest,
    SimilarSentencesResponse,
    GrammarRegisteredResponse,
    PrepareGrammarCardsRequest,
    PrepareGrammarCardsResponse,
)
from app.services.anki_service import anki_service
from app.services.gemini_service import GeminiError, gemini_service

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


@router.post("/undo-card", response_model=AnkiActionResponse)
async def undo_card(req: UndoCardRequest):
    """Deletes a card this app just created (app tag, never studied); refuses anything else."""
    res = await run_in_threadpool(anki_service.undo_card, req.note_id)
    if not res.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.error or "Anki 카드 취소에 실패했습니다."
        )
    return res


@router.post("/similar-sentences", response_model=SimilarSentencesResponse)
async def similar_sentences(req: SimilarSentencesRequest):
    """New example sentences for grammar fixes that share a sentence with another fix (see GeminiService)."""
    try:
        sentences = await gemini_service.generate_similar_sentences([i.model_dump() for i in req.items])
    except GeminiError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"유사 문장 생성에 실패했습니다: {e}")
    return SimilarSentencesResponse(sentences=sentences)


@router.get("/grammar-registered/{essay_id}", response_model=GrammarRegisteredResponse)
async def grammar_registered(essay_id: str = Path(pattern=r"^[A-Za-z0-9_-]{1,64}$")):
    """Which corrections of this essay already have a grammar card (read from the tags in Anki)."""
    return GrammarRegisteredResponse(fix_ids=await run_in_threadpool(anki_service.grammar_registered, essay_id))


@router.post("/prepare-grammar-cards", response_model=PrepareGrammarCardsResponse)
async def prepare_grammar_cards(req: PrepareGrammarCardsRequest):
    """Fix and translate grammar-card sentences right before they are added, and check both (Sonnet)."""
    try:
        return await gemini_service.prepare_grammar_cards([i.model_dump() for i in req.items])
    except GeminiError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"카드 문장 검사에 실패했습니다: {e}")
