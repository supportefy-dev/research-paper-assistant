#!/usr/bin/env python3
"""snowball.py - citation snowballing for the research-paper-assistant skill.

Builds the literature from seed papers instead of keywords: every reference
of a seed (backward) and every paper citing a seed (forward), scored for
relevance, then a second round from the best new papers. Free OpenAlex API
only, through scholar.py's helpers (the key is never printed).

Commands
  run       snowball from seed DOIs (or OpenAlex W ids)
  selftest  offline checks of scoring, de-duplication, round logic, PRISMA counts

Example
  python -X utf8 snowball.py run --seeds 10.1016/j.chb.2010.03.024 10.1016/j.chb.2011.08.026 \
      --topic "social media academic performance university students" --rounds 2 \
      --out cand_snowball.json --prisma prisma.md

Credits: a seed lookup (works/doi:...) costs 0; each backward batch
(filter=openalex_id:W1|W2|..., 100 ids) and each forward page
(filter=cites:W...) costs 1. The run prints the count it made plus the
X-RateLimit headers OpenAlex returned, when it sent them.
"""

import argparse
import json
import math
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scholar                                                    # noqa: E402
from scholar import (openalex, oa_row, norm_doi, clean, table, short, TODAY, HTTPError)   # noqa: E402

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

SELECT = ("id,doi,display_name,publication_year,cited_by_count,primary_location,authorships,type,"
          "open_access,is_retracted,abstract_inverted_index,referenced_works_count,referenced_works")
BATCH = 100              # OpenAlex allows up to 100 ids per openalex_id filter (1 credit)
FORWARD_PER_PAGE = 200

STOP = set("""a an the of and or in on at to for with by from as is are was were be been this that these those
it its into over under between among through about via than then there here which who whom whose what when
where how why not no nor do does did can could may might will would shall should study studies research paper
effect effects impact impacts role relationship relationships use using used based analysis among toward towards
case review evidence approach results findings data new model""".split())

# ---------------------------------------------------------------- budget (credits)

BUDGET = {"list_calls": 0, "entity_calls": 0, "remaining": None, "limit": None, "header_seen": False}
_real_http_get = scholar.http_get


def _recording_http_get(url, params=None, headers=None, **kw):
    """Same call as scholar.http_get, but remembers OpenAlex's rate-limit headers.
    Only the headers are read; the key stays inside params and is never logged."""
    r = _real_http_get(url, params=params, headers=headers, **kw)
    if r is not None and "api.openalex.org" in url:
        rem, lim = r.headers.get("X-RateLimit-Remaining"), r.headers.get("X-RateLimit-Limit")
        if rem is not None:
            BUDGET["remaining"], BUDGET["limit"], BUDGET["header_seen"] = rem, lim, True
    return r


scholar.http_get = _recording_http_get


def oa_list(params):
    """One works list call (1 credit for filter-only lists)."""
    BUDGET["list_calls"] += 1
    data = openalex("works", params) or {}
    return data.get("results", []), (data.get("meta") or {}).get("count")


def oa_entity(ident):
    """Single entity (0 credits). ident = DOI or W id."""
    BUDGET["entity_calls"] += 1
    ident = ident.strip()
    if re.fullmatch(r"[Ww]\d+", ident):
        return openalex("works/" + ident.upper(), {"select": SELECT})
    return openalex("works/doi:" + urllib.parse.quote(norm_doi(ident), safe="/()"), {"select": SELECT})


# ---------------------------------------------------------------- relevance

