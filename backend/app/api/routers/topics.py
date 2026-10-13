import random
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.essay import TopicResponse
from app.services import topic_service
from app.services.essay_service import essay_service

router = APIRouter(prefix="/api/topics", tags=["Topics"])


@router.get("", response_model=List[TopicResponse])
async def list_topics():
    return topic_service.load_topics()


@router.get("/suggest", response_model=TopicResponse)
async def suggest_topic(exclude: Optional[str] = Query(default=None, description="Comma-separated topic ids to skip")):
    """Suggest an unwritten IELTS question: types drawn evenly, not the last essay's type or theme."""
    exclude_ids = {x for x in (exclude or "").split(",") if x}
    last_type, last_topic_id = await essay_service.last_essay_topic()
    topic = topic_service.pick_topic(
        topic_service.load_topics(),
        used_ids=await essay_service.used_topic_ids(),
        exclude_ids=exclude_ids,
        last_type=last_type,
        last_theme=topic_service.theme_of(last_topic_id),
        rng=random.Random(),
    )
    if not topic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="주제 은행이 비어 있습니다.")
    return topic
