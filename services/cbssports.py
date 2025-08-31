import requests
from bs4 import BeautifulSoup

from models import EventOdds


class Error:
    type: str


class CBSSportsService:
    def __init__(self):
        self.http_service = requests

    def check(self, event_id, short_name, spread):
        if event_id is None:
            return Error("event_id")
        if short_name is None:
            return Error("short_name")
        if spread is None:
            return Error("spread")

    def fetch_soup(self, url):
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return BeautifulSoup(response.content, "html.parser")

    def fetch_events(self, season_year, starting_week=1):
        results = []
        error_count = 0  # Track the number of errors

        weeks = range(starting_week, 19)
        for week_number in weeks:
            print(f"Processing Week {week_number}")

            week_url = f"https://www.cbssports.com/nfl/scoreboard/{season_year}/regular/{week_number}/"
            soup = self.fetch_soup(week_url)

            # Find all elements with class "single-score-card"
            score_cards = soup.find_all("div", class_="single-score-card")

            # Iterate through each score card and extract required data
            event_odds = []
            for card in score_cards:
                # Get the id attribute
                event_id = card.get("id")
                if event_id:
                    event_id = event_id.split("-")[-1]

                # Get the data-abbrev attribute
                data_abbrev = card.get("data-abbrev")

                if data_abbrev:
                    short_name = data_abbrev.split("_")[-1]

                # Find the in-progress-odds-home element within the card
                odds_home = card.find("td", class_="in-progress-odds-home")

                # Get the text inside the in-progress-odds-home element if it exists and convert to integer spread
                if odds_home:
                    odds_home_text = odds_home.get_text(strip=True)
                    try:
                        spread = 0 if odds_home_text == "PK" else float(odds_home_text)
                    except ValueError:
                        pass

                error = self.check(event_id, short_name, spread)
                if error:
                    print(
                        f"Error - Week {week_number} - Type - {error.type}{' -- short_name: ' + short_name if short_name else ''}"
                    )

                    error_count += 1
                    continue

                event_odds.append(
                    EventOdds(
                        event_id=event_id,
                        season_year=season_year,  # This is the same for all events in a season
                        week=week_number,
                        short_name=short_name,
                        spread=spread,
                    )
                )

            print(
                f"Week {week_number} processing complete. {len(event_odds)} events processed.\n"
            )  # Progress reporting per week

            results.extend(event_odds)

        print(
            f"Processing complete. Total events processed: {len(results)}, Total errors: {error_count}"
        )

        return results