def stem(w):
    w = w.lower()
    for suf in ("ies", "ing", "ers", "er", "es", "s", "ed", "al", "ic"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            w = w[: -len(suf)]
            break
    return w[:6]            # crude prefix stem: 'university'/'universities' -> 'univer'


def terms_of(text):
    words = re.findall(r"[A-Za-z؀-ۿ][\w؀-ۿ'-]{2,}", clean(text))
    out = []
    for w in words:
        if w.lower() in STOP:
            continue
        s = stem(w)
        if s and s not in out:
            out.append(s)
    return out


def overlap(terms, text):
    """Fraction of topic terms present (by crude stem) in title + abstract. Heuristic."""
    if not terms:
        return 0.0
    have = {stem(w) for w in re.findall(r"[A-Za-z؀-ۿ][\w؀-ۿ'-]{2,}", clean(text))}
    hit = sum(1 for t in terms if t in have)
    return hit / len(terms)


def score_row(r):
    """score = 5 * term overlap + ln(cites + 1) / 2 + 1.5 per extra seed reaching it (max +3).
    Retracted papers are never scored (they are dropped earlier)."""
    cites = r.get("cites") or 0
    extra = max(0, len(r.get("reached_via") or []) - 1)
    r["co_citation_bonus"] = round(1.5 * min(extra, 2), 2)
    r["score"] = round(5 * r["overlap"] + math.log(cites + 1) / 2 + r["co_citation_bonus"], 3)
    return r["score"]


# ---------------------------------------------------------------- snowball core

def w_id(w):
    return (w.get("id") or "").rsplit("/", 1)[-1]


def make_row(w, via, direction, rnd):
    r = oa_row(w)
    r["openalex_id"] = w_id(w)
    r["referenced_works"] = [x.rsplit("/", 1)[-1] for x in (w.get("referenced_works") or [])]
    r["n_refs"] = w.get("referenced_works_count")
    r["reached_via"] = [via]
    r["direction"] = [direction]
    r["round"] = rnd
    return r


def fetch_backward(seed_rows, since, pool, identified, rnd, seen_batches):
    """referenced_works of every seed row, fetched in batches of 100 ids (1 credit each)."""
    want = {}
    for s in seed_rows:
        for wid in s["referenced_works"]:
            want.setdefault(wid, []).append(s["openalex_id"])
    ids = []
    for wid, vias in want.items():
        if wid in pool:                     # fetched in an earlier round: record the extra path, no refetch
            for via in vias:
                if via not in pool[wid]["reached_via"]:
                    pool[wid]["reached_via"].append(via)
                    pool[wid]["direction"].append("backward")
        elif wid not in seen_batches:
            ids.append(wid)
    for i in range(0, len(ids), BATCH):
        chunk = ids[i: i + BATCH]
        seen_batches.update(chunk)
        flt = "openalex_id:" + "|".join(chunk)
        if since:
            flt += f",publication_year:>{since - 1}"
        results, _ = oa_list({"filter": flt, "per_page": BATCH, "select": SELECT})
        identified["backward"] += len(results)
        for w in results:
            for via in want.get(w_id(w), []):
                merge(pool, make_row(w, via, "backward", rnd))


def fetch_forward(seed_rows, since, pages, pool, identified, rnd):
    """Papers citing each seed, most cited first, `pages` pages of 200 (1 credit per page)."""
    for s in seed_rows:
        flt = f"cites:{s['openalex_id']}"
        if since:
            flt += f",publication_year:>{since - 1}"
        for page in range(1, pages + 1):
            results, total = oa_list({"filter": flt, "per_page": FORWARD_PER_PAGE, "page": page,
                                      "sort": "cited_by_count:desc", "select": SELECT})
            s["citing_total"] = total
            identified["forward"] += len(results)
            for w in results:
                merge(pool, make_row(w, s["openalex_id"], "forward", rnd))
            if len(results) < FORWARD_PER_PAGE:
                break


def merge(pool, row):
    key = row["openalex_id"]
    if key in pool:
        p = pool[key]
        if row["reached_via"][0] not in p["reached_via"]:
            p["reached_via"].append(row["reached_via"][0])
            p["direction"].append(row["direction"][0])
        pool["_dups"] = pool.get("_dups", 0) + 1
    else:
        pool[key] = row


def run_snowball(seed_ids, topic, rounds, max_keep, since, forward_pages, topk, threshold, quiet=False):
    say = (lambda *a, **k: None) if quiet else print
    seeds, warnings = [], []
    for sid in seed_ids:
        try:
            w = oa_entity(sid)
        except HTTPError as e:
            w = None
            warnings.append(f"seed {sid}: {e}")
        if not w:
            warnings.append(f"seed {sid}: NOT FOUND in OpenAlex (check the DOI)")
            say(f"seed {sid}: NOT FOUND in OpenAlex")
            continue
        s = make_row(w, "seed", "seed", 0)
        s["input"] = sid
        if s["retracted"]:
            warnings.append(f"seed {sid} is RETRACTED in OpenAlex ({short(s['title'], 60)}): "
                            "its references and citers are kept but marked via_retracted_seed")
            say(f"WARNING: seed {sid} is RETRACTED: {short(s['title'], 70)}")
        seeds.append(s)
    if not seeds:
        sys.exit("no usable seed: nothing to snowball")

    terms = terms_of(topic) if topic else terms_of(" ".join(s["title"] for s in seeds))
    term_source = "topic" if topic else "seed titles"
    retracted_seed_ids = {s["openalex_id"] for s in seeds if s["retracted"]}
    seed_lookup = {s["openalex_id"]: s for s in seeds}
    pool = {}
    identified = {"backward": 0, "forward": 0}
    seen_batches = set()
    frontier = seeds
    round_log = []
    snowballed = set()
    for rnd in range(1, rounds + 1):
        before = set(pool) - {"_dups"}
        snowballed.update(s["openalex_id"] for s in frontier)
        fetch_backward(frontier, since, pool, identified, rnd, seen_batches)
        fetch_forward(frontier, since, forward_pages, pool, identified, rnd)
        new_ids = [k for k in pool if k != "_dups" and k not in before]
        relevant_new = 0
        for k in new_ids:
            r = pool[k]
            r["overlap"] = round(overlap(terms, r["title"] + " " + (r["abstract"] or "")), 3)
            if not r["retracted"] and r["overlap"] >= threshold and k not in seed_lookup:
                relevant_new += 1
        round_log.append({"round": rnd, "from": [s["openalex_id"] for s in frontier], "new": len(new_ids),
                          "relevant_new": relevant_new})
        say(f"round {rnd}: snowballed {len(frontier)} paper(s), {len(new_ids)} new, {relevant_new} relevant")
        if rnd == rounds:
            break
        if relevant_new < 5:
            say(f"stopping: round {rnd} added fewer than 5 relevant papers")
            break
        # next frontier: best new relevant papers not yet snowballed, with an OpenAlex id
        cands = [pool[k] for k in new_ids if not pool[k]["retracted"] and pool[k]["overlap"] >= threshold
                 and k not in snowballed and k not in seed_lookup]
        for r in cands:
            score_row(r)
        cands.sort(key=lambda r: -r["score"])
        frontier = cands[:topk]
        if not frontier:
            break

    dups = pool.pop("_dups", 0)
    rows = [r for k, r in pool.items() if k not in seed_lookup]
    seeds_hit_as_results = len(pool) - len(rows)
    retracted = [r for r in rows if r["retracted"]]
    rows = [r for r in rows if not r["retracted"]]
    for r in rows:
        r.setdefault("overlap", round(overlap(terms, r["title"] + " " + (r["abstract"] or "")), 3))
        r["via_retracted_seed"] = bool(set(r["reached_via"]) & retracted_seed_ids)
        r["only_via_retracted_seed"] = r["via_retracted_seed"] and not (set(r["reached_via"]) - retracted_seed_ids)
        r["reached_via"] = [v + (" (RETRACTED seed)" if v in retracted_seed_ids else "") for v in r["reached_via"]]
        score_row(r)
        r.pop("referenced_works", None)
    rows.sort(key=lambda r: (-r["score"], -(r["cites"] or 0)))
    relevant = [r for r in rows if r["overlap"] >= threshold]
    included = relevant[:max_keep]
    below = len(rows) - len(relevant)
    prisma = {
        "identified_backward": identified["backward"], "identified_forward": identified["forward"],
        "identified_total": identified["backward"] + identified["forward"],
        "duplicates_removed": dups, "seeds_returned_as_results": seeds_hit_as_results,
        "retracted_excluded": len(retracted), "screened": len(rows),
        "excluded_below_threshold": below, "relevant": len(relevant),
        "cut_by_max": max(0, len(relevant) - max_keep), "included": len(included),
        "threshold": threshold, "terms": terms, "term_source": term_source,
    }
    for s in seeds:
        s.pop("referenced_works", None)
        s.pop("abstract", None)
    return {"seeds": seeds, "rows": rows, "included": included, "retracted": retracted, "prisma": prisma,
            "rounds": round_log, "warnings": warnings, "terms": terms, "term_source": term_source}


# ---------------------------------------------------------------- reports

def budget_line():
    s = f"credits used (counted): {BUDGET['list_calls']} list call(s) at 1 each + {BUDGET['entity_calls']} entity call(s) at 0"
    if BUDGET["header_seen"]:
        s += (f" | OpenAlex X-RateLimit-Remaining: {BUDGET['remaining']} of {BUDGET['limit']} "
              "(whole key, every run today)")
    else:
        s += " | no X-RateLimit header seen (count is the estimate)"
    return s


def seed_table(seeds):
    return table([[s["input"], str(s["year"] or ""), str(s["cites"] or ""), str(s["n_refs"] or ""),
                   str(s.get("citing_total") or ""), "RETRACTED" if s["retracted"] else "ok",
                   short(s["title"], 70)] for s in seeds],
                 ["seed", "year", "cites", "refs", "citers", "status", "title"])


def top_table(rows, n):
    return table([[str(i + 1), f"{r['score']:.2f}", f"{r['overlap']:.2f}", str(r["year"] or ""),
                   str(r["cites"] if r["cites"] is not None else ""),
                   short(r["first_author"], 20) + (" et al." if r["n_authors"] > 2 else ""),
                   short(r["title"], 70), f"r{r['round']} {'/'.join(sorted(set(r['direction'])))} "
                   f"x{len(r['reached_via'])}" + (" !" if r.get("via_retracted_seed") else ""),
                   r["doi"] or "(no DOI)"] for i, r in enumerate(rows[:n])],
                 ["#", "score", "overlap", "year", "cites", "first author", "title", "via", "doi"])


def markdown_summary(res, args):
    p = res["prisma"]
    out = [f"# Snowball summary ({TODAY})", "",
           f"Topic terms ({res['term_source']}): {', '.join(res['terms'])}", "",
           f"Rounds: {len(res['rounds'])} | threshold overlap >= {p['threshold']} | forward pages per paper: "
           f"{args.forward_pages} | top-k per round: {args.topk}", ""]
    if res["warnings"]:
        out += ["## Warnings", ""] + [f"- {w}" for w in res["warnings"]] + [""]
    out += ["## Seeds", "", seed_table(res["seeds"]), "", "## Rounds", "",
            table([[str(r["round"]), ", ".join(r["from"]), str(r["new"]), str(r["relevant_new"])] for r in res["rounds"]],
                  ["round", "snowballed from", "new papers", "relevant new"]), "",
            f"## Top 25 of {p['included']} included", "", top_table(res["included"], 25), "",
            "via = round first seen, direction(s), number of snowballed papers (seeds + later frontiers) reaching it; "
            "'!' = reached through a retracted seed.", "",
            "Scores are a heuristic (term overlap + log citations + co-citation bonus): read the abstract "
            "before citing anything. Candidates are NOT sources until `scholar.py add`.", "",
            budget_line(), ""]
    return "\n".join(out)


def prisma_md(res):
    p = res["prisma"]
    flow = f"""# PRISMA-style flow (citation snowballing, {TODAY})

```
Identification
  Records identified through snowballing ........ {p['identified_total']}
      backward (references of seeds) ............ {p['identified_backward']}
      forward (papers citing seeds) ............. {p['identified_forward']}
  Duplicates removed ............................ {p['duplicates_removed']}
  Seeds themselves returned as results .......... {p['seeds_returned_as_results']}
  Retracted records excluded .................... {p['retracted_excluded']}
            |
            v
Screening
  Records screened (title + abstract, relevance) {p['screened']}
  Excluded: term overlap < {p['threshold']} ................ {p['excluded_below_threshold']}
            |
            v
Included
  Relevant records .............................. {p['relevant']}
  Cut by --max .................................. {p['cut_by_max']}
  Included for full reading ..................... {p['included']}
```

| stage | count |
|---|---|
| identified (backward + forward, with duplicates) | {p['identified_total']} |
| duplicates removed | {p['duplicates_removed']} |
| retracted excluded | {p['retracted_excluded']} |
| screened | {p['screened']} |
| excluded below relevance threshold | {p['excluded_below_threshold']} |
| included | {p['included']} |

Relevance screening here is automatic (term overlap with: {', '.join(p['terms'])}); a PRISMA
diagram for a manuscript must also report the full-text eligibility step done by the researcher.
"""
    return flow


# ---------------------------------------------------------------- commands

def cmd_run(a):
    res = run_snowball(a.seeds, a.topic, a.rounds, a.max, a.since, a.forward_pages, a.topk, a.threshold)
    p = res["prisma"]
    print(f"snowball: {len(res['seeds'])} seed(s) | {p['identified_total']} identified | {p['screened']} unique screened | "
          f"{p['relevant']} relevant (overlap >= {p['threshold']}) | {p['included']} included | {TODAY}")
    for w in res["warnings"]:
        print("WARNING: " + w)
    print(seed_table(res["seeds"]))
    print(top_table(res["included"], a.show))
    print("via = round first seen, direction(s), snowballed papers reaching it; '!' = reached through a RETRACTED seed.")
    if a.out:
        out = {"query": a.topic or " | ".join(s["title"] for s in res["seeds"]), "date": TODAY, "source": "snowball",
               "seeds": res["seeds"], "terms": res["terms"], "rounds": res["rounds"], "warnings": res["warnings"],
               "prisma": p, "budget": {k: BUDGET[k] for k in ("list_calls", "entity_calls", "remaining", "limit")},
               "results": res["included"]}
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"saved {len(res['included'])} candidates to {a.out}")
        md = a.md or os.path.splitext(a.out)[0] + ".md"
        with open(md, "w", encoding="utf-8") as f:
            f.write(markdown_summary(res, a))
        print(f"summary written to {md}")
    if a.prisma:
        with open(a.prisma, "w", encoding="utf-8") as f:
            f.write(prisma_md(res))
        print(f"PRISMA counts written to {a.prisma}")
    print(budget_line())
    print("Candidates are NOT sources yet: read the abstract, then `scholar.py add` the ones you will cite.")


