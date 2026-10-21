#!/usr/bin/env python3
"""instruments.py - validated scales instead of home-made questionnaires.

A thesis committee asks "why did you write your own items?" before it asks
anything else about a survey. This tool finds published, validated scales
for a construct, checks a pilot run item by item, and prints the
translation / adaptation protocol the Methods section can cite.

Commands
  find      OpenAlex search for validation / psychometric papers on a construct
            (2 list searches: one general, one for Arabic versions), ranked by
            citations, with items / subscales / alpha / CR / languages / sample
            pulled from the abstracts by regex and labelled as CANDIDATES
  pilot     item analysis of a pilot CSV: item M / SD, corrected item-total r,
            alpha if item deleted, floor / ceiling, alpha, recommendations
  protocol  the back-translation + adaptation checklist (Brislin 1970; Beaton
            et al. 2000; Sousa & Rojjanasrirat 2011), each source DOI verified
            through Crossref at run time and printed only when it resolves

Examples
  python -X utf8 instruments.py find --construct "transformational leadership" --since 2000 --out instruments.md
  python -X utf8 instruments.py pilot data.csv --items q1 q2 q3 q4 --reverse q3 >> analysis/output.txt
  python -X utf8 instruments.py protocol --construct "job satisfaction" --scale "JSS (Spector, 1985)" --from en --to ar

Every number printed by `find` is a regex extraction from an abstract: confirm
it in the full text before it reaches the thesis. Nothing here is a source
until it is `scholar.py add`ed.
"""

import argparse
import csv
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scholar import (openalex, oa_row, resolve_doi, HTTPError, clean, short, table, apa, TODAY)   # noqa: E402

try:
    import numpy as np
except ImportError:
    sys.exit("numpy is needed: pip install numpy")

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


# ---------------------------------------------------------------- find

LANGS = ["Arabic", "Spanish", "Chinese", "French", "German", "Turkish", "Persian", "Farsi", "Portuguese",
         "Italian", "Japanese", "Korean", "Malay", "Indonesian", "Urdu", "Hindi", "Greek", "Polish", "Dutch",
         "Swedish", "Norwegian", "Danish", "Finnish", "Hebrew", "Thai", "Vietnamese", "Russian", "Hungarian",
         "Czech", "Romanian", "Serbian", "Croatian", "Bengali", "Tamil", "Swahili", "Amharic", "Kurdish"]
_DEC = r"(0?\.\d{2,3})"
ALPHA_RE = re.compile(r"(?:cronbach'?s?\s*)?(?:alpha|α)\s*(?:coefficients?|values?|reliabilit(?:y|ies))?\s*"
                      r"(?:of|=|was|were|is|are|ranged|ranging|from|between|:|at)?\s*(?:from\s*|between\s*)?"
                      + _DEC + r"(?:\s*(?:to|and|-|\u2013)\s*" + _DEC + r")?", re.I)
CR_RE = re.compile(r"composite reliabilit(?:y|ies)\s*(?:\(CR\))?\s*(?:coefficients?|values?)?\s*"
                   r"(?:of|=|was|were|is|are|ranged|ranging|from|between|:|above|exceeded|>)?\s*(?:from\s*)?"
                   + _DEC + r"(?:\s*(?:to|and|-|\u2013)\s*" + _DEC + r")?", re.I)
ITEMS_RE = re.compile(r"\b(\d{1,3})\s*[- ]\s*items?\b", re.I)
SUBSCALE_RE = re.compile(r"\b(\d{1,2}|two|three|four|five|six|seven|eight|nine|ten)\s*[- ]?\s*"
                         r"(sub-?scales?|sub-?dimensions?|factors?|dimensions?|components?)\b", re.I)
SAMPLE_RE = re.compile(r"\b[nN]\s*=\s*(\d[\d,]{1,6})\b"
                       r"|\b(\d[\d,]{1,6})\s+(?:[a-z\-]+\s+){0,3}(?:participants|respondents|employees|nurses|"
                       r"students|teachers|workers|patients|managers|adults|individuals|subjects|leaders|"
                       r"followers|staff|physicians|customers|users|adolescents|athletes|officers|faculty)\b"
                       r"|\bsample of\s+(\d[\d,]{1,6})\b", re.I)
