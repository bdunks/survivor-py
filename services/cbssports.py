import math
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import requests
from bs4 import BeautifulSoup, Tag

from models import GameEvent


def fetch_soup(url: str) -> BeautifulSoup:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    soup.__dict__["_raw_content"] = response.content
    return soup


def _card_value(
    card: Tag,
    attributes: tuple[str, ...] = (),
    selectors: tuple[str, ...] = (),
) -> str | None:
    for attribute in attributes:
        value = card.get(attribute)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for selector in selectors:
        element = card.select_one(selector)
        if element is None:
            continue
        for attribute in (
            "datetime",
            "data-value",
            "data-timestamp",
            "data-date",
            "content",
        ):
            value = element.get(attribute)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for attribute in element.attrs:
            if not attribute.startswith("data-"):
                continue
            value = element.get(attribute)
            if isinstance(value, str) and value.strip():
                return value.strip()
        value = element.get_text(" ", strip=True)
        if value:
            return value
    return None


def _number(value: str | None, *, integer: bool = False) -> int | float | None:
    if value is None:
        return None
    text = value.strip().replace("−", "-")
    if text.upper() == "PK":
        return 0 if integer else 0.0
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", text)
    if match is None:
        return None
    try:
        number = float(match.group())
    except ValueError:
        return None
    if not math.isfinite(number):
        return None
    if integer:
        return int(number) if number.is_integer() else None
    return number


def _integer(value: str | None) -> int | None:
    number = _number(value, integer=True)
    return number if isinstance(number, int) else None


