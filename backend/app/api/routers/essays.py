from typing import List
from fastapi import APIRouter, HTTPException, status

from app.schemas.essay import EssayCreateRequest, EssayListResponse, EssayResponse, EssayUpdateRequest
from app.schemas.review import SuggestionItem
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
