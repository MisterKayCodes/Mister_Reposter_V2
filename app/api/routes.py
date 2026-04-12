"""
API: ROUTES
Core endpoints for programmatic bot control.
"""
from fastapi import APIRouter, Depends, HTTPException
from app.api.schemas import PairCreateRequest, SessionIngestRequest, StatsResponse
from app.api.security import get_api_key
from app.services.singleton import repost_service
from app.data.database import async_session
from app.data.repository import UserRepository

router = APIRouter(dependencies=[Depends(get_api_key)])

@router.get("/health")
async def health_check():
    return {"status": "Mister Reposter is operational", "engine": "alive"}

@router.get("/stats/{user_id}", response_model=StatsResponse)
async def get_stats(user_id: int):
    pairs = await repost_service.get_user_pairs(user_id)
    stats_list = []
    for p in pairs:
        s = await repost_service.get_effective_stats(user_id, p.id)
        stats_list.append(s)
    return {"user_id": user_id, "pairs": stats_list}

@router.post("/pair")
async def create_pair(request: PairCreateRequest):
    try:
        await repost_service.add_new_pair(
            user_id=request.user_id,
            source=request.source_id,
            destination=request.destination_id,
            schedule_interval=request.interval,
            filter_type=request.filter_type,
            replacement_link=request.replacement,
            start_from_msg_id=request.start_id
        )
        return {"status": "success", "message": "Pair created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/session")
async def ingest_session(request: SessionIngestRequest):
    async with async_session() as ds:
        repo = UserRepository(ds)
        await repo.create_or_update_user(request.user_id, f"API_User_{request.user_id}")
        await repo.update_session_string(request.user_id, request.session_string)
    
    # Trigger recovery to start listener
    await repost_service.recover_all_listeners()
    return {"status": "success", "message": "Session ingested and engine resumed"}

@router.post("/pair/{pair_id}/toggle")
async def toggle_pair(user_id: int, pair_id: int):
    pairs = await repost_service.get_user_pairs(user_id)
    target = next((p for p in pairs if p.id == pair_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Pair not found")
    
    if target.is_active:
        await repost_service.deactivate_pair(user_id, pair_id)
        return {"status": "paused"}
    else:
        await repost_service.activate_pair(user_id, pair_id)
        return {"status": "activated"}
