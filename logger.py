# Custom logger that saves to a CSV file
# Example usage:
# in main.py:
# import logging
# from logger import CSVLogger
# logging.setLoggerClass(CSVLogger)
# csv_logger = logging.getLogger("csv_logger")
# csv_logger.log(
#     [
#         "Split Week",
#         "Week",
#         "Team",
#         "Event",
#         "Spread",
#         "Future Value",
#         "Scaling Factor",
#         "Future Value Multiplier",
#         "Score",
#     ]
# )

# in other files:
# import logging
# should not be required, but was in code -> logging.setLoggerClass(CSVLogger)
# csv_logger = logging.getLogger("csv_logger")
# csv_logger.log(
#     [
#         split_week,
#         event.week,
#         event.favored_team,
#         event.short_name,
#         event.spread,
#         score_details.future_value,
#         score_details.scaling_factor,
#         (1 / score_details.future_value) * score_details.scaling_factor,
#         score_details.score,
#     ]
# )

from typing import Any, Iterable
import csv
import logging
import time


class CSVLogger(logging.Logger):
    def __init__(self, name):
        super().__init__(name)
        self.filename = f"log/{name}_{str(int(time.time()))}.csv"
        self.file = open(self.filename, "a", newline="")
        self.writer = csv.writer(self.file)

    def log(self, msg: Iterable[Any], level: int = logging.INFO):
        self.writer.writerow(msg)
        self.file.flush()
