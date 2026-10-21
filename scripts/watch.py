#!/usr/bin/env python3
"""watch.py - literature watch on OpenAlex, no account needed.

add       store a named query in watch.json
run       query OpenAlex for each watch, print the works that are new since the
          last run (DOI, venue, cites) and append them to watch_log.md
list      show the watches and when they last ran
remove    delete a watch
schedule  print the exact Windows schtasks command for a weekly run (never creates it)

How "new" is decided: OpenAlex's from_created_date filter is a paid feature
(Member+ plan; the API answers HTTP 429 "Plan upgrade required"), so the default
window is publication date: first run = everything published since --since
(or the last 365 days), later runs = published since the last run minus a
90-day lookback, and every work's OpenAlex ID is remembered so nothing is
reported twice. Works that OpenAlex adds late with an old publication date can
still be missed: say so in a PRISMA-style note if the watch feeds a review.
--window created tries from_created_date and falls back visibly if refused.

Each run costs 10 OpenAlex credits per watch (a title_and_abstract.search).

Usage
  python -X utf8 watch.py add --name sm-gpa --query '"social media" AND "academic performance"' --since 2024
  python -X utf8 watch.py run
  python -X utf8 watch.py run --name sm-gpa --limit 50
  python -X utf8 watch.py schedule --day MON --time 09:00
"""

import argparse
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scholar import openalex, oa_row, short, table, HTTPError, TODAY  # noqa: E402

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

LOOKBACK_DAYS = 90
FIRST_RUN_DAYS = 365
SEEN_CAP = 3000
OPERATORS = {"AND", "OR", "NOT"}
SELECT = ("id,doi,display_name,publication_year,publication_date,cited_by_count,primary_location,"
          "authorships,type,open_access,is_retracted")


# ---------------------------------------------------------------- query validation

class BadQuery(Exception):
    pass


def validate_query(q):
    """Reject queries OpenAlex would misread or that spend credits on nothing. Returns warnings."""
    q = (q or "").strip()
    if not q:
        raise BadQuery("the query is empty")
    if len(q) > 500:
        raise BadQuery(f"the query is {len(q)} characters; keep it under 500")
    if q.count('"') % 2:
        raise BadQuery(f"unbalanced double quotes ({q.count(chr(34))} quote marks): every phrase needs an opening "
                       "and a closing quote")
    if q.count("(") != q.count(")"):
        raise BadQuery("unbalanced parentheses")
    if "," in q:
        raise BadQuery("a comma separates OpenAlex filters and would cut the query: use AND / OR instead")
    if "|" in q:
        raise BadQuery("a pipe is OR in OpenAlex filter syntax and breaks a search string: write OR")
    tokens = re.findall(r'"[^"]*"|\(|\)|\S+', q)
    words = [t for t in tokens if t not in ("(", ")")]
    if not words:
        raise BadQuery("no search terms in the query")
    if words[0] in OPERATORS or words[-1] in OPERATORS:
        raise BadQuery("the query starts or ends with AND / OR / NOT")
    for x, y in zip(words, words[1:]):
        if x in OPERATORS and y in OPERATORS:
            raise BadQuery(f"two operators in a row: {x} {y}")
    if any(t == '""' for t in tokens):
        raise BadQuery("an empty phrase \"\" in the query")
    warnings = []
    if any(t in ("and", "or", "not") for t in words):
        warnings.append("lowercase and/or/not are searched as words; OpenAlex operators must be uppercase AND / OR / NOT")
    return warnings


# ---------------------------------------------------------------- store

def load(path):
    if not os.path.exists(path):
        return {"version": 1, "watches": []}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("watches", [])
    return data


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def find(data, name):
    return next((w for w in data["watches"] if w["name"] == name), None)


# ---------------------------------------------------------------- commands

def cmd_add(a):
    try:
        warnings = validate_query(a.query)
    except BadQuery as e:
        print(f"ERROR: query rejected: {e}\n  query: {a.query}", file=sys.stderr)
        return 2
    if not re.fullmatch(r"[A-Za-z0-9_\-]{1,40}", a.name):
        print("ERROR: --name must be 1-40 letters, digits, - or _", file=sys.stderr)
        return 2
    data = load(a.file)
    if find(data, a.name):
        print(f"ERROR: a watch named '{a.name}' exists; remove it first or pick another name", file=sys.stderr)
        return 2
    data["watches"].append({"name": a.name, "query": a.query.strip(), "since": a.since, "added": TODAY,
                            "last_run": None, "runs": 0, "seen": [], "total_new": 0})
    save(a.file, data)
    print(f"added watch '{a.name}' to {os.path.abspath(a.file)} | {len(data['watches'])} watches | {TODAY}")
    print(table([[a.name, a.query.strip(), str(a.since or "(last 365 days)")]], ["name", "query", "since"]))
    for w in warnings:
        print(f"WARNING: {w}")
    print("Run `watch.py run` now for the baseline; each run costs 10 OpenAlex credits per watch.")
    return 0


