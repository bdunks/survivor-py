from pydantic import BaseModel, ConfigDict, Field


class PickRequest(BaseModel):
    team: str = Field(
        ..., min_length=2, max_length=3, description="NFL team abbreviation"
    )
    week: int = Field(..., ge=1, le=18, description="NFL week number")
    spread: float | None = Field(None, description="Point spread for the pick")
    season_year: int = Field(..., ge=2020, le=2030, description="Season year")


class PickResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team: str
    week: int
    spread: float | None = None


class ConfigResponse(BaseModel):
    current_week: int = Field(..., ge=1, le=18)
    user_picks: list[PickResponse]
    total_picks: int
    algorithm: str = Field(
        default="best-spread", description="Selected optimization algorithm"
    )
    split_week: int = Field(default=10, ge=1, le=18, description="Selected split week")


class EventOddsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    picks: list[PickResponse]
    total_spread: float