SCALE_TITLE = re.compile(r"\b(scale|questionnaire|inventory|measure|measuring|measurement|index|survey|instrument|"
                         r"validation|validating|validity|psychometric|reliability|adaptation|version|short form)\b", re.I)
WORD_NUM = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def _nums(matches):
    vals = []
    for m in matches:
        for g in m.groups():
            if g:
                try:
                    v = float(g)
                except ValueError:
                    continue
                if 0 < v <= 1:
                    vals.append(v)
    return vals


def _range(vals):
    if not vals:
        return ""
    lo, hi = f"{min(vals):.2f}", f"{max(vals):.2f}"
    return lo if lo == hi else f"{lo}-{hi}"


def extract(abstract):
    """Regex candidates from one abstract. Every field may be wrong: the agent confirms in the full text."""
    t = clean(abstract)
    items = [int(m.group(1)) for m in ITEMS_RE.finditer(t) if 2 <= int(m.group(1)) <= 300]
    subs = []
    for m in SUBSCALE_RE.finditer(t):
        g = m.group(1).lower()
        n = WORD_NUM.get(g) or (int(g) if g.isdigit() else None)
        if n and 2 <= n <= 20:
            subs.append(n)
    sample = []
    for m in SAMPLE_RE.finditer(t):
        g = next((x for x in m.groups() if x), None)
        if g:
            n = int(g.replace(",", ""))
            if 10 <= n <= 1_000_000:
                sample.append(n)
    langs = [L for L in LANGS if re.search(r"\b" + L + r"\b", t, re.I)]
    return {
        "items": items[0] if items else None,
        "subscales": subs[0] if subs else None,
        "alpha": _range(_nums(ALPHA_RE.finditer(t))),
        "cr": _range(_nums(CR_RE.finditer(t))),
        "languages": langs,
        "arabic": bool(re.search(r"\barabic\b", t, re.I)),
        "sample": max(sample) if sample else None,
    }


def oa_search(title_q, query, a, extra_filters=()):
    """One OpenAlex list call (10 credits): construct in the title, method words anywhere."""
    filters = ["is_retracted:false", f"title.search:{title_q}", f"title_and_abstract.search:{query}"] + list(extra_filters)
    if a.since:
        filters.append(f"from_publication_date:{a.since}-01-01")
    params = {"filter": ",".join(filters), "per_page": min(a.limit, 100), "sort": "cited_by_count:desc",
              "select": "id,doi,display_name,publication_year,cited_by_count,primary_location,authorships,"
                        "type,open_access,is_retracted,abstract_inverted_index,language"}
    data = openalex("works", params) or {}
    rows = []
    for w in data.get("results", []):
        r = oa_row(w)
        r["language"] = w.get("language")
        r["scale_title"] = bool(SCALE_TITLE.search(r["title"]))
        r.update(extract(r["abstract"]))
        rows.append(r)
    # OpenAlex sorted by citations; within that, titles that name a scale or a validation come first.
    rows.sort(key=lambda r: (not r["scale_title"], -(r["cites"] or 0)))
    return rows, (data.get("meta") or {}).get("count", 0)


def cand_table(rows):
    body = []
    for i, r in enumerate(rows, 1):
        langs = ",".join(r["languages"][:4]) + ("+" if len(r["languages"]) > 4 else "")
        body.append([str(i), str(r["year"] or ""), str(r["cites"] if r["cites"] is not None else ""),
                     short(r["first_author"], 18) + (" et al." if r["n_authors"] > 2 else ""),
                     short(r["title"], 70),
                     str(r["items"] or "?"), str(r["subscales"] or "?"), r["alpha"] or "?", r["cr"] or "?",
                     (langs or "?") + (" AR" if r["arabic"] else ""),
                     str(r["sample"] or "?"),
                     ("scale paper?" if r["scale_title"] else "uses it only?")
                     + ("; no abstract" if not r["abstract"] else ""),
                     r["doi"] or "(no DOI)"])
    return table(body, ["#", "year", "cites", "first author", "title", "items", "subscales", "alpha", "CR",
                        "languages", "n", "note", "doi"])