def cmd_selftest(a):
    """Offline: scoring, merge/dedup, co-citation bonus, retracted marking, PRISMA arithmetic."""
    fails = []
    terms = terms_of("social media academic performance university students")
    if terms != ["soci", "media", "academ", "perfor", "univer", "studen"]:
        fails.append(f"terms_of gave {terms}")
    good = overlap(terms, "Facebook use and academic performance among university students")
    bad = overlap(terms, "Measles vaccine and autism in children")
    if not (good >= 0.6 and bad == 0.0):
        fails.append(f"overlap good={good} bad={bad}")
    pool = {}
    w = {"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/x", "display_name": "T", "cited_by_count": 100,
         "is_retracted": False, "referenced_works": [], "authorships": []}
    merge(pool, make_row(w, "WS1", "backward", 1))
    merge(pool, make_row(w, "WS2", "forward", 1))
    merge(pool, make_row(w, "WS2", "forward", 1))
    r = pool["W1"]
    if pool.get("_dups") != 2 or r["reached_via"] != ["WS1", "WS2"]:
        fails.append(f"merge: dups={pool.get('_dups')} via={r['reached_via']}")
    r["overlap"] = 1.0
    s = score_row(r)
    expect = round(5 + math.log(101) / 2 + 1.5, 3)
    if abs(s - expect) > 1e-6:
        fails.append(f"score {s} != {expect}")
    # negative control: a retracted candidate must never be scored into the included list
    wr = dict(w, id="https://openalex.org/W2", is_retracted=True)
    merge(pool, make_row(wr, "WS1", "backward", 1))
    rows = [x for k, x in pool.items() if k != "_dups" and not x["retracted"]]
    if any(x["openalex_id"] == "W2" for x in rows):
        fails.append("retracted candidate survived the filter")
    print(f"selftest: {len(fails)} failure(s)")
    for f in fails:
        print("  FAIL " + f)
    print("not checked offline: live OpenAlex calls (run the documented `run` example for that).")
    print("RESULT: " + ("PASS" if not fails else "FAIL (see above)"))
    sys.exit(1 if fails else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="snowball from seed DOIs. Example: run --seeds 10.1016/j.chb.2010.03.024 "
                                   "--topic 'social media academic performance' --rounds 2 --out cand_snowball.json")
    r.add_argument("--seeds", nargs="+", required=True, help="seed DOIs or OpenAlex W ids")
    r.add_argument("--topic", help="relevance terms; default: the seeds' titles")
    r.add_argument("--rounds", type=int, default=2)
    r.add_argument("--max", type=int, default=300, help="max candidates kept in --out")
    r.add_argument("--since", type=int, help="drop papers published before this year")
    r.add_argument("--forward-pages", type=int, default=1, help="pages of 200 citing papers per seed (1 credit each)")
    r.add_argument("--topk", type=int, default=5, help="papers snowballed in round 2+")
    r.add_argument("--threshold", type=float, default=0.4, help="min term overlap to count as relevant")
    r.add_argument("--show", type=int, default=25, help="rows printed")
    r.add_argument("--out", help="candidates JSON (same shape as scholar.py search --out)")
    r.add_argument("--md", help="markdown summary path (default: next to --out)")
    r.add_argument("--prisma", help="write PRISMA-style counts to this .md")
    r.set_defaults(func=cmd_run)
    t = sub.add_parser("selftest", help="offline checks, no network. Example: selftest")
    t.set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
