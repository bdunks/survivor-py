"""Sequential backtest runner for survivor pool algorithms.

Evaluates algorithm performance using historical point-in-time decision snapshots
without future leakage.
"""

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from models import Pick
from optimizer import ALGORITHM_DISPATCH
from services.sqlite import (
    DEFAULT_DB_NAME,
    fetch_closing_line,
    fetch_game_result,
    fetch_snapshot_events,
    find_decision_snapshot,
)


def _get_git_revision() -> str:
    """Get current git revision or explicit unidentified marker."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        return result.stdout.strip()
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return "unidentified"


def _fetch_closing_line(event_id: int, db_name: str | Path = DEFAULT_DB_NAME) -> dict:
    """Fetch closing line for an event."""
    return fetch_closing_line(event_id, db_name) or {}


@dataclass
class WeeklyResult:
    season: int
    week: int
    decision_at: str
    snapshot_id: int
    algorithm: str
    source_revision: str
    parameters: dict
    split_week: int
    selected_team: str
    opponent: str
    decision_spread: float
    closing_spread: float | None
    home_score: int | None
    away_score: int | None
    scoring_margin: float | None
    outcome: str
    previously_used: list[str]
    counterfactual: bool


@dataclass
class AggregateResult:
    algorithm: str
    season: int
    parameters: dict
    split_week: int
    first_elimination_week: int | None
    wins: int
    losses: int
    ties: int
    ungraded: int
    weeks_survived: int
    avg_decision_spread: float
    avg_closing_spread: float
    avg_decision_to_closing: float
    avg_selected_vs_best_alternative: float


def run_backtest(
    db_name: str | Path,
    season: int,
    algorithm: str,
    split_week: int,
    mode: str = "strict",
) -> tuple[list[WeeklyResult], AggregateResult]:
    """Run backtest for one algorithm across a season."""
    if algorithm not in ALGORITHM_DISPATCH:
        raise ValueError(f"Unknown algorithm: {algorithm}")
    if mode not in ("strict", "degraded"):
        raise ValueError(f"Unknown mode: {mode}")

    _, optimizer_fn = ALGORITHM_DISPATCH[algorithm]
    weekly_results = []
    prior_picks = []
    wins = losses = ties = ungraded = 0
    decision_spreads = []
    closing_spreads = []
    decision_to_closing = []
    selected_vs_best = []
    first_elimination = None
    source_revision = _get_git_revision()
    parameters = {"algorithm": algorithm, "split_week": split_week}

    for week in range(1, 19):
        snapshot_id = find_decision_snapshot(season, week, db_name)
        if snapshot_id is None:
            if mode == "strict":
                raise ValueError(f"Missing snapshot for {season} week {week}")
            continue

        snapshot_events = fetch_snapshot_events(snapshot_id, db_name)
        if not snapshot_events:
            if mode == "strict":
                raise ValueError(f"Empty snapshot for {season} week {week}")
            continue

        # Run optimizer with locked prior picks
        recommendations = optimizer_fn(snapshot_events, split_week, prior_picks)

        # Find current week recommendation
        current_pick = next((p for p in recommendations if p.week == week), None)
        if current_pick is None:
            if mode == "strict":
                raise ValueError(f"No recommendation for week {week}")
            continue

        selected_team = current_pick.team

        # Find event for grading
        selected_event = next(
            (e for e in snapshot_events if selected_team in (e.home_team, e.away_team)),
            None,
        )
        if not selected_event:
            raise ValueError(f"No event for {selected_team} in week {week}")

        opponent = (
            selected_event.away_team
            if selected_team == selected_event.home_team
            else selected_event.home_team
        )
        decision_spread = (
            current_pick.spread
            if current_pick.spread is not None
            else selected_event.spread
        )

        # Fetch closing line and result
        closing = _fetch_closing_line(selected_event.event_id, db_name)
        result = fetch_game_result(selected_event.event_id, db_name)

        closing_spread = closing.get("spread")
        home_score = result.get("home_score") if result else None
        away_score = result.get("away_score") if result else None
        status = result.get("status") if result else None

        # Determine outcome
        if status in ("postponed", "cancelled"):
            outcome = status
            ungraded += 1
        elif home_score is None or away_score is None:
            outcome = "ungraded"
            ungraded += 1
        else:
            # Margin from selected team's perspective
            if selected_team == selected_event.home_team:
                margin = home_score - away_score
                scoring_margin = float(home_score - away_score)
            else:
                margin = away_score - home_score
                scoring_margin = float(away_score - home_score)

            if margin > 0:
                outcome = "win"
                wins += 1
            elif margin < 0:
                outcome = "loss"
                losses += 1
                if first_elimination is None:
                    first_elimination = week
            else:
                outcome = "tie"
                ties += 1
                if first_elimination is None:
                    first_elimination = week

        # Get snapshot decision time
        import sqlite3

        with sqlite3.connect(db_name) as conn:
            decision_at = conn.execute(
                "SELECT decision_at FROM decision_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()[0]

        # Mark counterfactual weeks (after first elimination)
        counterfactual = first_elimination is not None and week > first_elimination

        weekly_results.append(
            WeeklyResult(
                season=season,
                week=week,
                decision_at=decision_at,
                snapshot_id=snapshot_id,
                algorithm=algorithm,
                source_revision=source_revision,
                parameters=parameters,
                split_week=split_week,
                selected_team=selected_team,
                opponent=opponent,
                decision_spread=decision_spread,
                closing_spread=closing_spread,
                home_score=home_score,
                away_score=away_score,
                scoring_margin=scoring_margin if home_score is not None else None,
                outcome=outcome,
                previously_used=[p.team for p in prior_picks],
                counterfactual=counterfactual,
            )
        )

        # Lock this pick for future weeks
        prior_picks.append(
            Pick(
                team=selected_team,
                week=week,
                spread=decision_spread,
            )
        )

        decision_spreads.append(abs(decision_spread))
        if closing_spread is not None:
            closing_spreads.append(abs(closing_spread))
            decision_to_closing.append(abs(closing_spread) - abs(decision_spread))

        # Calculate best alternative (simple: best spread among legal picks)
        legal_events = [
            e
            for e in snapshot_events
            if e.week == week
            and e.home_team not in {p.team for p in prior_picks}
            and e.away_team not in {p.team for p in prior_picks}
        ]
        if legal_events:
            best_spread = max(abs(e.spread) for e in legal_events)
            selected_vs_best.append(abs(decision_spread) - best_spread)

    aggregate = AggregateResult(
        algorithm=algorithm,
        season=season,
        parameters=parameters,
        split_week=split_week,
        first_elimination_week=first_elimination,
        wins=wins,
        losses=losses,
        ties=ties,
        ungraded=ungraded,
        weeks_survived=len(weekly_results),
        avg_decision_spread=sum(decision_spreads) / len(decision_spreads)
        if decision_spreads
        else 0.0,
        avg_closing_spread=sum(closing_spreads) / len(closing_spreads)
        if closing_spreads
        else 0.0,
        avg_decision_to_closing=sum(decision_to_closing) / len(decision_to_closing)
        if decision_to_closing
        else 0.0,
        avg_selected_vs_best_alternative=sum(selected_vs_best) / len(selected_vs_best)
        if selected_vs_best
        else 0.0,
    )

    return weekly_results, aggregate


def write_json(weekly: list[WeeklyResult], aggregate: AggregateResult, path: Path):
    """Write deterministic JSON output."""
    output = {
        "aggregate": asdict(aggregate),
        "weekly": [asdict(w) for w in weekly],
    }
    with path.open("w") as f:
        json.dump(output, f, indent=2, sort_keys=True)


def write_csv(weekly: list[WeeklyResult], aggregate: AggregateResult, path: Path):
    """Write deterministic CSV output with aggregate section."""
    with path.open("w", newline="") as f:
        writer = csv.writer(f)

        # Aggregate section
        writer.writerow(["AGGREGATE"])
        agg_dict = asdict(aggregate)
        for key in sorted(agg_dict.keys()):
            val = agg_dict[key]
            if isinstance(val, dict):
                val = json.dumps(val, sort_keys=True)
            writer.writerow([key, val])

        # Blank line separator
        writer.writerow([])

        # Weekly section
        writer.writerow(["WEEKLY"])
        if weekly:
            fieldnames = list(asdict(weekly[0]).keys())
            dict_writer = csv.DictWriter(f, fieldnames=fieldnames)
            dict_writer.writeheader()
            for result in weekly:
                row = asdict(result)
                row["previously_used"] = ",".join(row["previously_used"])
                row["parameters"] = json.dumps(row["parameters"], sort_keys=True)
                dict_writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Backtest survivor pool algorithms")
    parser.add_argument("--db", default=DEFAULT_DB_NAME, help="SQLite database path")
    parser.add_argument("--season", type=int, required=True, help="Season year")
    parser.add_argument(
        "--algorithm",
        required=True,
        choices=list(ALGORITHM_DISPATCH.keys()),
        help="Algorithm slug",
    )
    parser.add_argument(
        "--split-week", type=int, default=18, help="Optimization horizon"
    )
    parser.add_argument(
        "--mode",
        choices=["strict", "degraded"],
        default="strict",
        help="strict: require snapshots; degraded: skip missing",
    )
    parser.add_argument("--output", type=Path, help="Output path (JSON or CSV)")
    parser.add_argument(
        "--format", choices=["json", "csv"], default="json", help="Output format"
    )

    args = parser.parse_args()

    try:
        weekly, aggregate = run_backtest(
            args.db, args.season, args.algorithm, args.split_week, args.mode
        )

        if args.output:
            if args.format == "json":
                write_json(weekly, aggregate, args.output)
            else:
                write_csv(weekly, aggregate, args.output)
            print(f"Wrote {len(weekly)} results to {args.output}", file=sys.stderr)
        else:
            print(json.dumps(asdict(aggregate), indent=2, sort_keys=True))

    except (ValueError, FileNotFoundError, KeyError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
