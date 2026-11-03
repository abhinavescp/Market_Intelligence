#!/usr/bin/env python3
"""Check the dashboard's results calendar and report which companies need loading.

Reads the data object ("const D = {...}") inside index.html, looks at D.calendar,
and lists every company whose results date has passed but whose status is still
"Pending". Writes two files that the GitHub Action uses:

  report.md       the text of the alert (a GitHub issue)
  due_count.txt   how many companies are waiting to be loaded

Uses only the Python standard library, so it costs nothing and needs no install.

Local test:
  python3 scripts/check_results.py --html index.html --today 2026-11-03
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta


def read_data(html_path):
    """Return the JSON object assigned to `const D = ` in the HTML file."""
    with open(html_path, encoding="utf-8") as f:
        text = f.read()
    marker = "const D = "
    start = text.find(marker)
    if start == -1:
        sys.exit("Could not find 'const D = ' in " + html_path)
    start += len(marker)
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    sys.exit("The data object in " + html_path + " does not close properly")


def parse_day(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def line(entry):
    timing = entry.get("timing") or "time not stated"
    return "{name} ({ticker}), {date}, {timing}".format(
        name=entry["name"], ticker=entry["ticker"], date=entry["date"], timing=timing
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", default="index.html")
    parser.add_argument("--today", help="override today's date, format YYYY-MM-DD (for testing)")
    parser.add_argument("--out-dir", default=".")
    parser.add_argument("--look-ahead-days", type=int, default=7)
    args = parser.parse_args()

    today = parse_day(args.today) if args.today else date.today()
    data = read_data(args.html)
    calendar = data["calendar"]
    calendar = calendar if isinstance(calendar, list) else list(calendar.values())
    as_of = data.get("asOf", "unknown")

    # Reported on an earlier day and still not marked Released: ready to load.
    due = sorted(
        (e for e in calendar if e["status"] != "Released" and parse_day(e["date"]) < today),
        key=lambda e: e["date"],
    )
    # Reporting today: the transcript usually appears the next day, so just a heads-up.
    today_list = [e for e in calendar if e["status"] != "Released" and parse_day(e["date"]) == today]
    horizon = today + timedelta(days=args.look_ahead_days)
    upcoming = sorted(
        (e for e in calendar
         if e["status"] != "Released" and today < parse_day(e["date"]) <= horizon),
        key=lambda e: e["date"],
    )

    lines = []
    lines.append("Checked on " + today.isoformat() + ". The dashboard currently shows data as of " + as_of + ".")
    lines.append("")
    if due:
        lines.append("## Ready to load (" + str(len(due)) + ")")
        lines.append("")
        lines.append("These companies have reported but are still marked Pending in the results calendar:")
        lines.append("")
        for e in due:
            lines.append("- [ ] " + line(e))
        lines.append("")
        lines.append("Next step: run the three stages for these companies, check the major numbers "
                     "against the sources, then set their status to Released and publish.")
    else:
        lines.append("## Nothing to load")
        lines.append("")
        lines.append("Every company whose results date has passed is marked Released.")
    if today_list:
        lines.append("")
        lines.append("## Reporting today")
        lines.append("")
        for e in today_list:
            lines.append("- " + line(e))
    if upcoming:
        lines.append("")
        lines.append("## Next " + str(args.look_ahead_days) + " days")
        lines.append("")
        for e in upcoming:
            lines.append("- " + line(e))
    lines.append("")
    lines.append("This alert is created by the scheduled workflow in .github/workflows/results-alert.yml. "
                 "It reads the results calendar inside index.html. The data stages and the final check are still done by hand.")

    with open(args.out_dir + "/report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    with open(args.out_dir + "/due_count.txt", "w", encoding="utf-8") as f:
        f.write(str(len(due)) + "\n")

    print("\n".join(lines))
    print("\nDue count:", len(due))


if __name__ == "__main__":
    main()