def window_for(w, mode):
    """(filter string, human description) for this run."""
    since_floor = f"{w['since']}-01-01" if w.get("since") else None
    if mode == "created" and w.get("last_run"):
        return f"from_created_date:{w['last_run']}", f"created in OpenAlex since {w['last_run']}"
    if w.get("last_run"):
        start = (dt.date.fromisoformat(w["last_run"]) - dt.timedelta(days=LOOKBACK_DAYS)).isoformat()
        if since_floor and start < since_floor:
            start = since_floor
        return f"from_publication_date:{start}", f"published since {start} (last run {w['last_run']} minus {LOOKBACK_DAYS} days)"
    start = since_floor or (dt.date.today() - dt.timedelta(days=FIRST_RUN_DAYS)).isoformat()
    return f"from_publication_date:{start}", f"first run: published since {start}"


def run_one(w, a):
    mode = a.window
    flt, desc = window_for(w, mode)
    params = {"filter": f"title_and_abstract.search:{w['query']},{flt},is_retracted:false",
              "per_page": min(max(a.limit, 1), 200), "sort": "publication_date:desc", "select": SELECT}
    try:
        data = openalex("works", params)
    except HTTPError as e:
        body = e.body if isinstance(e.body, str) else ""
        if mode == "created" and "Plan upgrade required" in body:
            print(f"WARNING: from_created_date is a paid OpenAlex feature (HTTP {e.status}); "
                  "falling back to the publication-date window", file=sys.stderr)
            flt, desc = window_for(w, "published")
            params["filter"] = f"title_and_abstract.search:{w['query']},{flt},is_retracted:false"
            data = openalex("works", params)
        elif e.status in (400, 403):
            raise BadQuery(f"OpenAlex rejected the request (HTTP {e.status}): {body[:200]}")
        else:
            raise
    results = (data or {}).get("results", [])
    total = (data or {}).get("meta", {}).get("count")
    seen = set(w.get("seen") or [])
    new = []
    for work in results:
        wid = (work.get("id") or "").rsplit("/", 1)[-1]
        if not wid or wid in seen:
            continue
        row = oa_row(work)
        row["id"] = wid
        row["date"] = work.get("publication_date")
        new.append(row)
    return new, total, len(results), desc


def log_lines(w, new, total, shown, desc):
    L = [f"## {TODAY} | {w['name']} | {len(new)} new | window: {desc} | matches {total}, checked {shown}"]
    L.append(f"query: {w['query']}")
    for r in new:
        who = short(r["first_author"], 30) + (" et al." if r["n_authors"] > 2 else "")
        doi = f"https://doi.org/{r['doi']}" if r["doi"] else "(no DOI)"
        venue = r["venue"] or "(no venue)"
        core = "" if r.get("core_venue") is not False or not r["venue"] else " (venue outside CWTS core: vet it)"
        L.append(f"- {r['date'] or r['year']} | {who} | {r['title']} | *{venue}*{core} | cites {r['cites']} | {doi}")
    if not new:
        L.append("- nothing new")
    L.append("")
    return "\n".join(L)


def cmd_run(a):
    data = load(a.file)
    watches = [w for w in data["watches"] if not a.name or w["name"] == a.name]
    if not watches:
        print(f"ERROR: no watches{' named ' + a.name if a.name else ''} in {os.path.abspath(a.file)}; "
              "add one with `watch.py add`", file=sys.stderr)
        return 2
    total_new, credits, failed = 0, 0, 0
    log_chunks = []
    for w in watches:
        try:
            validate_query(w["query"])
            new, total, shown, desc = run_one(w, a)
        except BadQuery as e:
            print(f"ERROR: watch '{w['name']}': {e}", file=sys.stderr)
            failed += 1
            continue
        credits += 10
        total_new += len(new)
        print(f"watch: {w['name']} | {len(new)} new | window: {desc} | matches {total}, checked {shown} | {TODAY}")
        print(f"  query: {w['query']}")
        if new:
            print(table([[str(r["date"] or r["year"] or ""), str(r["cites"] if r["cites"] is not None else ""),
                          short(r["first_author"], 22) + (" et al." if r["n_authors"] > 2 else ""),
                          short(r["title"], 70),
                          short(r["venue"], 30) + (" *" if r.get("core_venue") is False and r["venue"] else ""),
                          r["doi"] or "(no DOI)"]
                         for r in new], ["date", "cites", "first author", "title", "venue", "doi"]))
            if any(r.get("core_venue") is False and r["venue"] for r in new):
                print("  * venue outside the CWTS core list: vet it before citing.")
        if total and shown < total:
            print(f"  only the {shown} most recent of {total} matches were checked; raise --limit to see more")
        log_chunks.append(log_lines(w, new, total, shown, desc))
        if not a.dry_run:
            seen = list(w.get("seen") or []) + [r["id"] for r in new]
            w["seen"] = seen[-SEEN_CAP:]
            w["last_run"] = TODAY
            w["runs"] = w.get("runs", 0) + 1
            w["total_new"] = w.get("total_new", 0) + len(new)
    if not a.dry_run:
        save(a.file, data)
        if log_chunks:
            with open(a.log, "a", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(log_chunks))
    print(f"run: {len(watches) - failed} of {len(watches)} watches | {total_new} new works | "
          f"{credits} OpenAlex credits spent | log: {os.path.abspath(a.log)}"
          + (" | dry run: nothing saved" if a.dry_run else ""))
    print("New works are candidates, not sources: read the abstract, then `scholar.py add` the ones you cite.")
    return 1 if failed else 0


