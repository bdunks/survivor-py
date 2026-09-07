import subprocess
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from api_models import (
    ConfigResponse,
    EventOddsResponse,
    OptimizationResult,
    PickRequest,
    PickResponse,
)
from config_store import (
    load_config,
    update_algorithm,
    update_current_week,
    update_split_week,
)
from models import Pick
from optimizer import ALGORITHM_DISPATCH
from services import (
    append_pick_event,
    apply_refresh,
    clear_all_pick_events,
    fetch_current_picks,
    fetch_decision_snapshot,
    fetch_events,
    fetch_odds_data,
    find_decision_snapshot,
    find_latest_optimization_run,
    save_optimization_run,
)

app = FastAPI(
    title="NFL Survivor Pool Optimizer",
    description="API for optimizing NFL survivor pool picks using multiple algorithms",
    version="1.0.0",
)


def _get_git_revision() -> tuple[str, str | None]:
    """Get code revision and source hash. Raises ValueError if dirty/unidentified."""
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        dirty = (
            subprocess.run(
                ["git", "diff", "--quiet", "HEAD"],
                timeout=5,
                check=False,
            ).returncode
            != 0
        )
        source_hash = None
        if dirty:
            hash_result = subprocess.run(
                ["git", "diff", "HEAD"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            if hash_result.returncode == 0:
                import hashlib

                source_hash = hashlib.sha256(hash_result.stdout).hexdigest()[:16]
        return rev, source_hash
    except Exception as e:
        raise ValueError(f"Cannot identify source revision: {e}") from e


# NFL teams constant
NFL_TEAMS = [
    "ARI",
    "ATL",
    "BAL",
    "BUF",
    "CAR",
    "CHI",
    "CIN",
    "CLE",
    "DAL",
    "DEN",
    "DET",
    "GB",
    "HOU",
    "IND",
    "JAC",
    "KC",
    "LV",
    "LAC",
    "LAR",
    "MIA",
    "MIN",
    "NE",
    "NO",
    "NYG",
    "NYJ",
    "PHI",
    "PIT",
    "SF",
    "SEA",
    "TB",
    "TEN",
    "WAS",
]


# Configuration Management Endpoints


@app.get("/api/config", response_model=ConfigResponse)
def get_config(year: int = Query(datetime.now().year, ge=2020, le=2030)):  # noqa: DTZ005
    """Get current configuration including week and user picks."""
    config = load_config()
    picks = fetch_current_picks(year)
    return ConfigResponse(
        current_week=config["current_week"],
        user_picks=picks,
        total_picks=len(picks),
        algorithm=config["algorithm"],
        split_week=config["split_week"],
    )


@app.put("/api/config/week/{week}")
def update_week(week: int):
    """Update current week."""
    if not 1 <= week <= 18:
        raise HTTPException(status_code=400, detail="Week must be between 1 and 18")
    try:
        update_current_week(week)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"message": f"Updated current week to {week}", "week": week}


@app.put("/api/config/algorithm")
def update_config_algorithm(algorithm: str):
    """Update algorithm setting."""
    if algorithm not in ALGORITHM_DISPATCH:
        valid_algorithms = ", ".join(ALGORITHM_DISPATCH)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid algorithm: {algorithm}. Must be one of: {valid_algorithms}",
        )
    try:
        update_algorithm(algorithm)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"message": f"Updated algorithm to {algorithm}", "algorithm": algorithm}


@app.put("/api/config/split-week")
def update_config_split_week(split_week: int):
    """Update split week setting."""
    if not 1 <= split_week <= 18:
        raise HTTPException(
            status_code=400, detail="Split week must be between 1 and 18"
        )
    try:
        update_split_week(split_week)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"message": f"Updated split week to {split_week}", "split_week": split_week}


