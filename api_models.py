from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class PickRequest(BaseModel):
    team: str = Field(..., min_length=2, max_length=3, description="NFL team abbreviation")
    week: int = Field(..., ge=1, le=18, description="NFL week number")
    spread: Optional[float] = Field(None, description="Point spread for the pick")


class PickResponse(BaseModel):
    team: str
    week: int
    spread: Optional[float] = None


class ConfigResponse(BaseModel):
    current_week: int = Field(..., ge=1, le=18)
    user_picks: List[PickResponse]
    total_picks: int
    algorithm: str = Field(default="best-spread", description="Selected optimization algorithm")
    split_week: int = Field(default=10, ge=1, le=18, description="Selected split week")


class EventOddsResponse(BaseModel):
    event_id: int
    season_year: int
    week: int
    short_name: str
    spread: float
    away_team: str
    home_team: str
    favored_team: str


class OptimizationResult(BaseModel):
    algorithm: str
    picks: List[PickResponse]
    total_spread: float


class OptimizationResponse(BaseModel):
    split_week: int
    algorithms: Dict[str, OptimizationResult]


class RefreshRequest(BaseModel):
    year: int = Field(..., ge=2020, le=2030, description="NFL season year")


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    status_code: int


class StatusResponse(BaseModel):
    current_week: int
    total_picks: int
    database_events: int
    last_refresh: Optional[str] = None


class TeamListResponse(BaseModel):
    teams: List[str]


class WeekUpdateRequest(BaseModel):
    week: int = Field(..., ge=1, le=18, description="New current week")


class ExportResponse(BaseModel):
    filename: str
    download_url: str