def cmd_list(a):
    data = load(a.file)
    if not data["watches"]:
        print(f"no watches in {os.path.abspath(a.file)}")
        return 0
    print(f"{len(data['watches'])} watches in {os.path.abspath(a.file)} | {TODAY}")
    print(table([[w["name"], w["query"], str(w.get("since") or ""), w.get("last_run") or "never",
                  str(w.get("runs", 0)), str(w.get("total_new", 0)), str(len(w.get("seen") or []))]
                 for w in data["watches"]],
                ["name", "query", "since", "last run", "runs", "new so far", "seen ids"]))
    return 0


def cmd_remove(a):
    data = load(a.file)
    w = find(data, a.name)
    if not w:
        print(f"ERROR: no watch named '{a.name}'", file=sys.stderr)
        return 2
    data["watches"].remove(w)
    save(a.file, data)
    print(f"removed watch '{a.name}' | {len(data['watches'])} left")
    return 0


def cmd_schedule(a):
    if not re.fullmatch(r"(MON|TUE|WED|THU|FRI|SAT|SUN)", a.day.upper()):
        print("ERROR: --day must be MON..SUN", file=sys.stderr)
        return 2
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", a.time):
        print("ERROR: --time must be HH:MM (24 h)", file=sys.stderr)
        return 2
    data = load(a.file)
    n = len(data["watches"])
    py = sys.executable
    me = os.path.abspath(__file__)
    wf, lg = os.path.abspath(a.file), os.path.abspath(a.log)
    tr = f'\\"{py}\\" -X utf8 \\"{me}\\" run --file \\"{wf}\\" --log \\"{lg}\\"'
    cmd = f'schtasks /Create /SC WEEKLY /D {a.day.upper()} /ST {a.time} /TN "{a.task_name}" /TR "{tr}" /F'
    print(f"schedule: weekly on {a.day.upper()} at {a.time} | {n} watches = {10 * n} OpenAlex credits per week | "
          "nothing was created")
    print("Run this yourself in cmd.exe (or PowerShell with cmd /c in front):")
    print()
    print(cmd)
    print()
    print(table([
        ["test it now", f'schtasks /Run /TN "{a.task_name}"'],
        ["see it", f'schtasks /Query /TN "{a.task_name}" /V /FO LIST'],
        ["remove it", f'schtasks /Delete /TN "{a.task_name}" /F'],
        ["results", lg + " (stdout of a scheduled task is not kept; the log is the record)"],
    ], ["step", "command"]))
    if n == 0:
        print("WARNING: watch.json has no watches yet; the task would run and report nothing.")
    print("The task runs only while the PC is on and logged in or when 'Run whether user is logged on' is set "
          "in Task Scheduler. The OpenAlex key is read from the key file at run time; it is not in the command.")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--file", default="watch.json", help="where the watches are stored")
    p.add_argument("--log", default="watch_log.md", help="markdown log appended on every run")
    sub = p.add_subparsers(dest="cmd", required=True)

    ad = sub.add_parser("add", help="store a query",
                        epilog='example: python -X utf8 watch.py add --name sm-gpa --query \'"social media" AND "academic performance"\' --since 2024')
    ad.add_argument("--name", required=True)
    ad.add_argument("--query", required=True, help="OpenAlex title_and_abstract search: quoted phrases, AND / OR / NOT")
    ad.add_argument("--since", type=int, help="earliest publication year (first run baseline and floor)")

    r = sub.add_parser("run", help="report new works since the last run",
                       epilog="example: python -X utf8 watch.py run --name sm-gpa --limit 50")
    r.add_argument("--name", help="one watch only (default: all)")
    r.add_argument("--limit", type=int, default=25, help="most recent works checked per watch (max 200)")
    r.add_argument("--window", choices=["published", "created"], default="published",
                   help="created = try OpenAlex from_created_date (paid feature; falls back if refused)")
    r.add_argument("--dry-run", action="store_true", help="query and print, but save nothing")

    sub.add_parser("list", help="show the watches", epilog="example: python -X utf8 watch.py list")

    rm = sub.add_parser("remove", help="delete a watch", epilog="example: python -X utf8 watch.py remove --name sm-gpa")
    rm.add_argument("--name", required=True)

    sc = sub.add_parser("schedule", help="print the weekly schtasks command (not executed)",
                        epilog="example: python -X utf8 watch.py schedule --day MON --time 09:00")
    sc.add_argument("--day", default="MON")
    sc.add_argument("--time", default="09:00")
    sc.add_argument("--task-name", default="research-watch")

    a = p.parse_args()
    try:
        sys.exit(globals()["cmd_" + a.cmd](a) or 0)
    except HTTPError as e:
        sys.exit(f"API error: {e} {e.body[:200] if isinstance(e.body, str) else ''}")


if __name__ == "__main__":
    main()
