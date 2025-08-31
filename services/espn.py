import requests

from models import EventOdds


class EspnService:
    def __init__(self):
        self.http_service = requests

    def fetch_json(self, url):
        response = self.http_service.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()

    def fetch_events(self, season_year, starting_week=1):
        results = []
        error_count = 0  # Track the number of errors

        weeks = range(starting_week, 19)
        for week_number in weeks:
            week_url = f"http://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{season_year}/types/2/weeks/{week_number}/events?lang=en&region=us"
            week_data = self.fetch_json(week_url)

            print(f"Processing Week {week_number}")

            event_odds = []
            for idx, item in enumerate(week_data["items"]):
                try:
                    event_data = self.fetch_json(item["$ref"])
                    odds_url = event_data["competitions"][0]["odds"]["$ref"]
                    odds_data = self.fetch_json(odds_url)

                    if odds_data["items"]:
                        spread_sum = sum(
                            odds_item["spread"]
                            for odds_item in odds_data["items"]
                            if "spread" in odds_item
                        )
                        average_spread = spread_sum / len(odds_data["items"])
                    else:
                        average_spread = 0

                    event_odds.append(
                        EventOdds(
                            event_id=event_data["id"],
                            season_year=season_year,  # This is the same for all events in a season
                            week=week_number,
                            short_name=event_data["shortName"],
                            spread=average_spread,
                        )
                    )
                except KeyError as e:
                    print(
                        f"KeyError encountered: Week {week_number}, Item {idx}, Event {item['$ref']}: Missing key {e}"
                    )
                    error_count += 1
                    continue
                except Exception as e:
                    print(
                        f"An error occurred: Week {week_number}, Item {idx}, Event {item['$ref']}: {e}"
                    )
                    error_count += 1
                    continue

            print(
                f"Week {week_number} processing complete. {len(event_odds)} events processed.\n"
            )  # Progress reporting per week

            results.extend(event_odds)

        print(
            f"Processing complete. Total events processed: {len(results)}, Total errors: {error_count}"
        )
        return results
