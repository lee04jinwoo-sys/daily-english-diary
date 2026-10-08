import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from app.services.gemini_service import gemini_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dict", tags=["Dictionary"])

class WordLookupRequest(BaseModel):
    word: str = Field(..., description="English word or idiom to lookup")
    context: str = Field(default="", description="Sentence context")

class WordLookupResponse(BaseModel):
    word: str
    phonetic: str = ""
    pos: str = "word"
    meaning: str
    explanation: str = ""
    synonyms: str = ""
    example: str = ""

@router.post("/lookup", response_model=WordLookupResponse)
async def lookup_word(req: WordLookupRequest):
    """
    Instant dictionary lookup for interactive word popover with phonetic, POS, Korean meaning, and explanation.
    """
    if not req.word.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="단어가 비어있습니다.")
    
    try:
        data = await gemini_service.lookup_word(req.word, req.context)
        return WordLookupResponse(**data)
    except Exception as e:
        logger.error(f"Error in word lookup: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"단어 검색 중 오류가 발생했습니다: {str(e)}"
        )
