"""
API: ROUTES
Core endpoints for programmatic bot control.
"""
from fastapi import APIRouter, Depends, HTTPException
from app.api.schemas import PairCreateRequest, PairUpdateRequest, SessionIngestRequest, StatsResponse, SessionFetchResponse
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

@router.delete("/pair/{pair_id}")
async def delete_pair(user_id: int, pair_id: int):
    success = await repost_service.delete_single_pair(user_id, pair_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pair not found or delete failed")
    return {"status": "deleted"}

@router.patch("/pair/{pair_id}")
async def update_pair(pair_id: int, request: PairUpdateRequest):
    """Live-edit a pair's interval, filter type, or replacement text."""
    success = await repost_service.update_pair(
        user_id=request.user_id,
        pair_id=pair_id,
        interval=request.interval,
        filter_type=request.filter_type,
        replacement=request.replacement
    )
    if not success:
        raise HTTPException(status_code=404, detail="Pair not found or unauthorized")
    return {"status": "updated"}

@router.get("/pairs/all")
async def get_all_pairs():
    """Admin: returns every pair from every user. Used by Mister Telegram control panel."""
    pairs = await repost_service.get_all_pairs()
    return {
        "count": len(pairs),
        "pairs": [
            {
                "id": p.id,
                "user_id": p.user_id,
                "source_id": p.source_id,
                "destination_id": p.destination_id,
                "is_active": p.is_active,
                "status": p.status,
                "filter_type": p.filter_type,
                "replacement_link": p.replacement_link,
                "schedule_interval": p.schedule_interval,
                "total_posts_source": p.total_posts_source,
                "start_from_msg_id": p.start_from_msg_id,
                "error_count": p.error_count,
                "loop_history": p.loop_history,
            }
            for p in pairs
        ]
    }

@router.get("/session/{user_id}", response_model=SessionFetchResponse)
async def get_session(user_id: int):
    """Retrieve the session string for a given user. Protected by API key."""
    async with async_session() as ds:
        user = await UserRepository(ds).get_user(user_id)
    if not user or not user.session_string:
        raise HTTPException(status_code=404, detail="No session found for this user")
    return {"user_id": user_id, "session_string": user.session_string}
