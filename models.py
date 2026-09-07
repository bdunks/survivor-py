import re
from dataclasses import dataclass, field
from typing import NamedTuple


@dataclass
class EventOdds:
    event_id: int
    season_year: int
    week: int
    short_name: str
    spread: float
    away_team: str = field(init=False)
    home_team: str = field(init=False)
    favored_team: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.short_name, str):
            raise TypeError(f"Invalid matchup: {self.short_name!r}")

        teams = [
            team.strip()
            for team in re.split(r"@|VS", self.short_name, flags=re.IGNORECASE)
        ]
        if len(teams) != 2 or not all(teams):
            raise ValueError(f"Invalid matchup: {self.short_name!r}")

        self.away_team, self.home_team = teams
        self.favored_team = self.home_team if self.spread <= 0 else self.away_team


class Pick(NamedTuple):
    team: str
    week: int
    spread: float | None = None
