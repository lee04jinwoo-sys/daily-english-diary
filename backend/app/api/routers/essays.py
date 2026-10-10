from typing import List
from fastapi import APIRouter, HTTPException, status

from app.schemas.essay import EssayCreateRequest, EssayListResponse, EssayResponse, EssayUpdateRequest
from app.schemas.review import SentencePair, SuggestionItem
from app.services.gemini_service import GeminiError, gemini_service
from app.services.essay_service import essay_service

router = APIRouter(prefix="/api/essays", tags=["Essays"])


def _not_found(essay_id: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"에세이({essay_id})를 찾을 수 없습니다.")


@router.get("", response_model=EssayListResponse)
async def list_essays():
    return await essay_service.list()


@router.post("", response_model=EssayResponse)
async def create_essay(req: EssayCreateRequest):
    return await essay_service.create(req)


@router.get("/{essay_id}", response_model=EssayResponse)
async def get_essay(essay_id: str):
    essay = await essay_service.get(essay_id)
    if not essay:
        raise _not_found(essay_id)
    return essay


@router.patch("/{essay_id}", response_model=EssayResponse)
async def update_essay(essay_id: str, req: EssayUpdateRequest):
    essay = await essay_service.update(essay_id, req)
    if not essay:
        raise _not_found(essay_id)
    return essay


@router.post("/{essay_id}/revise", response_model=EssayResponse)
async def revise_essay(essay_id: str):
    essay = await essay_service.revise(essay_id)
    if not essay:
        raise _not_found(essay_id)
    return essay


@router.patch("/{essay_id}/toggle-complete", response_model=EssayResponse)
async def toggle_complete(essay_id: str):
    essay = await essay_service.toggle_complete(essay_id)
    if not essay:
        raise _not_found(essay_id)
    return essay


@router.delete("/{essay_id}")
async def delete_essay(essay_id: str):
    if not await essay_service.delete(essay_id):
        raise _not_found(essay_id)
    return {"success": True}


@router.get("/{essay_id}/suggestions", response_model=List[SuggestionItem])
async def get_suggestions(essay_id: str):
    return await essay_service.get_suggestions(essay_id)


@router.post("/{essay_id}/sentence-pairs", response_model=List[SentencePair])
async def sentence_pairs(essay_id: str):
    """Sentence-by-sentence study pairs, generated on first request and stored with the review."""
    essay = await essay_service.get(essay_id)
    if not essay:
        raise _not_found(essay_id)
    if not essay.review:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="먼저 AI 첨삭을 받아야 합니다.")
    if essay.review.sentence_pairs:
        return essay.review.sentence_pairs
    try:
        pairs = await gemini_service.generate_sentence_pairs(essay.review)
    except GeminiError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"문장별 대조 생성에 실패했습니다: {e}")
    essay.review.sentence_pairs = pairs
    await essay_service.save_sentence_pairs(essay_id, essay.review)
    return pairs
