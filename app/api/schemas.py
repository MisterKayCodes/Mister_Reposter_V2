"""
API: SCHEMAS
Pydantic models for REST requests and responses.
"""
from pydantic import BaseModel
from typing import Optional, List

class PairCreateRequest(BaseModel):
    user_id: int
    source_id: str
    destination_id: str
    interval: Optional[int] = 0
    filter_type: Optional[int] = 1
    replacement: Optional[str] = None
    start_id: Optional[int] = None

class PairUpdateRequest(BaseModel):
    user_id: int
    interval: Optional[int] = None
    filter_type: Optional[int] = None
    replacement: Optional[str] = None

class SessionIngestRequest(BaseModel):
    user_id: int
    session_string: str

class PairResponse(BaseModel):
    id: int
    user_id: int
    source_id: str
    destination_id: str
    is_active: bool
    status: str

class StatsResponse(BaseModel):
    user_id: int
    pairs: List[dict]

class SessionFetchResponse(BaseModel):
    user_id: int
    session_string: str