def cmd_find(a):
    c = a.construct.strip().strip('"')
    q1 = '(scale OR questionnaire OR inventory OR measure) AND (validation OR psychometric OR reliability OR development)'
    q2 = 'Arabic AND (validation OR translation OR adaptation)'
    lines = [f"# Instrument candidates: {c} | OpenAlex | {TODAY}", ""]
    main, total = oa_search(f'"{c}"', q1, a)
    lines.append(f"Search 1 (validation / psychometric papers): title has \"{c}\", title or abstract has `{q1}` | "
                 f"total matches: {total} | shown: {len(main)}" + (f" | since {a.since}" if a.since else ""))
    if not main:
        lines.append("")
        lines.append(f"NOT FOUND: OpenAlex has no validation, psychometric or scale-development paper whose title or "
                     f"abstract contains \"{c}\". Either the construct is named differently in the literature "
                     f"(try a synonym, the theory's own term, or the English name of an Arabic construct), or no "
                     f"validated scale exists yet. Do not build items until a second search with synonyms also "
                     f"returns nothing; then a new scale needs a development study (item pool, expert review, "
                     f"EFA then CFA on separate samples), not a thesis questionnaire written in an afternoon.")
    else:
        lines += ["", cand_table(main), ""]
    arab, total2 = oa_search(f'"{c}"', q2, a)
    lines.append(f"Search 2 (Arabic versions): title has \"{c}\", title or abstract has `{q2}` | "
                 f"total matches: {total2} | shown: {len(arab)}")
    if arab:
        lines += ["", cand_table(arab)]
    else:
        lines.append("No Arabic validation or translation paper found: an Arabic study needs the `protocol` "
                     "command (forward + back translation, committee, cognitive interviews, pilot).")
    lines += ["",
              "Rows whose title names a scale, measure or validation are listed first ('scale paper?'); the others "
              "probably only USE a scale for this construct and are worth opening for the instrument they cite. "
              "All rows are CANDIDATES. items / subscales / alpha / CR / languages / n are regex extractions "
              "from the abstract ('?' = not stated in the abstract, 'no abstract' = nothing to extract): open the "
              "full text, confirm the figures, then `scholar.py add <doi> --note \"instrument: ...\"` the ones you "
              "cite. Most-cited is not best: prefer the ORIGINAL development paper plus one independent validation, "
              "and check the licence (references/instruments.md) before you copy any item."]
    text = "\n".join(lines)
    print(text)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
        print(f"saved {a.out}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"query": q1, "query_arabic": q2, "date": TODAY, "source": "openalex",
                       "construct": c, "results": main, "results_arabic": arab}, f, ensure_ascii=False, indent=1)
        print(f"saved candidates JSON to {a.json}")
    return 0 if main else 1


# ---------------------------------------------------------------- pilot

def load_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.DictReader(f, dialect=dialect))
    if not rows:
        sys.exit("empty file")
    return rows


def num(v):
    try:
        return float(str(v).strip().replace(",", ".")) if str(v).strip() != "" else math.nan
    except ValueError:
        return math.nan


def fmt(x):
    if isinstance(x, float):
        return f"{x:.6f}".rstrip("0").rstrip(".") if x == x else "nan"
    return str(x)


def ev(key, value):
    print(f"{key} = {fmt(value)}")


def cronbach(m):
    k = m.shape[1]
    if k < 2:
        return math.nan
    tv = m.sum(axis=1).var(ddof=1)
    return k / (k - 1) * (1 - m.var(axis=0, ddof=1).sum() / tv) if tv > 0 else math.nan