@app.post("/api/config/picks")
def add_pick(pick_request: PickRequest):
    """Add or update a user pick."""
    if pick_request.team.upper() not in NFL_TEAMS:
        raise HTTPException(
            status_code=400, detail=f"Invalid team: {pick_request.team}"
        )
    pick = Pick(
        team=pick_request.team.upper(),
        week=pick_request.week,
        spread=pick_request.spread,
    )

    config = load_config()
    algorithm = config["algorithm"]
    current_week = config["current_week"]

    optimization_run_id = None
    if pick_request.week == current_week:
        run = find_latest_optimization_run(
            pick_request.season_year, current_week, algorithm
        )
        if run is not None:
            recommendations = run["recommendations"]
            current_week_recs = [r for r in recommendations if r.week == current_week]
            if current_week_recs and current_week_recs[0].team == pick.team:
                optimization_run_id = run["run_id"]

    try:
        append_pick_event(
            season_year=pick_request.season_year,
            week=pick_request.week,
            action="set",
            pick=pick,
            recorded_at=datetime.now(UTC),
            optimization_run_id=optimization_run_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {
        "message": f"Added pick for week {pick_request.week}",
        "pick": PickResponse.model_validate(pick, from_attributes=True),
    }


@app.delete("/api/config/picks/{week}")
def clear_week_pick(
    week: int,
    year: int = Query(datetime.now().year, ge=2020, le=2030),  # noqa: DTZ005
):
    """Clear pick for specific week."""
    if not 1 <= week <= 18:
        raise HTTPException(status_code=400, detail="Week must be between 1 and 18")
    try:
        append_pick_event(
            season_year=year,
            week=week,
            action="clear",
            pick=None,
            recorded_at=datetime.now(UTC),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"message": f"Cleared pick for week {week}", "week": week}


@app.delete("/api/config/picks")
def clear_all_picks(
    year: int = Query(datetime.now().year, ge=2020, le=2030),  # noqa: DTZ005
):
    """Clear all user picks."""
    clear_all_pick_events(year, datetime.now(UTC))
    return {"message": "Cleared all picks"}


# Data Operations Endpoints


@app.post("/api/data/refresh")
def refresh_data(year: int = Query(..., ge=2020, le=2030)):
    """Refresh current odds, closing lines, and completed game results."""
    config = load_config()
    current_week = config["current_week"]
    starting_week = max(1, current_week - 1)
    requested_weeks = list(range(starting_week, 19))
    source_urls = [
        f"https://www.cbssports.com/nfl/scoreboard/{year}/regular/{week}/"
        for week in requested_weeks
    ]
    started_at = datetime.now(UTC)
    try:
        events = fetch_events(year, starting_week=starting_week)
    except Exception as error:
        observed_at = datetime.now(UTC)
        apply_refresh(
            year,
            [],
            observed_at,
            status="failed",
            error=str(error),
            requested_weeks=requested_weeks,
            source_urls=source_urls,
            started_at=started_at,
            finished_at=observed_at,
        )
        raise

    finished_at = datetime.now(UTC)
    failed_weeks = list(getattr(events, "failed_weeks", ()))
    successful_weeks = list(
        getattr(
            events,
            "successful_weeks",
            sorted({event.week for event in events} - set(failed_weeks)),
        )
    )
    errors = list(getattr(events, "errors", ()))
    status = (
        "complete"
        if not failed_weeks
        else ("partial" if successful_weeks else "failed")
    )
    result = apply_refresh(
        year,
        events,
        finished_at,
        status=status,
        error="; ".join(errors) or None,
        requested_weeks=requested_weeks,
        successful_weeks=successful_weeks,
        failed_weeks=failed_weeks,
        source_urls=list(getattr(events, "source_urls", source_urls)),
        raw_failures=getattr(events, "raw_failures", ()),
        started_at=started_at,
        finished_at=finished_at,
    )
    result.update(
        {
            "message": f"Refreshed {result['parsed_count']} events for {year}",
            "year": year,
            "events_count": result["parsed_count"],
            "starting_week": starting_week,
        }
    )
    return result


@app.get("/api/data/events", response_model=list[EventOddsResponse])
def get_events(year: int = Query(..., ge=2020, le=2030)):
    """Get all events for specified year."""
    return fetch_odds_data(year)


# Optimization Engine Endpoints


@app.get("/api/optimize/{split_week}/{algorithm}")
def optimize_single_algorithm(
    split_week: int,
    algorithm: str,
    year: int = Query(datetime.now().year, ge=2020, le=2030),  # noqa: DTZ005
):
    """Get optimization results for a single algorithm."""
    if not 1 <= split_week <= 18:
        raise HTTPException(
            status_code=400, detail="Split week must be between 1 and 18"
        )
    if algorithm not in ALGORITHM_DISPATCH:
        raise HTTPException(status_code=400, detail="Invalid algorithm")

    config = load_config()
    current_week = config["current_week"]
    snapshot_id = find_decision_snapshot(year, current_week)

    if snapshot_id is not None:
        events = fetch_decision_snapshot(year, current_week)
    else:
        events = fetch_odds_data(year)

    picks = fetch_current_picks(year)
    algorithm_name, optimize = ALGORITHM_DISPATCH[algorithm]
    results = optimize(events, split_week, picks)

    try:
        code_revision, source_hash = _get_git_revision()
        save_optimization_run(
            season_year=year,
            algorithm=algorithm,
            split_week=split_week,
            current_week=current_week,
            parameters={},
            code_revision=code_revision,
            generated_at=datetime.now(UTC),
            decision_snapshot_id=snapshot_id,
            recommendations=results,
            source_hash=source_hash,
        )
    except ValueError:
        pass

    return OptimizationResult(
        algorithm=algorithm_name,
        picks=results,
        total_spread=sum(pick.spread or 0 for pick in results),
    )


app.mount("/", StaticFiles(directory="static", html=True), name="static")
