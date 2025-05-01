#!/usr/bin/env python

# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import argparse
import datetime
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

FILTER_INTERVAL_WEEKS = 26
DEFAULT_PLOT_STYLE = "ggplot"

# Mapping of days as outputted in Rust crate to how each day should be formatted in the plot legend
DAYS = {
    ("Mon",): "Monday",
    ("Tue",): "Tuesday",
    ("Wed",): "Wednesday",
    ("Thu",): "Thursday",
    ("Fri",): "Friday",
    ("Sat",): "Saturday",
    ("Sun",): "Sunday",
}

MINI_DAYS = {
    ("Mon", "Tue", "Wed", "Thu", "Fri", "Sun"): "Non-Saturday",
    ("Sat",): "Saturday",
}

A = argparse.ArgumentParser(
    description="Generates plots of crossword statistics from a CSV"
)
A.add_argument(
    "in_file",
    action="store",
    type=str,
    help="The path to a CSV file generated from the crossword crate",
)
A.add_argument(
    "out_file",
    action="store",
    type=str,
    help="The output path where plots should be saved (e.g. trends.png)",
)
A.add_argument(
    "-c",
    "--ceiling",
    action="store",
    type=int,
    default=None,
    help="Max Y Value in minutes",
)
A.add_argument(
    "-s",
    "--style",
    action="store",
    default=DEFAULT_PLOT_STYLE,
    type=str,
    choices=plt.style.available,
    help="Name of the plot style to use; must be in plt.style.available",
)
A.add_argument(
    "-m",
    "--mini",
    action="store_true",
    default=False,
    help="Only separate Saturdays, not all days of the week (for mini puzzles)",
)


def parse_data(csv_path):
    """Parse crossword database stored at the given path into a pandas DataFrame. The DataFrame
    only contains solve data for unaided, solved puzzles and is sorted by the index, the time when
    each puzzle was solved.

    Interesting columns in the returned DataFrame:
    solve_time_secs
    weekday
    """
    df = pd.read_csv(csv_path, parse_dates=["date"])
    df["Solved datetime"] = pd.to_datetime(df["solved_unix"], unit="s")
    # Use the date solved rather than the puzzle date as the index.
    # Puzzle date is interesting for analyzing puzzle difficulty over time (but skewed by change
    # in ability over time)
    # Date solved is interesting for analyzing change in solving ability over time (assuming puzzle
    # difficulty is a constant)
    df.index = df["Solved datetime"]
    df = df.sort_index()
    # Filter out:
    # * Puzzles that were solved more than 7 days after first open. These puzzles were revisited
    # much later, making it hard to make accurate conclusions about the solve time.
    # * Unsolved puzzles
    # * Puzzles where cheats were used
    df = df[
        (df["solved_unix"] - df["opened_unix"] < 3600 * 24 * 7)
        & (df["cheated"] == False)
        & df.solve_time_secs.notnull()
    ]

    return df


def save_plot(df, out_path, ymax, mini=False):
    fig = plt.figure(figsize=(10, 7), dpi=200)
    today = datetime.date.today().isoformat()
    latest_solve = df["date"].sort_values().iat[-1].date().isoformat()
    plt.title(
        f"NYT {'mini' if mini else 'crossword'} solve time ({FILTER_INTERVAL_WEEKS}-week rolling average) as of {today}"
    )
    ax = fig.gca()
    for day_data, day_legend in (MINI_DAYS if mini else DAYS).items():
        rolling_avg = (
            df[df["weekday"].isin(day_data)]["solve_time_secs"]
            .rolling(f"{FILTER_INTERVAL_WEEKS * 7}D")
            .mean()
        )

        (rolling_avg / (1.0 if mini else 60.0)).plot(
            ax=ax,
            label=day_legend,
            linewidth=2,
        )
    plt.legend()

    ax.set_xlabel(f"Solve Date (latest: {latest_solve})")
    ax.set_ylabel("Seconds" if mini else "Minutes")
    minor_yticks = np.arange(0, ymax + 1, 5)
    
    ax.set_ylim(0, ymax)
    ax.set_yticks(minor_yticks, minor=True)

    # plot multiples of 30 for mini puzzles
    if mini:
        major_yticks = np.arange(0, ymax + 1, 30)
        ax.set_yticks(major_yticks, minor=False)

    # Show y-axis labels on the right of the plot as well 
    ax_right = ax.secondary_yaxis('right')
    ax_right.set_yticks(ax.get_yticks())

    plt.xticks(rotation=0)

    plt.grid(True, which="both", axis="both")
    plt.tight_layout()
    plt.savefig(out_path)


def generate(in_file, out_file, ceiling=None, style=DEFAULT_PLOT_STYLE, mini=False):
    df = parse_data(in_file)

    if ceiling is None:
        # Pick an appropriate y-axis, balancing being robust to outliers vs. showing all data
        ymax = df["solve_time_secs"].quantile(0.99) / (1.0 if mini else 60.0)
    else:
        ymax = ceiling

    if style is not None:
        plt.style.use(style)
    save_plot(df, out_file, ymax, mini=mini)

    if mini:
        min_time = min(df["solve_time_secs"])
        print(f"Your fastest time is {int(min_time)}s")
        min_time_achieved = df[df["solve_time_secs"] == 13.0].index.to_list()

        print(f"This minimum was achieved {len(min_time_achieved)} times on the following dates:")
        for date in min_time_achieved:
            print(f"  {date.date().isoformat()}")


def main():
    args = A.parse_args()

    generate(args.in_file, args.out_file, args.ceiling, args.style, args.mini)


if __name__ == "__main__":
    main()