def cmd_pilot(a):
    rows = load_csv(a.csv)
    missing = [c for c in a.items if c not in rows[0]]
    if missing:
        sys.exit(f"unknown column(s): {', '.join(missing)}. Available: {', '.join(rows[0].keys())}")
    bad_rev = [c for c in a.reverse if c not in a.items]
    if bad_rev:
        sys.exit(f"--reverse names columns that are not in --items: {', '.join(bad_rev)}")
    m = np.array([[num(r[c]) for c in a.items] for r in rows], dtype=float)
    keep = ~np.isnan(m).any(axis=1)
    m, dropped = m[keep], int((~keep).sum())
    n, k = m.shape
    if n < 3 or k < 2:
        sys.exit("pilot needs at least 3 complete rows and 2 items")
    lo = a.min if a.min is not None else float(np.nanmin(m))
    hi = a.max if a.max is not None else float(np.nanmax(m))
    if a.min is None or a.max is None:
        print(f"# scale range taken from the data: {fmt(lo)} to {fmt(hi)} (pass --min/--max for the printed range)")
    out_of_range = int(((m < lo) | (m > hi)).sum())
    for j, c in enumerate(a.items):
        if c in a.reverse:
            m[:, j] = lo + hi - m[:, j]
    print(f"# pilot {' '.join(a.items)} | file {a.csv} | rows {n} complete, {dropped} dropped (missing)"
          + (f" | reverse-coded: {', '.join(a.reverse)}" if a.reverse else ""))
    if out_of_range:
        print(f"# WARNING: {out_of_range} value(s) outside {fmt(lo)}-{fmt(hi)}: check the coding before trusting anything below")
    al = cronbach(m)
    total = m.sum(axis=1)
    corr = np.corrcoef(m, rowvar=False)
    off = corr[~np.eye(k, dtype=bool)]
    mean_r = float(np.nanmean(off))
    # Keys end in the statistic symbol (r, alpha, pct) so `scholar.py numbers` matches each value to its own label.
    ev("pilot.n", n)
    ev("pilot.items", k)
    ev("pilot.alpha", float(al))
    ev("pilot.mean_inter_item.r", mean_r)
    recs, body = [], []
    for j, c in enumerate(a.items):
        x = m[:, j]
        rest = total - x
        sd = float(x.std(ddof=1))
        r_it = float(np.corrcoef(x, rest)[0, 1]) if sd > 0 and rest.std(ddof=1) > 0 else math.nan
        al_del = cronbach(np.delete(m, j, axis=1)) if k > 2 else math.nan
        floor = float((x <= lo).mean() * 100)
        ceil = float((x >= hi).mean() * 100)
        ev(f"pilot.{c}.m", float(x.mean()))
        ev(f"pilot.{c}.sd", sd)
        ev(f"pilot.{c}.item_total.r", r_it)
        ev(f"pilot.{c}.alpha_if_deleted.alpha", float(al_del))
        ev(f"pilot.{c}.floor.pct", floor)
        ev(f"pilot.{c}.ceiling.pct", ceil)
        flags = []
        if sd == 0:
            flags.append("no variance: drop or rewrite")
        elif r_it != r_it:
            flags.append("item-total r undefined")
        elif r_it < 0:
            flags.append("negative item-total r: reverse-code check" + (" (already reversed: wording problem)" if c in a.reverse else ""))
        elif r_it < 0.30:
            flags.append(f"item-total r {r_it:.2f} < .30: drop candidate")
        if al_del == al_del and al == al and al_del > al + 0.01:
            flags.append(f"alpha rises to {al_del:.2f} without it")
        if floor > 15:
            flags.append(f"floor {floor:.0f}% at {fmt(lo)}")
        if ceil > 15:
            flags.append(f"ceiling {ceil:.0f}% at {fmt(hi)}")
        verdict = "keep" if not flags else ("drop" if any(f.startswith(("item-total r", "no variance")) for f in flags)
                                            else "check")
        recs.append((c, verdict, "; ".join(flags) or "fine"))
        body.append([c, f"{x.mean():.2f}", f"{sd:.2f}", f"{r_it:.2f}" if r_it == r_it else "nan",
                     f"{al_del:.2f}" if al_del == al_del else "n/a", f"{floor:.0f}%", f"{ceil:.0f}%", verdict])
    print("# " + table(body, ["item", "M", "SD", "item-total r", "alpha if deleted", "floor", "ceiling",
                              "verdict"]).replace("\n", "\n# "))
    a_txt = f"{al:.2f}".replace("0.", ".", 1) if al == al else "nan"
    print(f"# APA: Cronbach's α = {a_txt} ({k} items, n = {n}); mean inter-item r = {mean_r:.2f}")
    if n < 30:
        print(f"# WARNING: pilot n = {n} < 30: item statistics are unstable, treat every verdict as provisional")
    if al == al and al < 0.70:
        print(f"# WARNING: alpha {al:.2f} < .70 (Nunnally's floor for research use): revise before the main study")
    elif al == al and al > 0.95:
        print(f"# WARNING: alpha {al:.2f} > .95: items may be redundant (near-duplicates), consider shortening")
    print("# Recommendations (corrected item-total r < .30 = drop candidate; negative r = reverse-coding or wording;"
          " floor/ceiling > 15% = restricted range):")
    for c, v, why in recs:
        print(f"#   {c}: {v.upper()} ({why})")
    print("# A pilot decides wording and reverse-coding only. Keep every published item of a validated scale unless "
          "the authors allow shortening; report the pilot alpha and the main-study alpha separately.")
    return 0


