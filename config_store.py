from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from models import Pick

CONFIG_PATH = Path("config.json")
DEFAULT_CONFIG = {
    "current_week": 1,
    "picks": [],
    "algorithm": "best-spread",
    "split_week": 10,
}
VALID_ALGORITHMS = ("best-spread", "back-to-front", "weighted-future-value")


def _default_config() -> dict[str, Any]:
    return {**DEFAULT_CONFIG, "picks": []}


def _path(path: Path | str | None) -> Path:
    return CONFIG_PATH if path is None else Path(path)


def _validate_week(value: object, label: str) -> int:
    if type(value) is not int or not 1 <= value <= 18:
        raise ValueError(f"{label} must be between 1 and 18")
    return value


def _validate_algorithm(algorithm: object) -> str:
    if not isinstance(algorithm, str) or algorithm not in VALID_ALGORITHMS:
        options = ", ".join(VALID_ALGORITHMS)
        raise ValueError(f"Invalid algorithm: {algorithm}. Must be one of: {options}")
    return algorithm


def _validate_pick(pick: Pick) -> Pick:
    if not isinstance(pick, Pick):
        raise TypeError("pick must be a Pick")

    team = pick.team.strip().upper() if isinstance(pick.team, str) else ""
    if not 2 <= len(team) <= 3 or not team.isalpha():
        raise ValueError(f"Invalid pick team: {pick.team}. Must be 2-3 letters.")

    return Pick(
        team,
        _validate_week(pick.week, "Pick week"),
        pick.spread if pick.spread is not None else 0.0,
    )


def _pick_from_value(value: object) -> Pick:
    if isinstance(value, Pick):
        return _validate_pick(value)
    if isinstance(value, dict):
        return _validate_pick(
            Pick(
                team=value["team"],
                week=value["week"],
                spread=value.get("spread", 0.0),
            )
        )
    raise TypeError("pick must be a Pick or object")


def _validate_picks(values: object) -> list[Pick]:
    if not isinstance(values, list):
        raise TypeError("Picks must be a list")

    picks = [_pick_from_value(value) for value in values]
    weeks = [pick.week for pick in picks]
    if len(weeks) != len(set(weeks)):
        raise ValueError("Each week can only have one pick")
    return picks


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    try:
        data = json.loads(_path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_config()

    if not isinstance(data, dict):
        return _default_config()

    config = dict(data)
    try:
        config["current_week"] = _validate_week(
            data.get("current_week", DEFAULT_CONFIG["current_week"]), "Current week"
        )
    except ValueError:
        config["current_week"] = DEFAULT_CONFIG["current_week"]

    try:
        config["split_week"] = _validate_week(
            data.get("split_week", DEFAULT_CONFIG["split_week"]), "Split week"
        )
    except ValueError:
        config["split_week"] = DEFAULT_CONFIG["split_week"]

    try:
        config["algorithm"] = _validate_algorithm(
            data.get("algorithm", DEFAULT_CONFIG["algorithm"])
        )
    except ValueError:
        config["algorithm"] = DEFAULT_CONFIG["algorithm"]

    raw_picks = data.get("picks", [])
    picks: list[Pick] = []
    if isinstance(raw_picks, list):
        for value in raw_picks:
            try:
                picks.append(_pick_from_value(value))
            except (KeyError, TypeError, ValueError):
                continue
        try:
            _validate_picks(picks)
        except ValueError:
            picks = []
    config["picks"] = picks
    config.pop("user_picks", None)
    return config


def save_config(config: dict[str, Any], path: Path | str | None = None) -> None:
    if not isinstance(config, dict):
        raise TypeError("config must be a dictionary")

    current_week = _validate_week(
        config.get("current_week", DEFAULT_CONFIG["current_week"]), "Current week"
    )
    split_week = _validate_week(
        config.get("split_week", DEFAULT_CONFIG["split_week"]), "Split week"
    )
    algorithm = _validate_algorithm(
        config.get("algorithm", DEFAULT_CONFIG["algorithm"])
    )
    picks = _validate_picks(config.get("picks", []))

    data = {key: value for key, value in config.items() if key != "user_picks"}
    data.update(
        current_week=current_week,
        picks=[pick._asdict() for pick in picks],
        algorithm=algorithm,
        split_week=split_week,
    )

    target = _path(path)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def update_current_week(week: int, path: Path | str | None = None) -> None:
    _validate_week(week, "Current week")
    config = load_config(path)
    config["current_week"] = week
    save_config(config, path)


def update_algorithm(algorithm: str, path: Path | str | None = None) -> None:
    _validate_algorithm(algorithm)
    config = load_config(path)
    config["algorithm"] = algorithm
    save_config(config, path)


def update_split_week(split_week: int, path: Path | str | None = None) -> None:
    _validate_week(split_week, "Split week")
    config = load_config(path)
    config["split_week"] = split_week
    save_config(config, path)


def update_pick(pick: Pick, path: Path | str | None = None) -> None:
    pick = _validate_pick(pick)
    config = load_config(path)
    for index, existing in enumerate(config["picks"]):
        if existing.week == pick.week:
            config["picks"][index] = pick
            break
    else:
        config["picks"].append(pick)
    save_config(config, path)


def clear_pick(week: int, path: Path | str | None = None) -> None:
    _validate_week(week, "Pick week")
    config = load_config(path)
    config["picks"] = [pick for pick in config["picks"] if pick.week != week]
    save_config(config, path)


def clear_all_picks(path: Path | str | None = None) -> None:
    config = load_config(path)
    config["picks"] = []
    save_config(config, path)