def _kickoff(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    try:
        if text.isdigit():
            seconds = int(text) / (1000 if len(text) > 10 else 1)
            return datetime.fromtimestamp(seconds, UTC).isoformat()
        parsed = parsedate_to_datetime(text)
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC).isoformat()
    except (OverflowError, TypeError, ValueError):
        pass
    iso_text = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(iso_text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def _score(card: Tag, side: str) -> int | None:
    value = _card_value(
        card,
        attributes=(
            f"data-{side}-score",
            f"data-score-{side}",
        ),
        selectors=(
            f"[data-{side}-score]",
            f"[data-score-{side}]",
            f".{side}-score",
            f".score-{side}",
            f".{side}-team .score",
            f".team-{side} .score",
            f".team-{side} .team-score",
            f".{side} .team-score",
        ),
    )
    number = _number(value, integer=True)
    if isinstance(number, int):
        return number
    return None


def _status(card: Tag) -> str | None:
    status = _card_value(
        card,
        attributes=("data-game-status", "data-status", "data-state"),
        selectors=(".game-status", ".score-status", ".game-status-text", ".status"),
    )
    if status:
        return status
    status_node = card.select_one(".game-status")
    status_classes = str(status_node.get("class", "")) if status_node else ""
    if "postgame" in status_classes:
        return "Final"
    if "pregame" in status_classes:
        return "Scheduled"
    if "live" in status_classes or "in-progress" in status_classes:
        return "In Progress"
    return None


def parse_events(
    html: str | bytes | BeautifulSoup, season_year: int, week_number: int
) -> list[GameEvent]:
    soup = (
        BeautifulSoup(html, "html.parser") if isinstance(html, (str, bytes)) else html
    )
    events: list[GameEvent] = []

    for card in soup.find_all("div", class_="single-score-card"):
        if not isinstance(card, Tag):
            continue
        identifier = _card_value(
            card,
            attributes=("data-event-id", "data-id", "id"),
        )
        identifiers = re.findall(r"\d+", identifier or "")
        if not identifiers:
            continue
        event_id = int(identifiers[-1])

        data_abbrev = card.get("data-abbrev")
        short_name = (
            data_abbrev.rsplit("_", 1)[-1].strip()
            if isinstance(data_abbrev, str) and data_abbrev.strip()
            else ""
        )
        if not short_name:
            away = _card_value(
                card,
                attributes=("data-away-team", "data-away"),
                selectors=(
                    "[data-away-team]",
                    ".away-team .team-name",
                    ".team-away .team-name",
                ),
            )
            home = _card_value(
                card,
                attributes=("data-home-team", "data-home"),
                selectors=(
                    "[data-home-team]",
                    ".home-team .team-name",
                    ".team-home .team-name",
                ),
            )
            if away and home:
                short_name = f"{away} @ {home}"

        if not short_name:
            continue

        status = _status(card)
        spread_text = _card_value(
            card,
            attributes=("data-home-spread", "data-spread-home", "data-spread"),
            selectors=(
                "td.in-progress-odds-home",
                ".in-progress-odds-home",
                "[data-home-spread]",
                "[data-spread-home]",
                ".home-spread",
            ),
        )
        spread = _number(spread_text)
        if not isinstance(spread, (int, float)) and not (
            status and status.strip().lower().startswith("final")
        ):
            continue

        away_score = _score(card, "away")
        home_score = _score(card, "home")
        if away_score is None or home_score is None:
            scores = [
                _number(node.get_text(" ", strip=True), integer=True)
                for node in card.select(".team-score, .score, td.score, td.total")
            ]
            scores = [score for score in scores if isinstance(score, int)]
            if len(scores) >= 2:
                away_score = away_score if away_score is not None else scores[0]
                home_score = home_score if home_score is not None else scores[1]

        kickoff = _kickoff(
            _card_value(
                card,
                attributes=(
                    "data-kickoff",
                    "data-kickoff-at",
                    "data-start-time",
                    "data-start-date",
                    "data-game-date",
                    "data-event-date",
                    "data-date",
                ),
                selectors=(
                    "[data-kickoff]",
                    "[data-kickoff-at]",
                    "[data-start-time]",
                    "[data-start-date]",
                    "time[datetime]",
                    ".game-date",
                    ".game-time",
                    ".kickoff",
                    ".start-time",
                    ".single-score-card__date",
                ),
            )
        )
        home_moneyline = _integer(
            _card_value(
                card,
                attributes=("data-home-moneyline", "data-moneyline-home"),
                selectors=(
                    "td.in-progress-moneyline-home",
                    ".in-progress-moneyline-home",
                    "[data-home-moneyline]",
                    "[data-moneyline-home]",
                    ".home-moneyline",
                ),
            ),
        )
        away_moneyline = _integer(
            _card_value(
                card,
                attributes=("data-away-moneyline", "data-moneyline-away"),
                selectors=(
                    "td.in-progress-moneyline-away",
                    ".in-progress-moneyline-away",
                    "[data-away-moneyline]",
                    "[data-moneyline-away]",
                    ".away-moneyline",
                ),
            ),
        )
        total = _number(
            _card_value(
                card,
                attributes=("data-total", "data-over-under"),
                selectors=(
                    "td.in-progress-odds-total",
                    ".in-progress-odds-total",
                    "td.in-progress-odds-away",
                    ".in-progress-odds-away",
                    "[data-total]",
                    "[data-over-under]",
                    ".total",
                    ".over-under",
                ),
            )
        )

        try:
            events.append(
                GameEvent(
                    event_id=event_id,
                    season_year=season_year,
                    week=week_number,
                    short_name=short_name,
                    spread=float(spread) if spread is not None else None,
                    kickoff_at=kickoff,
                    game_status=status,
                    home_score=home_score,
                    away_score=away_score,
                    home_moneyline=home_moneyline,
                    away_moneyline=away_moneyline,
                    total=float(total) if total is not None else None,
                )
            )
        except (TypeError, ValueError):
            continue

    return events


class FetchResult(list[GameEvent]):
    def __init__(
        self,
        events: list[GameEvent],
        *,
        requested_weeks: list[int],
        successful_weeks: list[int],
        failed_weeks: list[int],
        source_urls: list[str],
        errors: list[str],
        raw_failures: list[dict[str, object]],
    ) -> None:
        super().__init__(events)
        self.requested_weeks = requested_weeks
        self.successful_weeks = successful_weeks
        self.failed_weeks = failed_weeks
        self.source_urls = source_urls
        self.errors = errors
        self.raw_failures = raw_failures


def fetch_events(season_year: int, starting_week: int = 1) -> FetchResult:
    results: list[GameEvent] = []
    requested_weeks = list(range(starting_week, 19))
    successful_weeks: list[int] = []
    failed_weeks: list[int] = []
    source_urls: list[str] = []
    errors: list[str] = []
    raw_failures: list[dict[str, object]] = []

    for week_number in requested_weeks:
        print(f"Processing Week {week_number}")
        week_url = (
            f"https://www.cbssports.com/nfl/scoreboard/"
            f"{season_year}/regular/{week_number}/"
        )
        source_urls.append(week_url)
        soup: BeautifulSoup | None = None
        try:
            soup = fetch_soup(week_url)
            event_odds = parse_events(soup, season_year, week_number)
            if soup.find_all("div", class_="single-score-card") and not event_odds:
                raise ValueError("no events parsed")
        except Exception as error:  # noqa: BLE001
            message = f"week {week_number}: {error}"[:1000]
            failed_weeks.append(week_number)
            errors.append(message)
            raw_content = getattr(soup, "_raw_content", None)
            if isinstance(raw_content, bytes):
                raw_failures.append(
                    {
                        "week": week_number,
                        "source_url": week_url,
                        "payload": raw_content,
                        "error": message,
                    }
                )
            print(f"Failed to process data for week {week_number}: {error}")
            print("Skipping this week and continuing...")
            continue

        successful_weeks.append(week_number)
        print(
            f"Week {week_number} processing complete. "
            f"{len(event_odds)} events processed.\n"
        )
        results.extend(event_odds)

    print(
        f"Processing complete. Total events processed: {len(results)}, "
        f"Total errors: {len(failed_weeks)}"
    )
    if not results and failed_weeks:
        print(
            "Warning: No data was retrieved. Please check your internet connection and try again."
        )
        print(
            "If the problem persists, CBS Sports may have changed their website format."
        )

    return FetchResult(
        results,
        requested_weeks=requested_weeks,
        successful_weeks=successful_weeks,
        failed_weeks=failed_weeks,
        source_urls=source_urls,
        errors=errors,
        raw_failures=raw_failures,
    )