# ---------------------------------------------------------------- protocol

# Standard sources for the method. Each DOI is resolved through Crossref at run
# time and printed only when it resolves; nothing here is cited from memory.
PROTOCOL_SOURCES = [
    ("brislin1970", "10.1177/135910457000100301", "back-translation method"),
    ("beaton2000", "10.1097/00007632-200012150-00014", "six-stage cross-cultural adaptation guidelines"),
    ("sousa2011", "10.1111/j.1365-2753.2010.01434.x", "translation, adaptation and validation guideline"),
    ("guillemin1993", "10.1016/0895-4356(93)90142-N", "original cross-cultural adaptation guidelines"),
]

LANG_NAMES = {"en": "English", "ar": "Arabic", "fr": "French", "de": "German", "es": "Spanish", "tr": "Turkish",
              "fa": "Persian", "ur": "Urdu", "ms": "Malay", "id": "Indonesian", "zh": "Chinese", "pt": "Portuguese"}


def verify_sources():
    ok, bad = [], []
    for key, doi, role in PROTOCOL_SOURCES:
        try:
            rec, verdict = resolve_doi(doi)
        except HTTPError as e:
            rec, verdict = None, f"network error ({e.status})"
        if rec and (rec.get("retraction") or {}).get("status") in ("ok", "corrected", "unknown"):
            ok.append((key, doi, role, rec))
        else:
            bad.append((key, doi, role, verdict if not rec else rec["retraction"]["status"]))
    return ok, bad


