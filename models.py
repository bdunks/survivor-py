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
        try:
            teams = re.split(r"@|VS", self.short_name, flags=re.IGNORECASE)
            if len(teams) != 2:
                raise ValueError(f"Expected 2 teams, got {len(teams)}")
            self.away_team, self.home_team = teams
            self.away_team = self.away_team.strip()
            self.home_team = self.home_team.strip()
            self.favored_team = self.home_team if self.spread <= 0 else self.away_team
        except (ValueError, AttributeError) as e:
            print(f"Warning: Could not parse game '{self.short_name}': {e}")
            print("This game will be skipped. CBS Sports may have changed their format.")
            # Set default values to prevent further errors
            self.away_team = "UNK"
            self.home_team = "UNK" 
            self.favored_team = "UNK"


class Pick(NamedTuple):
    team: str
    week: int
    spread: Optional[float] = None
