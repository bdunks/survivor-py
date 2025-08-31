import re
from dataclasses import dataclass, field
from typing import NamedTuple, Optional


@dataclass
class EventOdds:
    event_id: int
    season_year: int
    week: int
    short_name: str
    spread: float
    away_team: str = field(
        init=False
    )  # These fields won't be initialized by the default __init__
    home_team: str = field(init=False)
    favored_team: str = field(init=False)

    def __post_init__(self):
        self.away_team, self.home_team = re.split(
            r"@|VS", self.short_name, flags=re.IGNORECASE
        )
        self.away_team = self.away_team.strip()
        self.home_team = self.home_team.strip()
        self.favored_team = self.home_team if self.spread <= 0 else self.away_team


class Pick(NamedTuple):
    team: str
    week: int
    spread: Optional[float] = None
