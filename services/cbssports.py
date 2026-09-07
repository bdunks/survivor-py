import math

import requests
from bs4 import BeautifulSoup, Tag

from models import EventOdds


def fetch_soup(url: str) -> BeautifulSoup:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.content, "html.parser")


def parse_events(
    html: str | bytes | BeautifulSoup, season_year: int, week_number: int
) -> list[EventOdds]:
    soup = (
        BeautifulSoup(html, "html.parser") if isinstance(html, (str, bytes)) else html
    )
    events = []

    for card in soup.find_all("div", class_="single-score-card"):
        if not isinstance(card, Tag):
            continue
        identifier = card.get("id")
        if not isinstance(identifier, str) or not identifier:
            continue
        try:
            event_id = int(identifier.rsplit("-", 1)[-1])
        except ValueError:
            continue

        data_abbrev = card.get("data-abbrev")
        if not isinstance(data_abbrev, str) or not data_abbrev:
            continue
        short_name = data_abbrev.rsplit("_", 1)[-1].strip()
        if not short_name:
            continue

        odds_home = card.find("td", class_="in-progress-odds-home")
        if odds_home is None:
            continue
        odds_home_text = odds_home.get_text(strip=True)
        if odds_home_text.upper() == "PK":
            spread = 0.0
        else:
            try:
                spread = float(odds_home_text)
            except ValueError:
                continue
            if not math.isfinite(spread):
                continue

        try:
            events.append(
                EventOdds(
                    event_id=event_id,
                    season_year=season_year,
                    week=week_number,
                    short_name=short_name,
                    spread=spread,
                )
            )
        except (TypeError, ValueError):
            continue

    return events


def fetch_events(season_year: int, starting_week: int = 1) -> list[EventOdds]:
    results = []
    error_count = 0

    for week_number in range(starting_week, 19):
        print(f"Processing Week {week_number}")
        week_url = (
            f"https://www.cbssports.com/nfl/scoreboard/"
            f"{season_year}/regular/{week_number}/"
        )
        try:
            soup = fetch_soup(week_url)
        except requests.RequestException as error:
            print(f"Failed to fetch data for week {week_number}: {error}")
            print("Skipping this week and continuing...")
            error_count += 1
            continue

        event_odds = parse_events(soup, season_year, week_number)
        print(
            f"Week {week_number} processing complete. "
            f"{len(event_odds)} events processed.\n"
        )
        results.extend(event_odds)

    print(
        f"Processing complete. Total events processed: {len(results)}, "
        f"Total errors: {error_count}"
    )
    if not results and error_count > 0:
        print(
            "Warning: No data was retrieved. Please check your internet connection and try again."
        )
        print(
            "If the problem persists, CBS Sports may have changed their website format."
        )

    return results