def cmd_protocol(a):
    src, tgt = LANG_NAMES.get(a.src, a.src), LANG_NAMES.get(a.dst, a.dst)
    ok, bad = verify_sources()
    cite = {k: f"{r['authors'][0]['family']}" + (" et al." if len(r["authors"]) > 2 else
            (" & " + r["authors"][1]["family"] if len(r["authors"]) == 2 else "")) + f" ({r['year']})"
            for k, _, _, r in ok}
    c = lambda k: cite.get(k, "[source not verified: do not cite]")
    cp = lambda *ks: "; ".join(c(k).replace(" (", ", ").rstrip(")") for k in ks)     # parenthetical form
    L = [f"# Translation and cultural adaptation protocol: {a.scale} for \"{a.construct}\" ({src} to {tgt}) | {TODAY}",
         "",
         "Method basis: " + ("; ".join(f"{c(k)} ({role})" for k, _, role, _ in ok) if ok else "NO SOURCE VERIFIED"),
         "",
         "## Checklist (tick each step in the thesis appendix; the Methods paragraph cites the steps, not the ticks)",
         "",
         f"- [ ] 0. Permission: written permission or licence from the scale's copyright holder to translate "
         f"{a.scale} into {tgt} (keep the email / licence PDF in the appendix). Check references/instruments.md.",
         f"- [ ] 1. Forward translation ({src} to {tgt}) by TWO independent bilingual translators whose mother "
         f"tongue is {tgt}: one familiar with the construct (informed), one naive to it ({cp('beaton2000')}). "
         f"Each writes a short report on difficult phrases.",
         f"- [ ] 2. Reconciliation: the two forward versions are merged into one {tgt} version (T12) in a recorded "
         f"meeting; every disagreement and its resolution is written down ({cp('beaton2000')}).",
         f"- [ ] 3. Back-translation ({tgt} to {src}) by a translator blind to the original, mother tongue {src} "
         f"({cp('brislin1970', 'beaton2000')}). Two back-translators when the budget allows.",
         f"- [ ] 4. Expert committee (methodologist, subject expert, language professional, all translators) compares "
         f"original, forward, reconciled and back-translated versions and reaches semantic, idiomatic, "
         f"experiential and conceptual equivalence; produces the pre-final version "
         f"({cp('guillemin1993', 'beaton2000')}).",
         f"- [ ] 5. Cognitive interviews / pre-test with 5 to 10 respondents from the target population "
         f"(think-aloud or probing on each item: what does this item ask you?); items misunderstood by any "
         f"respondent go back to the committee ({cp('beaton2000', 'sousa2011')}).",
         f"- [ ] 6. Pilot with n >= 30 from the target population: `instruments.py pilot pilot.csv --items ...` "
         f"for item-total correlations, alpha, floor/ceiling; revise, never delete published items without "
         f"the author's agreement ({cp('sousa2011')}).",
         f"- [ ] 7. Main study psychometrics: Cronbach's alpha (and CR / AVE when CFA is run) per subscale, "
         f"CFA of the original factor structure, and the evidence lines written to analysis/output.txt "
         f"({cp('sousa2011')}).",
         f"- [ ] 8. Report: the Methods section names every step, who did it (qualifications, not names), the "
         f"number of respondents at steps 5 and 6, what changed and why, and the licence. Submit the {tgt} "
         f"version and the back-translation as appendices.",
         "",
         "## Methods paragraph (fill the brackets; keep only verified citations)",
         "",
         f"The {a.scale} was translated from {src} into {tgt} following the back-translation procedure of "
         f"{c('brislin1970')} and the cross-cultural adaptation guidelines of {c('beaton2000')}. Two bilingual "
         f"translators produced independent forward translations, which were reconciled into a single version. "
         f"A third translator, blind to the original, back-translated this version into {src}. An expert committee "
         f"of [k] members compared all versions and resolved discrepancies to reach semantic and conceptual "
         f"equivalence. The pre-final version was pre-tested in cognitive interviews with [5-10] [population], "
         f"after which [n] items were reworded, and piloted with [n >= 30] [population] (Cronbach's alpha = [ ]). "
         f"Permission to translate and use the instrument was obtained from [copyright holder] on [date].",
         ]
    if a.dst == "ar" or a.src == "ar":
        L += ["",
              "## فقرة المنهجية (عربي)",
              "",
              f"تمت ترجمة مقياس {a.scale} من {('الإنجليزية' if a.src == 'en' else src)} إلى العربية وفق إجراء الترجمة "
              f"العكسية ({cp('brislin1970')}) وإرشادات التكييف عبر الثقافات ({cp('beaton2000')}). أعد مترجمان "
              f"ثنائيا اللغة ترجمتين أماميتين مستقلتين دُمجتا في نسخة واحدة، ثم أعاد مترجم ثالث لا يعرف النسخة "
              f"الأصلية ترجمتها إلى اللغة الأصلية. قارنت لجنة من الخبراء مكونة من [ك] أعضاء جميع النسخ وحلّت "
              f"الاختلافات للوصول إلى التكافؤ الدلالي والمفاهيمي. اختُبرت النسخة شبه النهائية بمقابلات معرفية "
              f"مع [5-10] من [المجتمع المستهدف] وعُدّلت صياغة [ن] فقرات، ثم طُبقت تجريبيا على [ن >= 30] من "
              f"[المجتمع المستهدف] (معامل ألفا كرونباخ = [ ]). وحُصل على إذن الترجمة والاستخدام من [مالك حقوق "
              f"المقياس] بتاريخ [التاريخ].",
              ]
    L += ["", "## Sources (resolved through Crossref today; add them with `scholar.py add <doi>` before citing)", ""]
    for k, doi, role, rec in ok:
        L.append(f"- {k}: {apa(rec)}")
    for k, doi, role, why in bad:
        L.append(f"- {k}: UNVERIFIED ({why}) for https://doi.org/{doi}: NOT cited above; run "
                 f"`scholar.py verify {doi}` and only then add it")
    L += ["", f"RESULT: {'PASS' if ok and not bad else 'FAIL'} ({len(ok)} of {len(PROTOCOL_SOURCES)} method sources verified)"]
    text = "\n".join(L)
    print(text)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
        print(f"saved {a.out}")
    return 0 if ok and not bad else 1


# ---------------------------------------------------------------- selftest

