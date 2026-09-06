import csv
import os
import tempfile
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api_models import (
    ConfigResponse,
    EventOddsResponse,
    OptimizationResponse,
    OptimizationResult,
    PickRequest,
    PickResponse,
    StatusResponse,
    TeamListResponse,
)
from main import (
    add_pick_to_config,
    clear_pick_from_config,
    load_config,
    update_algorithm,
    update_current_week,
    update_split_week,
)
from models import EventOdds, Pick
from optimizer import PickOptimizer
from services import CBSSportsService, DatabaseService

app = FastAPI(
    title="NFL Survivor Pool Optimizer",
    description="API for optimizing NFL survivor pool picks using multiple algorithms",
    version="1.0.0",
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


def pick_to_response(pick: Pick) -> PickResponse:
    """Convert Pick model to PickResponse"""
    return PickResponse(team=pick.team, week=pick.week, spread=pick.spread)


def event_to_response(event: EventOdds) -> EventOddsResponse:
    """Convert EventOdds model to EventOddsResponse"""
    return EventOddsResponse(
        event_id=event.event_id,
        season_year=event.season_year,
        week=event.week,
        short_name=event.short_name,
        spread=event.spread,
        away_team=event.away_team,
        home_team=event.home_team,
        favored_team=event.favored_team,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500, content={"error": "Internal server error", "detail": str(exc)}
    )


# Configuration Management Endpoints


@app.get("/api/config", response_model=ConfigResponse)
async def get_config():
    """Get current configuration including week and user picks"""
    try:
        config = load_config()
        return ConfigResponse(
            current_week=config["current_week"],
            user_picks=[pick_to_response(pick) for pick in config["user_picks"]],
            total_picks=len(config["user_picks"]),
            algorithm=config["algorithm"],
            split_week=config["split_week"],
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/config/week/{week}")
async def update_week(week: int):
    """Update current week"""
    try:
        if not (1 <= week <= 18):
            raise HTTPException(status_code=400, detail="Week must be between 1 and 18")

        update_current_week(week)
        return {"message": f"Updated current week to {week}", "week": week}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/config/algorithm")
async def update_config_algorithm(algorithm: str):
    """Update algorithm setting"""
    try:
        valid_algorithms = ["best-spread", "weighted-future-value", "back-to-front"]
        if algorithm not in valid_algorithms:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid algorithm: {algorithm}. Must be one of: {', '.join(valid_algorithms)}",
            )

        update_algorithm(algorithm)
        return {"message": f"Updated algorithm to {algorithm}", "algorithm": algorithm}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/config/split-week")
async def update_config_split_week(split_week: int):
    """Update split week setting"""
    try:
        if not (1 <= split_week <= 18):
            raise HTTPException(
                status_code=400, detail="Split week must be between 1 and 18"
            )

        update_split_week(split_week)
        return {
            "message": f"Updated split week to {split_week}",
            "split_week": split_week,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config/picks")
async def add_pick(pick_request: PickRequest):
    """Add or update a user pick"""
    try:
        # Validate team
        if pick_request.team.upper() not in NFL_TEAMS:
            raise HTTPException(
                status_code=400, detail=f"Invalid team: {pick_request.team}"
            )

        # Format the pick string for the existing function
        spread = pick_request.spread or 0.0
        pick_string = f"{pick_request.team.upper()}:{pick_request.week}:{spread}"

        add_pick_to_config(pick_string)

        return {
            "message": f"Added pick for week {pick_request.week}",
            "pick": pick_to_response(
                Pick(
                    team=pick_request.team.upper(),
                    week=pick_request.week,
                    spread=pick_request.spread,
                )
            ),
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/config/picks/{week}")
async def clear_week_pick(week: int):
    """Clear pick for specific week"""
    try:
        if not (1 <= week <= 18):
            raise HTTPException(status_code=400, detail="Week must be between 1 and 18")

        clear_pick_from_config(str(week))
        return {"message": f"Cleared pick for week {week}", "week": week}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/config/picks")
async def clear_all_picks():
    """Clear all user picks"""
    try:
        clear_pick_from_config("all")
        return {"message": "Cleared all picks"}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


# Data Operations Endpoints


@app.post("/api/data/refresh")
async def refresh_data(year: int = Query(..., ge=2020, le=2030)):
    """Refresh odds data from CBS Sports"""
    try:
        config = load_config()
        current_week = config["current_week"]

        odds_service = CBSSportsService()
        events = odds_service.fetch_events(year, starting_week=current_week)

        db_service = DatabaseService()
        db_service.save_odds_data(events)
        db_service.close()

        return {
            "message": f"Refreshed {len(events)} events for {year}",
            "year": year,
            "events_count": len(events),
            "starting_week": current_week,
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data/events", response_model=list[EventOddsResponse])
async def get_events(year: int = Query(..., ge=2020, le=2030)):
    """Get all events for specified year"""
    try:
        db_service = DatabaseService()
        events = db_service.fetch_odds_data(year)
        db_service.close()

        return [event_to_response(event) for event in events]
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/teams", response_model=TeamListResponse)
async def get_teams():
    """Get list of NFL teams"""
    return TeamListResponse(teams=NFL_TEAMS)


# Optimization Engine Endpoints


@app.get("/api/optimize/{split_week}", response_model=OptimizationResponse)
async def optimize_picks(
    split_week: int,
    year: int = Query(datetime.now().year, ge=2020, le=2030),  # noqa: DTZ005
):
    """Get optimization results for all algorithms at specified split week"""
    try:
        if not (1 <= split_week <= 18):
            raise HTTPException(
                status_code=400, detail="Split week must be between 1 and 18"
            )

        # Load configuration and events
        config = load_config()
        user_picks = config["user_picks"]

        db_service = DatabaseService()
        events = db_service.fetch_odds_data(year)
        db_service.close()

        if not events:
            raise HTTPException(
                status_code=404, detail=f"No events found for year {year}"
            )

        # Initialize optimizer
        optimizer = PickOptimizer()

        # Run all algorithms
        algorithms = {}

        # Best Spread
        picks_best_spread = optimizer.find_optimal_picks_best_spread(
            events, split_week, user_picks
        )
        algorithms["bestSpread"] = OptimizationResult(
            algorithm="Best Spread",
            picks=[pick_to_response(pick) for pick in picks_best_spread],
            total_spread=sum(pick.spread or 0 for pick in picks_best_spread),
        )

        # Back to Front
        picks_back_to_front = optimizer.find_optimal_picks_back_to_front(
            events, split_week, user_picks
        )
        algorithms["backToFront"] = OptimizationResult(
            algorithm="Back to Front",
            picks=[pick_to_response(pick) for pick in picks_back_to_front],
            total_spread=sum(pick.spread or 0 for pick in picks_back_to_front),
        )

        # Weighted Future Value
        picks_weighted = optimizer.find_optimal_picks_weighted_future_value(
            events, split_week, user_picks
        )
        algorithms["futureValue"] = OptimizationResult(
            algorithm="Weighted Future Value",
            picks=[pick_to_response(pick) for pick in picks_weighted],
            total_spread=sum(pick.spread or 0 for pick in picks_weighted),
        )

        return OptimizationResponse(split_week=split_week, algorithms=algorithms)

    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/optimize/{split_week}/{algorithm}")
async def optimize_single_algorithm(
    split_week: int,
    algorithm: str,
    year: int = Query(datetime.now().year, ge=2020, le=2030),  # noqa: DTZ005
):
    """Get optimization results for single algorithm"""
    try:
        if not (1 <= split_week <= 18):
            raise HTTPException(
                status_code=400, detail="Split week must be between 1 and 18"
            )

        if algorithm not in ["best-spread", "back-to-front", "weighted-future-value"]:
            raise HTTPException(status_code=400, detail="Invalid algorithm")

        config = load_config()
        user_picks = config["user_picks"]

        db_service = DatabaseService()
        events = db_service.fetch_odds_data(year)
        db_service.close()

        optimizer = PickOptimizer()

        if algorithm == "best-spread":
            picks = optimizer.find_optimal_picks_best_spread(
                events, split_week, user_picks
            )
            algo_name = "Best Spread"
        elif algorithm == "back-to-front":
            picks = optimizer.find_optimal_picks_back_to_front(
                events, split_week, user_picks
            )
            algo_name = "Back to Front"
        else:  # weighted-future-value
            picks = optimizer.find_optimal_picks_weighted_future_value(
                events, split_week, user_picks
            )
            algo_name = "Weighted Future Value"

        return OptimizationResult(
            algorithm=algo_name,
            picks=[pick_to_response(pick) for pick in picks],
            total_spread=sum(pick.spread or 0 for pick in picks),
        )

    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


# Export & Status Endpoints


@app.get("/api/export/csv")
async def export_csv(
    split_week: int = Query(..., ge=1, le=18),
    algorithm: str = Query(
        "all", regex="^(all|best-spread|back-to-front|weighted-future-value)$"
    ),
    year: int = Query(datetime.now().year, ge=2020, le=2030),  # noqa: DTZ005
):
    """Export picks to CSV file"""
    try:
        config = load_config()
        user_picks = config["user_picks"]

        db_service = DatabaseService()
        events = db_service.fetch_odds_data(year)
        db_service.close()

        optimizer = PickOptimizer()

        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv")  # noqa: SIM115
        writer = csv.writer(temp_file)

        # Write header
        header = (
            ["Algorithm", "Split Week"]
            + [f"Week {i:02}" for i in range(1, 19)]
            + ["Total Spread"]
        )
        writer.writerow(header)

        algorithms_to_export = []
        if algorithm == "all":
            algorithms_to_export = [
                ("best-spread", "Best Spread"),
                ("back-to-front", "Back to Front"),
                ("weighted-future-value", "Weighted Future Value"),
            ]
        else:
            algo_map = {
                "best-spread": "Best Spread",
                "back-to-front": "Back to Front",
                "weighted-future-value": "Weighted Future Value",
            }
            algorithms_to_export = [(algorithm, algo_map[algorithm])]

        for algo_key, algo_name in algorithms_to_export:
            if algo_key == "best-spread":
                picks = optimizer.find_optimal_picks_best_spread(
                    events, split_week, user_picks
                )
            elif algo_key == "back-to-front":
                picks = optimizer.find_optimal_picks_back_to_front(
                    events, split_week, user_picks
                )
            else:
                picks = optimizer.find_optimal_picks_weighted_future_value(
                    events, split_week, user_picks
                )

            # Create row
            row = [algo_name, split_week]
            total_spread = 0

            for week in range(1, 19):
                pick = next((p for p in picks if p.week == week), None)
                if pick:
                    row.append(f"{pick.team} ({pick.spread:.1f})")
                    total_spread += pick.spread or 0
                else:
                    row.append("N/A")

            row.append(f"{total_spread:.1f}")
            writer.writerow(row)

        temp_file.close()

        filename = f"survivor_picks_{year}_week{split_week}_{algorithm}.csv"

        return FileResponse(
            path=temp_file.name, filename=filename, media_type="text/csv"
        )

    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Get system status"""
    try:
        config = load_config()

        # Get database event count
        db_service = DatabaseService()
        events = db_service.fetch_odds_data(datetime.now().year)  # noqa: DTZ005
        db_service.close()

        return StatusResponse(
            current_week=config["current_week"],
            total_picks=len(config["user_picks"]),
            database_events=len(events),
            last_refresh=None,  # Could be implemented with a timestamp file
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


# Mount static files (will be created in next step)
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