def cmd_selftest(a):
    """Offline checks of the regex extraction and the pilot maths (no network)."""
    fails = 0
    ab = ("The 20-item scale with four subscales was validated in a sample of 412 nurses (N = 412). "
          "Cronbach's alpha ranged from .78 to .91 and composite reliability was 0.84. "
          "An Arabic version and a Turkish version are available.")
    e = extract(ab)
    exp = {"items": 20, "subscales": 4, "alpha": "0.78-0.91", "cr": "0.84", "arabic": True, "sample": 412}
    for k, v in exp.items():
        if e[k] != v:
            print(f"FAIL extract.{k}: got {e[k]!r}, expected {v!r}")
            fails += 1
    if "Turkish" not in e["languages"]:
        print("FAIL extract.languages: Turkish missing")
        fails += 1
    e0 = extract("A qualitative study of leadership narratives.")
    if any([e0["items"], e0["subscales"], e0["alpha"], e0["cr"], e0["sample"], e0["arabic"]]):
        print(f"FAIL extract on plain abstract should be empty: {e0}")
        fails += 1
    # pilot maths: three parallel items + one pure-noise item; the noise item must be the drop candidate
    rng = np.random.default_rng(7)
    base = rng.normal(0, 1, 60)
    m = np.column_stack([np.clip(np.round(3 + base + rng.normal(0, .5, 60)), 1, 5) for _ in range(3)]
                        + [np.clip(np.round(rng.uniform(1, 5, 60)), 1, 5)])
    al = cronbach(m)
    al_del = cronbach(m[:, :3])
    r_noise = float(np.corrcoef(m[:, 3], m[:, :3].sum(axis=1))[0, 1])
    if not (al_del > al and r_noise < 0.30):
        print(f"FAIL pilot maths: alpha {al:.2f}, without noise item {al_del:.2f}, noise item-total r {r_noise:.2f}")
        fails += 1
    print(f"selftest: extraction {'ok' if fails == 0 else 'FAILED'}; pilot maths alpha={al:.2f} -> {al_del:.2f} "
          f"without the noise item (item-total r = {r_noise:.2f})")
    print(f"RESULT: {'PASS' if fails == 0 else 'FAIL'} ({fails} failures; network commands not exercised here)")
    return 1 if fails else 0


# ---------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("find", help="validated scales for a construct (OpenAlex, 2 searches = 20 credits)",
                       epilog='example: find --construct "transformational leadership" --since 2000 --out instruments.md')
    f.add_argument("--construct", required=True, help='the construct in English, e.g. "job satisfaction"')
    f.add_argument("--since", type=int, help="earliest publication year")
    f.add_argument("--limit", type=int, default=25, help="rows per search (max 100)")
    f.add_argument("--out", help="save the report as markdown")
    f.add_argument("--json", help="also save the candidates in the cand*.json shape")

    pl = sub.add_parser("pilot", help="item analysis of a pilot CSV (evidence lines for analysis/output.txt)",
                        epilog="example: pilot data.csv --items q1 q2 q3 q4 --reverse q3 --min 1 --max 5")
    pl.add_argument("csv")
    pl.add_argument("--items", nargs="+", required=True, help="item columns in scale order")
    pl.add_argument("--reverse", nargs="*", default=[], help="items to reverse-code before analysis")
    pl.add_argument("--min", type=float, help="lowest response option (default: observed minimum)")
    pl.add_argument("--max", type=float, help="highest response option (default: observed maximum)")

    pr = sub.add_parser("protocol", help="back-translation / adaptation checklist with verified method sources",
                        epilog='example: protocol --construct "burnout" --scale "OLBI (Demerouti et al., 2003)" --from en --to ar')
    pr.add_argument("--construct", required=True)
    pr.add_argument("--scale", required=True, help='scale name and citation, e.g. "UWES-9 (Schaufeli et al., 2006)"')
    pr.add_argument("--from", dest="src", default="en", help="source language code (en)")
    pr.add_argument("--to", dest="dst", default="ar", help="target language code (ar)")
    pr.add_argument("--out", help="save the checklist as markdown")

    sub.add_parser("selftest", help="offline checks of the extraction regexes and the pilot maths")

    a = p.parse_args()
    try:
        rc = {"find": cmd_find, "pilot": cmd_pilot, "protocol": cmd_protocol, "selftest": cmd_selftest}[a.cmd](a)
    except HTTPError as e:
        sys.exit(f"network error: {e}")
    sys.exit(rc or 0)


if __name__ == "__main__":
    main()
