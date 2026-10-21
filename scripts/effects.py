#!/usr/bin/env python3
"""effects.py - effect sizes from the literature and a defensible sample size.

Commands
  harvest   regex-extract reported effect sizes (r, rho, beta, d, g, OR, R2, eta2, f2, f)
            from the abstracts in cand*.json files and/or the source ledger, with the
            p-value, N, relation words, DOI and year next to each one. Every hit is a
            CANDIDATE: confirm it in the abstract before using it.
  power     required N with scipy (correlation: Fisher z, with the exact bivariate-normal
            value as a cross-check; two-sample t: noncentral t; regression R2/f2/beta and
            one-way ANOVA: noncentral F; mediation: Monte Carlo power for the indirect
            effect ab), or the achieved power for a given --n. Warns when the effect size
            has no --source.
  justify   the Methods paragraph (EN + AR) that cites the ledger keys behind the effect
            size and the power parameters, plus evidence lines for analysis/output.txt
            (with --range the sensitivity table and its evidence lines too).
  selftest  planted abstracts (positive + negative control) and published power values.

Examples
  python -X utf8 effects.py harvest --in cand.json --ledger sources.jsonl --relation "sleep|GPA" --out effects.md --json effects.json
  python -X utf8 effects.py power --test corr --effect 0.3 --source "junco2012; lau2017"
  python -X utf8 effects.py power --test t --effect 0.5 --n 64 --source kolhar2021
  python -X utf8 effects.py power --test regression --effect 0.3 --effect-type beta --predictors 3 --source junco2012
  python -X utf8 effects.py power --test mediation --a 0.3 --b 0.3 --cprime 0.1 --sims 1000 --source "hayes2018"
  python -X utf8 effects.py justify --test regression --effect 0.15 --predictors 3 --source junco2012 --attrition 10 --evidence analysis/output.txt --append
  python -X utf8 effects.py justify --test corr --effect 0.3 --range "0.25,0.45" --label h1 --source junco2012
Needs numpy and scipy only. No network call is made by any command.
"""

import argparse
import contextlib
import io
import json
import math
import os
import re
import statistics
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scholar import clean, load_ledger, norm_doi, short, table, TODAY, ARABIC_RE  # noqa: E402

try:
    import numpy as np
    from scipy import integrate, special, stats
except ImportError:
    sys.exit("numpy and scipy are needed: pip install numpy scipy")

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

CANDIDATE = "candidate, confirm in the abstract"
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫", "01234567890123456789.")
NO_ABSTRACTS = "no abstracts in {file}: rerun scholar.py search with --out (abstracts are saved with --out)"

# ---------------------------------------------------------------- harvest: patterns

# A number as abstracts write it: .31, 0.31, -0.31, 0,554 (decimal comma), 1.8, 2
VAL = r"(-?\s?(?:\d+[.,]\d+|[.,]\d+|\d+(?![.,]\d)))"
EQ = r"\s*(?:=|:)\s*"
DF = r"\s*(?:\(\s*\d+\s*\))?"                      # r(197) = .31

# Order matters: the first pattern that covers a span wins (R2 before r, rho before r).
EFFECT_PATTERNS = [
    ("r2", re.compile(r"(?:(?:adjusted|adj\.?|Δ|delta)\s*)?(?<![A-Za-z])[Rr]\s*(?:2|²|\^2|-squared)" + EQ + VAL)),
    ("f2", re.compile(r"(?:Cohen'?s?\s+)?(?<![A-Za-z])f\s*(?:2|²|\^2)" + EQ + VAL)),
    ("eta2", re.compile(r"(?:(?:partial\s+)?eta\s*(?:2|²|\^2|squared)|η\s*(?:p|²p|p²|2|²|\^2)?\s*(?:2|²)?)" + EQ + VAL)),
    ("rho", re.compile(r"(?:ρ|(?<![A-Za-z])rho|(?<![A-Za-z])r[_\s]?s|Spearman'?s?\s+(?:rho|ρ|r|correlation(?:\s+coefficient)?))"
                       + DF + EQ + VAL)),
    ("r", re.compile(r"(?:Pearson'?s?\s+(?:r|correlation(?:\s+coefficient)?)|(?<![A-Za-z])r)" + DF + EQ + VAL)),
    ("beta", re.compile(r"(?:β|(?<![A-Za-z])[Bb]eta|[Ss]tandardi[sz]ed\s+(?:beta|coefficient|regression\s+coefficient))"
                        + DF + EQ + VAL)),
    ("d", re.compile(r"(?:Cohen'?s?\s+d|(?<![A-Za-z])d)" + EQ + VAL)),
    ("g", re.compile(r"(?:Hedges'?s?\s+g|(?<![A-Za-z])g)" + EQ + VAL)),
    ("f", re.compile(r"Cohen'?s?\s+f" + EQ + VAL)),
    ("or", re.compile(r"(?:(?<![A-Za-z])[aA]?OR|[Oo]dds\s+ratios?)(?:\s*(?:=|:|of|was|were)\s*" + VAL + r"|\s+(-?\d+[.,]\d+))")),
]
SIGNED = {"r", "rho", "beta", "d", "g"}
EFFECT_NAME = {"r": "Pearson r", "rho": "Spearman rho", "beta": "standardised beta", "d": "Cohen's d",
               "g": "Hedges' g", "or": "odds ratio", "r2": "R squared", "eta2": "eta squared",
               "f2": "Cohen's f2", "f": "Cohen's f"}

P_RE = re.compile(r"(?<![A-Za-z])p\s*(?:-?\s*values?)?\s*(=|<=|>=|<|>|≤|≥)\s*" + VAL)
CI_RE = re.compile(r"(?:95\s*%\s*CI|CI\s*95\s*%|confidence\s+interval)\s*[:=]?\s*[\[(]?\s*" + VAL
                   + r"\s*(?:-|,|to|;)\s*" + VAL, re.I)
N_EXPLICIT = re.compile(r"(?<![A-Za-z])[Nn]\s*=\s*(\d{1,3}(?:,\d{3})+|\d+)")
N_NOUN = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d{2,6})\s+(?:[A-Za-z\-]+\s+){0,3}?"
                    r"(participants|students|respondents|adolescents|adults|employees|teachers|nurses|patients|children|"
                    r"undergraduates|graduates|workers|users|subjects|managers|individuals|people|women|men|learners|pupils|"
                    r"youths?|teens?|teenagers|cases|controls|dyads|households|firms|companies|schools|faculty|staff|"
                    r"physicians|doctors|clients|customers|consumers|athletes|soldiers|officers|voters|citizens|"
                    r"طالب|طالبة|طالبًا|طالباً|طلاب|مشارك|مشاركًا|مشاركاً|موظف|موظفًا|موظفاً|معلم|معلمًا|معلماً|ممرض|مريض|فرد|فردًا|فرداً|مستجيب)",
                    re.I)
N_SAMPLE = re.compile(r"(?:sample|total)\s+(?:size\s+)?(?:of|was|=|:)\s*(\d{1,3}(?:,\d{3})+|\d+)", re.I)

# Text that must never yield a number: DOIs, URLs, author-year citations.
DOI_URL = re.compile(r"https?://\S+|(?<![A-Za-z0-9])(?:doi:\s*)?10\.\d{4,9}/\S+", re.I)
CITATION = re.compile(r"\((?:[^()]*?(?:19|20)\d{2}[a-z]?)[^()]*\)")

RELATION_PHRASES = [
    re.compile(r"(?:relationship|relation|association|correlation|link)s?\s+between\s+(?P<a>[^,;()]{3,80}?)\s+and\s+(?P<b>[^,;()]{3,80}?)(?=[,;:(.]|\s+(?:was|were|is|are|r\b))", re.I),
    re.compile(r"(?P<a>[A-Za-z][^,;()]{2,60}?)\s+(?:was|were|is|are)?\s*(?:\w+ly\s+)?(?:correlated|associated|related)\s+(?:with|to)\s+(?P<b>[^,;()]{3,80}?)(?=[,;:(.])", re.I),
    re.compile(r"(?:effect|impact|influence)s?\s+of\s+(?P<a>[^,;()]{3,80}?)\s+on\s+(?P<b>[^,;()]{3,80}?)(?=[,;:(.])", re.I),
    re.compile(r"(?P<a>[A-Za-z][^,;()]{2,60}?)\s+(?:significantly\s+)?predict(?:ed|s)\s+(?P<b>[^,;()]{3,80}?)(?=[,;:(.])", re.I),
]


def to_float(s):
    s = s.replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def to_int(s):
    try:
        return int(s.replace(",", ""))
    except ValueError:
        return None


def prepare(text):
    """Clean an abstract and blank out the spans that must never yield a number."""
    t = clean(text).translate(ARABIC_DIGITS)
    t = DOI_URL.sub(lambda m: " " * len(m.group(0)), t)
    t = CITATION.sub(lambda m: " " * len(m.group(0)), t)
    return t


def sentences(text):
    """(start, end) spans of sentences. Splits on . ! ? followed by a capital (space optional,
    abstracts often glue 'performance.Method:')."""
    spans, start = [], 0
    for m in re.finditer(r"(?<=[.!?])\s+(?=[A-Z\"'(\[0-9])|(?<=[a-z][.!?])(?=[A-Z])", text):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(text)))
    return [(s, e) for s, e in spans if text[s:e].strip()]


def find_n(text):
    """(N, how) from the first explicit N =, else 'sample of', else '<number> participants'."""
    m = N_EXPLICIT.search(text)
    if m:
        return to_int(m.group(1)), "N ="
    m = N_SAMPLE.search(text)
    if m:
        v = to_int(m.group(1))
        if v and not 1900 <= v <= 2100:
            return v, "sample of"
    for m in N_NOUN.finditer(text):
        v = to_int(m.group(1))
        if v and not 1900 <= v <= 2100:
            return v, m.group(2)
    return None, ""


def relation_terms(sentence, pattern):
    hits = sorted({h.lower() for h in re.findall(pattern, sentence, re.I)}) if pattern else []
    pairs = []
    for rx in RELATION_PHRASES:
        for m in rx.finditer(sentence):
            a, b = m.group("a").strip(), m.group("b").strip()
            if a and b:
                pairs.append(f"{short(a, 40)} ~ {short(b, 40)}")
                break
        if pairs:
            break
    return hits, pairs[0] if pairs else ""


def harvest_text(text, relation=None):
    """All effect-size candidates in one abstract. Returns a list of dicts."""
    t = prepare(text)
    if not t:
        return []
    n_abs, n_how = find_n(t)
    spans = sentences(t)
    taken, out = [], []
    for etype, rx in EFFECT_PATTERNS:
        for m in rx.finditer(t):
            if any(not (m.end() <= s or m.start() >= e) for s, e in taken):
                continue
            raw = m.group(1) or (m.group(2) if m.lastindex and m.lastindex >= 2 else None)
            val = to_float(raw or "")
            if val is None:
                continue
            if etype in ("r", "rho", "beta") and abs(val) > 1.0001:
                continue                                  # r = 2.3 is not a correlation
            if etype in ("r2", "eta2") and not 0 <= val <= 1.0001:
                continue
            if etype == "or" and val <= 0:
                continue
            taken.append((m.start(), m.end()))
            s, e = next(((s, e) for s, e in spans if s <= m.start() < e), (0, len(t)))
            sent = t[s:e].strip()
            after = t[m.end():e]
            pm = P_RE.search(after) or P_RE.search(sent)
            p_op, p_val = (pm.group(1), to_float(pm.group(2))) if pm else ("", None)
            cm = CI_RE.search(after[:120])
            ci = [to_float(cm.group(1)), to_float(cm.group(2))] if cm else None
            n_sent, how_sent = find_n(sent)
            hits, pair = relation_terms(sent, relation)
            out.append({"type": etype, "value": val, "p_op": p_op, "p": p_val, "ci": ci,
                        "n": n_sent if n_sent else n_abs,
                        "n_source": f"sentence ({how_sent})" if n_sent else (f"abstract ({n_how})" if n_abs else ""),
                        "relation_hits": hits, "relation_pair": pair, "sentence": sent,
                        "match": t[m.start():m.end()], "status": CANDIDATE})
    out.sort(key=lambda r: t.find(r["sentence"]))
    return out


def read_candidates(p):
    """Rows of a cand*.json (dict with results, or a bare list)."""
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("results", []) if isinstance(data, dict) else data


def count_abstracts(p):
    return sum(1 for r in read_candidates(p) if (r.get("abstract") or "").strip())


def load_inputs(paths, ledger_path):
    """Yield (source_id, doi, year, title, abstract, origin) for every record."""
    ledger = load_ledger(ledger_path) if ledger_path and os.path.exists(ledger_path) else []
    by_doi = {norm_doi(e.get("doi")).lower(): e["key"] for e in ledger if e.get("doi") and e.get("key")}
    seen = set()
    for e in ledger:
        doi = norm_doi(e.get("doi"))
        seen.add(doi.lower() or e.get("key"))
        yield e.get("key", ""), doi, e.get("year"), e.get("title", ""), e.get("abstract") or "", os.path.basename(ledger_path)
    for p in paths:
        for r in read_candidates(p):
            doi = norm_doi(r.get("doi"))
            ident = doi.lower() or r.get("title", "")
            if ident in seen:
                continue
            seen.add(ident)
            yield by_doi.get(doi.lower(), ""), doi, r.get("year"), r.get("title", ""), r.get("abstract") or "", os.path.basename(p)


def fmt_val(v, etype):
    if v is None:
        return ""
    if etype == "or":
        return f"{v:.2f}"
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s


def fmt_p(rec):
    if rec["p"] is None:
        return ""
    p = rec["p"]
    return f"p {rec['p_op']} {p:g}"


def summarise(records):
    groups = {}
    for r in records:
        groups.setdefault(r["type"], []).append(r)
    rows, summary = [], {}
    for etype in [t for t, _ in EFFECT_PATTERNS if t in groups]:
        vals = [r["value"] for r in groups[etype]]
        srcs = []
        for r in groups[etype]:
            tag = f"{r['source']} ({r['year'] or 'n.d.'}): {fmt_val(r['value'], etype)}"
            if tag not in srcs:
                srcs.append(tag)
        med_abs = statistics.median(abs(v) for v in vals) if etype in SIGNED else None
        summary[etype] = {"k": len(vals), "median": statistics.median(vals), "min": min(vals), "max": max(vals),
                          "median_abs": med_abs, "sources": srcs}
        rows.append([etype, str(len(vals)), fmt_val(statistics.median(vals), etype), fmt_val(min(vals), etype),
                     fmt_val(max(vals), etype), fmt_val(med_abs, etype) if med_abs is not None else "", "; ".join(srcs)])
    return rows, summary


def cmd_harvest(a):
    paths = a.inp or []
    if not paths and not (a.ledger and os.path.exists(a.ledger)):
        sys.exit("nothing to read: give --in cand.json (repeatable) and/or --ledger sources.jsonl")
    if a.relation:
        try:
            re.compile(a.relation)
        except re.error as e:
            sys.exit(f"--relation is not a valid regex: {e}")
    n_abs = n_empty = 0
    records = []
    for key, doi, year, title, abstract, origin in load_inputs(paths, a.ledger):
        if not abstract.strip():
            n_empty += 1
            continue
        n_abs += 1
        src = key or doi or f"(no DOI) {short(title, 50)}"
        for rec in harvest_text(abstract, a.relation):
            rec.update({"source": src, "key": key, "doi": doi, "year": year, "title": title, "file": origin})
            records.append(rec)
    if a.relation_only:
        records = [r for r in records if r["relation_hits"]]
    papers = len({r["source"] for r in records})
    hit = sum(1 for r in records if r["relation_hits"])
    lines = [f"harvest: {len(paths)} file(s)" + (f" + ledger {os.path.basename(a.ledger)}" if a.ledger and os.path.exists(a.ledger) else "")
             + f" | {n_abs} abstracts scanned ({n_empty} without abstract) | {len(records)} effect-size candidates in {papers} papers"
             + (f" | relation /{a.relation}/ matched in {hit}" if a.relation else "") + f" | {TODAY}"]
    for p in paths:
        if count_abstracts(p) == 0:
            lines.append(NO_ABSTRACTS.format(file=p))
    if records:
        lines.append(table([[str(i + 1), r["type"], fmt_val(r["value"], r["type"]), fmt_p(r),
                             (str(r["n"]) + ("" if r["n_source"].startswith("sentence") else " *")) if r["n"] else "",
                             ", ".join(r["relation_hits"]) or r["relation_pair"], str(r["year"] or ""), r["source"],
                             short(r["sentence"], a.width)]
                            for i, r in enumerate(records)],
                           ["#", "type", "value", "p", "N", "relation", "year", "source", "sentence (candidate)"]))
        if any(r["n"] and not r["n_source"].startswith("sentence") for r in records):
            lines.append("* N taken from elsewhere in the abstract, not from the sentence with the effect size.")
        rows, summary = summarise(records)
        lines.append("")
        lines.append("Per effect type (candidates only):")
        lines.append(table(rows, ["type", "k", "median", "min", "max", "median |value|", "sources"]))
        lines.append("")
        lines.append("Where to look: every row is a regex candidate. Open the abstract (`scholar.py abstract <DOI>`), "
                     "confirm the number, its sign, the variables it relates and the N, then cite it with its ledger key.")
        noted = set()
        for r in records:
            if not r["key"] and r["source"] not in noted:
                noted.add(r["source"])
                lines.append(f"- {r['source']}: not in the ledger. `scholar.py add {r['doi']} --note \"...\"` before citing it."
                             if r["doi"] else f"- {r['source']}: no DOI, cannot be added to the ledger as is.")
    else:
        lines.append("NOT FOUND: no labelled effect size (r, rho, beta, d, g, OR, R2, eta2, f2) in these abstracts. "
                     "Abstracts often omit the statistic: read the Results of the most relevant papers (fulltext) instead.")
        summary = {}
    lines.append("Not checked: full texts (abstracts only), tables, numbers written in words, effect sizes with no label "
                 "(e.g. 'a strong correlation'), and whether a sign in the abstract matches the paper's coding.")
    text = "\n".join(lines)
    print(text)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"# Effect sizes harvested from abstracts ({TODAY})\n\n" + text + "\n")
        print(f"written: {os.path.abspath(a.out)}")
    if a.json:
        with open(a.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"date": TODAY, "inputs": [os.path.abspath(p) for p in paths], "ledger": a.ledger,
                       "relation": a.relation, "status": CANDIDATE, "records": records, "summary": summary},
                      f, ensure_ascii=False, indent=1)
        print(f"written: {os.path.abspath(a.json)}")


# ---------------------------------------------------------------- power

BENCH = {"r": (0.1, 0.3, 0.5), "d": (0.2, 0.5, 0.8), "f2": (0.02, 0.15, 0.35), "f": (0.1, 0.25, 0.4)}
NATIVE = {"corr": "r", "t": "d", "regression": "f2", "anova": "f", "mediation": "ab"}
ACCEPTED = {"corr": ("r",), "t": ("d",), "regression": ("f2", "r2", "beta"), "anova": ("f", "eta2"), "mediation": ("ab",)}
LABEL_RE = re.compile(r"^[A-Za-z0-9_-]+$")
BETA_NOTE = ("beta treated as a partial correlation, f2 = beta^2 / (1 - beta^2): an APPROXIMATION (a standardised "
             "beta equals the partial r only when the predictors are uncorrelated). The power is for the test of that "
             "one predictor (numerator df = 1) in a model with --predictors predictors.")

# Monte Carlo CI for the indirect effect. DOI checked with `scholar.py verify` on 2026-10-21: found, integrity ok.
MED_CITE = "Preacher & Selig, 2012"
MED_DOI = "10.1080/19312458.2012.679848"
MED_METHOD = f"Monte Carlo confidence interval for the indirect effect ({MED_CITE}, doi:{MED_DOI})"
MC_DRAWS = 5000


def benchmark(sym, v):
    """Where the value sits against Cohen's small / medium / large benchmarks."""
    s, m, l = BENCH[sym]
    v = abs(v)
    if v < s:
        return f"below Cohen's small ({s:g})"
    for lo, hi, a, b in ((s, m, "small", "medium"), (m, l, "medium", "large")):
        if lo <= v < hi:
            return f"Cohen's {a} ({lo:g})" if v == lo else f"between Cohen's {a} ({lo:g}) and {b} ({hi:g})"
    return f"Cohen's large ({l:g}) or above"


def to_native(test, etype, value):
    """Convert R2 -> f2, beta -> f2 (partial-correlation approximation) and eta2 -> f;
    everything else is already native."""
    if test == "regression" and etype == "r2":
        if not 0 < value < 1:
            sys.exit("R2 must be between 0 and 1")
        return value / (1 - value)
    if test == "regression" and etype == "beta":
        if not 0 < abs(value) < 1:
            sys.exit("a standardised beta must be between -1 and 1 and non-zero")
        return value * value / (1 - value * value)
    if test == "anova" and etype == "eta2":
        if not 0 < value < 1:
            sys.exit("eta2 must be between 0 and 1")
        return math.sqrt(value / (1 - value))
    return value


def power_corr_fisher(r, n, alpha, tails):
    if n < 4:
        return 0.0
    z = math.atanh(abs(r)) * math.sqrt(n - 3)
    za = stats.norm.ppf(1 - alpha / tails)
    p = stats.norm.sf(za - z)
    if tails == 2:
        p += stats.norm.cdf(-za - z)
    return float(p)


def _r_density(r, rho, n):
    """Sampling density of Pearson r under a bivariate normal with correlation rho (Hotelling 1953)."""
    lc = (math.log(n - 2) + special.gammaln(n - 1) - 0.5 * math.log(2 * math.pi) - special.gammaln(n - 0.5)
          + (n - 1) / 2 * math.log1p(-rho * rho) + (n - 4) / 2 * math.log1p(-r * r)
          - (n - 1.5) * math.log1p(-rho * r))
    return math.exp(lc) * special.hyp2f1(0.5, 0.5, n - 0.5, (1 + rho * r) / 2)


def power_corr_exact(rho, n, alpha, tails):
    """Exact test (G*Power's 'Correlation: bivariate normal model'): integrate the density of r
    over the rejection region of the t test of H0: rho = 0."""
    if n < 5:
        return 0.0
    tc = stats.t.ppf(1 - alpha / tails, n - 2)
    rc = tc / math.sqrt(tc * tc + n - 2)
    rho = abs(rho)
    p = integrate.quad(_r_density, rc, 1, args=(rho, n), limit=200)[0]
    if tails == 2:
        p += integrate.quad(_r_density, -1, -rc, args=(rho, n), limit=200)[0]
    return float(min(p, 1.0))


def power_t(d, n1, alpha, tails, ratio=1.0):
    n2 = max(2, int(round(n1 * ratio)))
    df = n1 + n2 - 2
    if df < 1:
        return 0.0
    ncp = abs(d) * math.sqrt(n1 * n2 / (n1 + n2))
    tc = stats.t.ppf(1 - alpha / tails, df)
    p = stats.nct.sf(tc, df, ncp)
    if tails == 2:
        p += stats.nct.cdf(-tc, df, ncp)
    return float(p)


def power_F(lam, df1, df2, alpha):
    if df2 < 1:
        return 0.0
    fc = stats.f.ppf(1 - alpha, df1, df2)
    return float(stats.ncf.sf(fc, df1, df2, lam))


def power_regression(f2, n, u, alpha):
    """R2 deviation from zero: numerator df = u (all predictors)."""
    return power_F(f2 * n, u, n - u - 1, alpha)


def power_regression_one(f2, n, u, alpha):
    """One predictor's increment in a model with u predictors: numerator df = 1."""
    return power_F(f2 * n, 1, n - u - 1, alpha)


def power_anova(f, n, k, alpha):
    return power_F(f * f * n, k - 1, n - k, alpha)


def power_mediation(a, b, cprime, n, sims=1000, alpha=0.05, draws=MC_DRAWS, seed=1):
    """Monte Carlo power for the indirect effect ab in X -> M -> Y with standardised variables.
    Each simulated sample: estimate a (M on X) and b (Y on X and M) and their SEs by OLS, draw
    a* ~ N(a_hat, se_a) and b* ~ N(b_hat, se_b) `draws` times, take the (alpha/2, 1 - alpha/2)
    quantiles of a*b*; the sample counts when that CI excludes 0. Deterministic per (seed, n)."""
    if n < 10:
        return 0.0
    var_m = 1 - a * a
    var_y = 1 - (b * b + cprime * cprime + 2 * a * b * cprime)
    if var_m <= 0 or var_y <= 0:
        sys.exit("a, b and c' imply a variance <= 0 for a standardised M or Y: use smaller paths")
    rng = np.random.default_rng([seed, n])
    sig = 0
    chunk = max(1, min(sims, 2_000_000 // n))
    done = 0
    while done < sims:
        k = min(chunk, sims - done)
        X = rng.standard_normal((k, n))
        M = a * X + rng.standard_normal((k, n)) * math.sqrt(var_m)
        Y = cprime * X + b * M + rng.standard_normal((k, n)) * math.sqrt(var_y)
        xc = X - X.mean(1, keepdims=True)
        mc = M - M.mean(1, keepdims=True)
        yc = Y - Y.mean(1, keepdims=True)
        sxx = (xc * xc).sum(1)
        sxm = (xc * mc).sum(1)
        smm = (mc * mc).sum(1)
        a_hat = sxm / sxx
        se_a = np.sqrt(((mc - a_hat[:, None] * xc) ** 2).sum(1) / (n - 2) / sxx)
        sxy = (xc * yc).sum(1)
        smy = (mc * yc).sum(1)
        det = sxx * smm - sxm * sxm
        c_hat = (smm * sxy - sxm * smy) / det
        b_hat = (sxx * smy - sxm * sxy) / det
        mse = ((yc - c_hat[:, None] * xc - b_hat[:, None] * mc) ** 2).sum(1) / (n - 3)
        se_b = np.sqrt(mse * sxx / det)
        ab = ((rng.standard_normal((k, draws)) * se_a[:, None] + a_hat[:, None])
              * (rng.standard_normal((k, draws)) * se_b[:, None] + b_hat[:, None]))
        lo = np.quantile(ab, alpha / 2, axis=1)
        hi = np.quantile(ab, 1 - alpha / 2, axis=1)
        sig += int(((lo > 0) | (hi < 0)).sum())
        done += k
    return sig / sims


def required_n(fn, start, target, cap=2_000_000):
    """Smallest integer n >= start with fn(n) >= target (fn is monotone in n)."""
    lo, hi = start, start
    while fn(hi) < target:
        lo, hi = hi, hi * 2
        if hi > cap:
            return None
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if fn(mid) >= target:
            hi = mid
        else:
            lo = mid
    return hi if fn(hi) >= target else None


def parse_sources(s):
    return [k.strip() for k in re.split(r"[;,\s]+", s or "") if k.strip()]


def power_fn(test, eff, etype, a):
    """The power-at-n function for a native effect size eff under the parameters in a."""
    if test == "corr":
        if a.method == "fisher":
            return lambda n: power_corr_fisher(eff, n, a.alpha, a.tails)
        return lambda n: power_corr_exact(eff, n, a.alpha, a.tails)
    if test == "t":
        return lambda n: power_t(eff, n, a.alpha, a.tails, a.ratio)
    if test == "regression":
        if etype == "beta":
            return lambda n: power_regression_one(eff, n, a.predictors, a.alpha)
        return lambda n: power_regression(eff, n, a.predictors, a.alpha)
    if test == "anova":
        return lambda n: power_anova(eff, n, a.groups, a.alpha)
    return lambda n: power_mediation(a.a, a.b, a.cprime, n, a.sims, a.alpha, MC_DRAWS, a.seed)


def compute(a):
    """Shared by power and justify: returns a dict with every number and the warnings."""
    test = a.test
    warnings = []
    label = getattr(a, "label", "") or ""
    if label and not LABEL_RE.match(label):
        sys.exit("--label must be letters, digits, _ or - only (it becomes an evidence key segment, so no dots or spaces)")
    key = f"power.{label or test}"
    sources = parse_sources(a.source)
    ledger = load_ledger(a.ledger) if a.ledger and os.path.exists(a.ledger) else []
    keys = {e.get("key") for e in ledger}
    missing = [k for k in sources if k not in keys]
    if sources and not ledger:
        warnings.append(f"WARNING: ledger {a.ledger} not found, so the source keys could not be checked.")
    elif missing:
        warnings.append(f"WARNING: not in the ledger {a.ledger}: {', '.join(missing)}. Add them with `scholar.py add` "
                        "before citing them.")
    if a.n is not None and a.n < 1:
        sys.exit("--n must be a positive integer")
    if test == "mediation":
        return compute_mediation(a, key, sources, ledger, warnings)
    if a.effect is None:
        sys.exit(f"--effect is required for --test {test}")
    etype = a.effect_type or NATIVE[test]
    if etype not in ACCEPTED[test]:
        sys.exit(f"--effect-type {etype} does not fit --test {test} (accepted: {', '.join(ACCEPTED[test])})")
    eff = to_native(test, etype, a.effect)
    sym = NATIVE[test]
    if eff == 0 or (sym == "r" and abs(eff) >= 1):
        sys.exit("the effect size must be non-zero (and |r| < 1)")
    tails = a.tails
    if not sources:
        warnings.append(f"WARNING: the effect size {sym} = {eff:g} is UNJUSTIFIED: no --source. A reviewer will ask where it "
                        "comes from. Run `effects.py harvest` on your candidates and pass the ledger keys "
                        "(--source \"junco2012; lau2017\"), or state in the Methods that it is a conventional benchmark.")
    res = {"test": test, "sym": sym, "effect": eff, "given_type": etype, "given_value": a.effect, "alpha": a.alpha,
           "tails": tails, "target": a.power, "sources": sources, "ledger": ledger, "warnings": warnings,
           "predictors": a.predictors, "groups": a.groups, "ratio": a.ratio, "key": key, "label": label}
    fn = power_fn(test, eff, etype, a)
    if test == "corr":
        alt = (lambda n: power_corr_exact(eff, n, a.alpha, tails)) if a.method == "fisher" else \
              (lambda n: power_corr_fisher(eff, n, a.alpha, tails))
        res["method"] = "Fisher z approximation" if a.method == "fisher" else "exact bivariate-normal model"
        res["alt_method"] = "exact bivariate-normal model" if a.method == "fisher" else "Fisher z approximation"
        res["n"] = required_n(fn, 5, a.power)
        res["n_alt"] = required_n(alt, 5, a.power)
        res["unit"] = "total N"
        if a.n:
            res["achieved"] = fn(a.n)
            res["achieved_alt"] = alt(a.n)
    elif test == "t":
        res["method"] = "noncentral t (two independent means)"
        res["n"] = required_n(fn, 2, a.power)
        res["unit"] = "per group (group 1)"
        if res["n"]:
            res["n2"] = max(2, int(round(res["n"] * a.ratio)))
            res["n_total"] = res["n"] + res["n2"]
        if a.n:
            res["achieved"] = fn(a.n)
    elif test == "regression":
        if tails == 1:
            warnings.append("note: an F test has no tails; --tails ignored.")
        u = a.predictors
        if u < 1:
            sys.exit("--predictors must be >= 1")
        if etype == "beta":
            res["method"] = f"noncentral F (one predictor's increment, numerator df 1, in a model with {u} predictor{'s' if u > 1 else ''})"
            res["note"] = BETA_NOTE.replace("--predictors", str(u))
        else:
            res["method"] = f"noncentral F (R2 deviation from zero, {u} predictor{'s' if u > 1 else ''})"
        res["n"] = required_n(fn, u + 2, a.power)
        res["unit"] = "total N"
        res["r2_equiv"] = eff / (1 + eff)
        if a.n:
            res["achieved"] = fn(a.n)
    else:
        if tails == 1:
            warnings.append("note: an F test has no tails; --tails ignored.")
        k = a.groups
        if k < 2:
            sys.exit("--groups must be >= 2")
        res["method"] = f"noncentral F (one-way ANOVA, {k} groups)"
        res["n"] = required_n(fn, k + 1, a.power)
        res["unit"] = "total N"
        if res["n"]:
            res["per_group"] = math.ceil(res["n"] / k)
            res["n_balanced"] = res["per_group"] * k
        res["eta2_equiv"] = eff * eff / (1 + eff * eff)
        if a.n:
            res["achieved"] = fn(a.n)
    apply_attrition(res, a)
    res["range"] = []
    start = {"corr": 5, "t": 2, "regression": a.predictors + 2, "anova": a.groups + 1}[test]
    for v in parse_sources(a.range):
        try:
            v = float(v)
        except ValueError:
            sys.exit(f"--range values must be numbers: {v}")
        ev = to_native(test, etype, v)
        res["range"].append((v, required_n(power_fn(test, ev, etype, a), start, a.power)))
    return res


def apply_attrition(res, a):
    if a.attrition:
        if not 0 <= a.attrition < 100:
            sys.exit("--attrition is a percentage between 0 and 99")
        if res.get("n"):
            base = res.get("n_total") or res.get("n_balanced") or res["n"]
            res["n_adjusted"] = math.ceil(base / (1 - a.attrition / 100))


def compute_mediation(a, key, sources, ledger, warnings):
    if a.a is None or a.b is None:
        sys.exit("--test mediation needs --a and --b (standardised paths X -> M and M -> Y), e.g. --a 0.3 --b 0.3")
    for name, v in (("--a", a.a), ("--b", a.b), ("--cprime", a.cprime)):
        if not -1 < v < 1:
            sys.exit(f"{name} is a standardised path and must be between -1 and 1")
    if a.a == 0 or a.b == 0:
        sys.exit("--a and --b must be non-zero (the indirect effect is a * b)")
    if a.sims < 100:
        sys.exit("--sims must be at least 100")
    if a.effect is not None:
        warnings.append("note: --effect is ignored for mediation; the effect is a * b.")
    if a.tails == 1:
        warnings.append("note: the Monte Carlo CI is two-sided; --tails ignored.")
    if a.range:
        warnings.append("note: --range is ignored for mediation (vary --a and --b and run again with another --label).")
    var_y = 1 - (a.b ** 2 + a.cprime ** 2 + 2 * a.a * a.b * a.cprime)
    if var_y <= 0:
        sys.exit("a, b and c' imply a variance <= 0 for a standardised Y: use smaller paths")
    ab = a.a * a.b
    if not sources:
        warnings.append(f"WARNING: the paths a = {a.a:g}, b = {a.b:g} are UNJUSTIFIED: no --source. A reviewer will ask where they "
                        "come from. Harvest beta / r values from the literature and pass the ledger keys (--source \"key1; key2\").")
    res = {"test": "mediation", "sym": "ab", "effect": ab, "given_type": "ab", "given_value": ab, "alpha": a.alpha,
           "tails": 2, "target": a.power, "sources": sources, "ledger": ledger, "warnings": warnings, "key": key,
           "label": getattr(a, "label", "") or "", "a": a.a, "b": a.b, "cprime": a.cprime, "sims": a.sims,
           "seed": a.seed, "draws": MC_DRAWS, "predictors": None, "groups": None, "ratio": None,
           "method": MED_METHOD, "unit": "total N", "range": []}
    fn = power_fn("mediation", ab, "ab", a)
    res["n"] = required_n(fn, 20, a.power, cap=20_000)
    res["mc_se"] = math.sqrt(a.power * (1 - a.power) / a.sims)
    if a.n:
        res["achieved"] = fn(a.n)
    apply_attrition(res, a)
    return res


def tails_word(t):
    return "two-tailed" if t == 2 else "one-tailed"


def print_range(res):
    if res["range"]:
        print("Sensitivity (required N at other plausible effect sizes, e.g. the harvested range):")
        print(table([[f"{v:g}", str(n) if n else "NOT FOUND"] for v, n in res["range"]], [res["given_type"], "required N"]))


def print_power(res, a):
    sym, eff = res["sym"], res["effect"]
    tails = f" {tails_word(res['tails'])}" if res["test"] in ("corr", "t") else ""
    head = f"a = {res['a']:g}, b = {res['b']:g}, c' = {res['cprime']:g} (ab = {eff:.3g})" if res["test"] == "mediation" else f"{sym} = {eff:.3g}"
    print(f"power: {res['test']} | {head} | alpha {res['alpha']:g}{tails} | "
          f"target power {res['target']:g} | sources: {'; '.join(res['sources']) or 'NONE'}"
          + (f" | label {res['label']}" if res["label"] else "") + f" | {TODAY}")
    for w in res["warnings"]:
        print(w)
    rows = [["test", res["method"]]]
    if res["test"] == "mediation":
        rows.append(["effect size", f"indirect effect ab = {eff:.3g} (a = {res['a']:g}, b = {res['b']:g}, c' = {res['cprime']:g}, standardised)"])
        rows.append(["simulation", f"{res['sims']} simulated samples per N, {res['draws']} Monte Carlo draws each, seed {res['seed']}"])
        rows.append(["alpha", f"{res['alpha']:g} ({100 * (1 - res['alpha']):g}% Monte Carlo CI, two-sided)"])
    else:
        rows.append(["effect size", f"{sym} = {eff:.3g}" + (f" (from {res['given_type']} = {res['given_value']:g})"
                                                          if res["given_type"] != sym else "")
                     + (f"; {benchmark(sym, eff)} by Cohen's benchmarks (a benchmark is not a justification)" if sym in BENCH else "")])
        if res.get("note"):
            rows.append(["note", res["note"]])
        rows.append(["alpha", f"{res['alpha']:g}, {tails_word(res['tails'])}" if res["test"] in ("corr", "t") else f"{res['alpha']:g}"])
    rows.append(["target power", f"{res['target']:g}"])
    if res.get("n") is None:
        cap = "20,000 (Monte Carlo search cap)" if res["test"] == "mediation" else "2,000,000"
        rows.append(["required N", f"NOT FOUND below {cap} (effect too small for this power)"])
    else:
        rows.append([f"required N ({res['unit']})", str(res["n"])
                     + (f" (Monte Carlo estimate; power SE about {res['mc_se']:.3f} at this N)" if res["test"] == "mediation" else "")])
        if res.get("n_total"):
            rows.append(["group 2 / total", f"{res['n2']} / {res['n_total']}" + (f" (ratio {res['ratio']:g})" if res["ratio"] != 1 else "")])
        if res.get("n_balanced"):
            rows.append(["per group / balanced total", f"{res['per_group']} / {res['n_balanced']}"])
        if res.get("n_alt") is not None:
            rows.append([f"cross-check: {res['alt_method']}", str(res["n_alt"])])
        if res.get("n_adjusted"):
            rows.append([f"recruit with {a.attrition:g}% attrition", str(res["n_adjusted"])])
    if res.get("r2_equiv") is not None:
        rows.append(["equivalent R2", f"{res['r2_equiv']:.3f}"])
    if res.get("eta2_equiv") is not None:
        rows.append(["equivalent eta2", f"{res['eta2_equiv']:.3f}"])
    if res.get("achieved") is not None:
        rows.append([f"achieved power at --n {a.n}", f"{res['achieved']:.3f}"
                     + (f" ({res['alt_method']}: {res['achieved_alt']:.3f})" if res.get("achieved_alt") is not None else "")])
    print(table(rows, ["quantity", "value"]))
    print_range(res)
    if res["test"] == "mediation":
        print(f"Method citation: {MED_CITE}, https://doi.org/{MED_DOI} (add it to the ledger with `scholar.py add {MED_DOI}` if you cite it). "
              "Numbers are Monte Carlo estimates from simulated standardised data, not from your data.")
    else:
        print("Numbers are computed from the parameters above, not from data; the effect size is the only input a source can justify.")


def evidence_lines(res, a):
    t, sym, k = res["test"], res["sym"], res["key"]
    if t == "mediation":
        lines = [f"# power mediation | a = {res['a']:g}, b = {res['b']:g}, c' = {res['cprime']:g} | sources: "
                 f"{'; '.join(res['sources']) or 'NONE (unjustified)'} | {MED_CITE} | {TODAY}",
                 f"{k}.path_a.beta = {res['a']:.6g}", f"{k}.path_b.beta = {res['b']:.6g}", f"{k}.cprime.beta = {res['cprime']:.6g}",
                 f"{k}.indirect.beta = {res['effect']:.6g}", f"{k}.sims.n = {res['sims']}", f"{k}.draws.n = {res['draws']}"]
    else:
        lines = [f"# power {t} | {sym} = {res['effect']:g} | sources: {'; '.join(res['sources']) or 'NONE (unjustified)'} | {TODAY}",
                 f"{k}.effect.{sym} = {res['effect']:.6g}"]
        if res["given_type"] != sym:
            lines.append(f"{k}.given.{res['given_type']} = {res['given_value']:.6g}")
    lines.append(f"{k}.alpha = {res['alpha']:g}")
    if t in ("corr", "t"):
        lines.append(f"{k}.tails = {res['tails']}")
    if t == "regression":
        lines.append(f"{k}.predictors.n = {res['predictors']}")
    if t == "anova":
        lines.append(f"{k}.groups.n = {res['groups']}")
    lines.append(f"{k}.power = {res['target']:g}")
    if res.get("n"):
        lines.append(f"{k}.n = {res['n']}")
        if res.get("n_total"):
            lines.append(f"{k}.group2.n = {res['n2']}")
            lines.append(f"{k}.total.n = {res['n_total']}")
        if res.get("n_balanced"):
            lines.append(f"{k}.per_group.n = {res['per_group']}")
            lines.append(f"{k}.total.n = {res['n_balanced']}")
        if res.get("n_adjusted"):
            lines.append(f"{k}.attrition.pct = {a.attrition:g}")
            lines.append(f"{k}.adjusted.n = {res['n_adjusted']}")
    if res.get("achieved") is not None:
        lines.append(f"{k}.given.n = {a.n}")
        lines.append(f"{k}.achieved.power = {res['achieved']:.3f}")
    for i, (v, n) in enumerate(res["range"], 1):
        lines.append(f"{k}.range{i}.{res['given_type']} = {v:g}")
        lines.append(f"{k}.range{i}.n = {n if n else 'NOT FOUND'}")
    if res["sources"]:
        lines.append(f"{k}.sources = {'; '.join(res['sources'])}")
    lines.append("# APA: " + apa_sentence(res))
    return lines


def apa_num(x, lead=True, dec=2):
    s = f"{x:.{dec}f}"
    return s if lead else s.replace("0.", ".", 1)


def apa_sentence(res):
    sym, eff, t = res["sym"], res["effect"], res["test"]
    n = res.get("n")
    if t == "mediation":
        return (f"A Monte Carlo power analysis for the indirect effect (a = {apa_num(res['a'], False)}, b = {apa_num(res['b'], False)}, "
                f"c' = {apa_num(res['cprime'], False)}; {res['sims']:,} simulated samples, {res['draws']:,} Monte Carlo draws each; "
                f"{100 * (1 - res['alpha']):g}% CI; 1 - β = {apa_num(res['target'], False)}) required "
                + (f"N = {n}." if n else "N = NOT FOUND."))
    eff_s = {"r": f"r = {apa_num(eff, False)}", "d": f"d = {apa_num(eff)}", "f2": f"f² = {apa_num(eff)}",
             "f": f"f = {apa_num(eff)}"}[sym]
    tail = f", {tails_word(res['tails'])}" if t in ("corr", "t") else ""
    if t == "t" and n:
        n_s = f"n = {n} per group (N = {res['n_total']})"
    elif t == "anova" and n:
        n_s = f"N = {res['n_balanced']} ({res['per_group']} per group)"
    else:
        n_s = f"N = {n}" if n else "N = NOT FOUND"
    return (f"An a priori power analysis ({eff_s}, α = {apa_num(res['alpha'], False)}{tail}, 1 - β = {apa_num(res['target'], False)}) "
            f"required {n_s}.")


def cmd_power(a):
    res = compute(a)
    print_power(res, a)
    print("Evidence lines (append to analysis/output.txt, or use `justify --evidence ... --append`):")
    print("\n".join(evidence_lines(res, a)))


# ---------------------------------------------------------------- justify

def cite_entry(e, arabic=False):
    auths = e.get("authors") or []
    year = e.get("year") or ("د.ت" if arabic else "n.d.")
    if not auths:
        return f"{short(e.get('title', e.get('key', '')), 40)}, {year}"
    fam = [x.get("family", "") for x in auths]
    if len(fam) == 1:
        who = fam[0]
    elif len(fam) == 2:
        who = f"{fam[0]} & {fam[1]}" if not arabic else f"{fam[0]} و{fam[1]}"
    else:
        who = f"{fam[0]} et al." if not (arabic and ARABIC_RE.search(fam[0])) else f"{fam[0]} وآخرون"
    return f"{who}, {year}" if not arabic else f"{who}، {year}"


def citations(res, arabic=False):
    by_key = {e.get("key"): e for e in res["ledger"]}
    parts, missing = [], []
    for k in res["sources"]:
        if k in by_key:
            parts.append(cite_entry(by_key[k], arabic))
        else:
            missing.append(k)
    sep = "؛ " if arabic else "; "
    txt = "(" + sep.join(parts) + ")" if parts else ""
    if missing:
        txt += (" " if txt else "") + "[" + ("المفتاح ليس في السجل: " if arabic else "not in ledger: ") + ", ".join(missing) + "]"
    if not res["sources"]:
        txt = "[SOURCE NEEDED: effect size has no citation]" if not arabic else "[مطلوب مصدر: حجم الأثر بلا استشهاد]"
    return txt


def given_label(res, arabic=False):
    g = res["given_type"]
    return {"r2": "R²", "eta2": "η²", "beta": "β"}.get(g, g)


def paragraph_en(res, a):
    sym, eff, t = res["sym"], res["effect"], res["test"]
    claim = a.claim or "the expected effect"
    n = res.get("n")
    if t == "mediation":
        p = (f"The sample size was determined a priori with a Monte Carlo power analysis for the indirect effect (ab) in a simple "
             f"mediation model, using the Monte Carlo confidence interval method ({MED_CITE}). "
             f"The standardised path coefficients for {claim}, a = {apa_num(res['a'], False)} and b = {apa_num(res['b'], False)} "
             f"(direct effect c' = {apa_num(res['cprime'], False)}), were taken from the literature {citations(res)}. "
             f"For each candidate sample size, {res['sims']:,} data sets were simulated from standardised X, M and Y; a and b and "
             f"their standard errors were estimated by ordinary least squares, and the indirect effect was counted as detected when "
             f"the {100 * (1 - res['alpha']):g}% Monte Carlo confidence interval ({res['draws']:,} draws) excluded zero. "
             f"With a target power of {apa_num(res['target'], False)}, the required sample (effects.py, NumPy) was "
             + (f"N = {n} participants." if n else "N = [NOT FOUND]."))
    else:
        eff_s = {"r": f"r = {apa_num(eff, False)}", "d": f"d = {apa_num(eff)}", "f2": f"f² = {apa_num(eff)}",
                 "f": f"f = {apa_num(eff)}"}[sym]
        if res["given_type"] != sym:
            eff_s += f" (from {given_label(res)} = {apa_num(res['given_value'], False)}"
            eff_s += ", the standardised beta treated as a partial correlation, an approximation)" if res["given_type"] == "beta" else ")"
        test_s = {"corr": "a two-tailed test of a Pearson correlation" if res["tails"] == 2 else "a one-tailed test of a Pearson correlation",
                  "t": "an independent-samples t test" + (" (two-tailed)" if res["tails"] == 2 else " (one-tailed)"),
                  "regression": (f"the test of one predictor in a multiple regression with {res['predictors']} predictor{'s' if res['predictors'] > 1 else ''}"
                                 if res["given_type"] == "beta" else
                                 f"a multiple regression with {res['predictors']} predictor{'s' if res['predictors'] > 1 else ''} (R² deviation from zero)"),
                  "anova": f"a one-way ANOVA with {res['groups']} groups"}[t]
        dist = {"corr": res["method"], "t": "the noncentral t distribution", "regression": "the noncentral F distribution",
                "anova": "the noncentral F distribution"}[t]
        if t == "t" and n:
            n_s = f"n = {n} participants per group (N = {res['n_total']})"
        elif t == "anova" and n:
            n_s = f"N = {res['n_balanced']} participants ({res['per_group']} per group)"
        else:
            n_s = f"N = {n} participants" if n else "N = [NOT FOUND]"
        p = (f"The sample size was determined a priori with a power analysis for {test_s}. "
             f"The effect size for {claim}, {eff_s}, was taken from the literature {citations(res)}. "
             f"With α = {apa_num(res['alpha'], False)} and a target power of {apa_num(res['target'], False)}, "
             f"the required sample computed with {dist} (effects.py, SciPy) was {n_s}.")
    if res.get("n_adjusted"):
        p += f" Allowing for {a.attrition:g}% attrition, the recruitment target was set at {res['n_adjusted']} participants."
    if res.get("achieved") is not None:
        p += f" With the available N = {a.n}, the achieved power for this effect size is {apa_num(res['achieved'])}."
    if res["range"]:
        parts = [f"{given_label(res)} = {apa_num(v, False)} requires N = {n_ if n_ else '[NOT FOUND]'}" for v, n_ in res["range"]]
        p += " As a sensitivity check, " + "; ".join(parts) + "."
    return p


def ar_prefix(p, w):
    """Attach the one-letter prepositions ل / ب: joined to an Arabic word (لاختبار, بالارتباط, للأثر),
    with a tatweel before Latin text or digits (بـ89, بـFisher)."""
    if ARABIC_RE.match(w[:1]):
        if p == "ل" and w.startswith("ال"):
            return "لل" + w[2:]
        return p + w
    return p + "ـ" + w


def paragraph_ar(res, a):
    sym, eff, t = res["sym"], res["effect"], res["test"]
    claim = a.claim_ar or "الأثر المتوقع"
    n = res.get("n")
    if t == "mediation":
        p = (f"حُدد حجم العينة مسبقًا باستخدام تحليل قوة إحصائية بطريقة Monte Carlo للأثر غير المباشر (ab) في نموذج وساطة بسيط، "
             f"وفق طريقة فترة ثقة Monte Carlo ({MED_CITE}). "
             f"واستُمدت معاملات المسار المعيارية الخاصة {ar_prefix('ب', claim)}، a = {apa_num(res['a'], False)} و b = {apa_num(res['b'], False)} "
             f"(الأثر المباشر c' = {apa_num(res['cprime'], False)})، من الدراسات السابقة {citations(res, arabic=True)}. "
             f"ولكل حجم عينة مرشح جرت محاكاة {res['sims']:,} مجموعة بيانات لمتغيرات X وM وY المعيارية، وقُدر المساران a وb وخطآهما "
             f"المعياريان بطريقة المربعات الصغرى (OLS)، وعُدّ الأثر غير المباشر مكتشفًا عندما تستبعد فترة ثقة Monte Carlo "
             f"{100 * (1 - res['alpha']):g}% ({res['draws']:,} سحبة) الصفر. "
             f"وعند قوة إحصائية مستهدفة قدرها {apa_num(res['target'], False)} بلغ حجم العينة المطلوب (effects.py، NumPy) "
             + (f"N = {n} مشاركًا." if n else "N = [غير محدد]."))
    else:
        eff_s = {"r": f"r = {apa_num(eff, False)}", "d": f"d = {apa_num(eff)}", "f2": f"f² = {apa_num(eff)}",
                 "f": f"f = {apa_num(eff)}"}[sym]
        if res["given_type"] != sym:
            eff_s += f" (محسوب من {given_label(res)} = {apa_num(res['given_value'], False)}"
            eff_s += "، مع معاملة β المعياري كارتباط جزئي، وهو تقريب)" if res["given_type"] == "beta" else ")"
        test_s = {"corr": "اختبار معامل ارتباط Pearson " + ("(ذو ذيلين)" if res["tails"] == 2 else "(ذو ذيل واحد)"),
                  "t": "اختبار t لعينتين مستقلتين " + ("(ذو ذيلين)" if res["tails"] == 2 else "(ذو ذيل واحد)"),
                  "regression": (f"اختبار متنبئ واحد في تحليل الانحدار المتعدد بعدد {res['predictors']} من المتنبئات"
                                 if res["given_type"] == "beta" else
                                 f"تحليل الانحدار المتعدد بعدد {res['predictors']} من المتنبئات (انحراف R² عن الصفر)"),
                  "anova": f"تحليل التباين الأحادي (ANOVA) بعدد {res['groups']} مجموعات"}[t]
        dist = {"corr": "تقريب Fisher z" if "Fisher" in res["method"] else "النموذج الدقيق ثنائي المتغير الطبيعي",
                "t": "توزيع t غير المركزي", "regression": "توزيع F غير المركزي", "anova": "توزيع F غير المركزي"}[t]
        if t == "t" and n:
            n_s = f"n = {n} مشاركًا في كل مجموعة (N = {res['n_total']})"
        elif t == "anova" and n:
            n_s = f"N = {res['n_balanced']} مشاركًا ({res['per_group']} في كل مجموعة)"
        else:
            n_s = f"N = {n} مشاركًا" if n else "N = [غير محدد]"
        p = (f"حُدد حجم العينة مسبقًا باستخدام تحليل القوة الإحصائية {ar_prefix('ل', test_s)}. "
             f"واستُمد حجم الأثر الخاص {ar_prefix('ب', claim)}، {eff_s}، من الدراسات السابقة {citations(res, arabic=True)}. "
             f"وعند مستوى دلالة α = {apa_num(res['alpha'], False)} وقوة إحصائية مستهدفة قدرها {apa_num(res['target'], False)}، "
             f"بلغ حجم العينة المطلوب المحسوب {ar_prefix('ب', dist)} (effects.py، SciPy) {n_s}.")
    if res.get("n_adjusted"):
        p += f" ومع احتساب نسبة تسرب قدرها {a.attrition:g}%، حُدد هدف التجنيد {ar_prefix('ب', str(res['n_adjusted']))} مشاركًا."
    if res.get("achieved") is not None:
        p += f" وبالعينة المتاحة (N = {a.n}) تبلغ القوة المتحققة لهذا الأثر {apa_num(res['achieved'])}."
    if res["range"]:
        parts = [f"{given_label(res)} = {apa_num(v, False)} يتطلب N = {n_ if n_ else '[غير محدد]'}" for v, n_ in res["range"]]
        p += " وكتحليل حساسية، " + "؛ ".join(parts) + "."
    return p


def cmd_justify(a):
    res = compute(a)
    head = f"a = {res['a']:g}, b = {res['b']:g}" if res["test"] == "mediation" else f"{res['sym']} = {res['effect']:.3g}"
    print(f"justify: {res['test']} | {head} | N = {res.get('n')} | sources: "
          f"{'; '.join(res['sources']) or 'NONE'}" + (f" | label {res['label']}" if res["label"] else "") + f" | {TODAY}")
    for w in res["warnings"]:
        print(w)
    if a.lang in ("en", "both"):
        print("\n## Methods: sample size (EN)\n")
        print(paragraph_en(res, a))
    if a.lang in ("ar", "both"):
        print("\n## حجم العينة (AR)\n")
        print(paragraph_ar(res, a))
    if res["range"]:
        print("")
        print_range(res)
    lines = evidence_lines(res, a)
    print("\nEvidence lines:")
    print("\n".join(lines))
    if a.evidence:
        if a.append:
            os.makedirs(os.path.dirname(os.path.abspath(a.evidence)), exist_ok=True)
            with open(a.evidence, "a", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(lines) + "\n")
            print(f"appended {len(lines)} lines to {os.path.abspath(a.evidence)}")
        else:
            print(f"not written: add --append to append these lines to {os.path.abspath(a.evidence)}")
    if not res["sources"]:
        print("The paragraph carries a [SOURCE NEEDED] placeholder: the effect size is not cited.")
    if res["test"] == "mediation":
        print(f"Method citation: {MED_CITE}, https://doi.org/{MED_DOI}: add it to the ledger (`scholar.py add {MED_DOI}`) so the reference list carries it.")
    if res.get("note"):
        print(res["note"])
    print("The paragraphs cite only ledger keys; the prose is a draft for the author to adapt.")


# ---------------------------------------------------------------- selftest

POSITIVE = (
    "We surveyed 234 participants at one university. GPA was negatively correlated with time on social media, "
    "r = -.31, p < .001, and sleep quality predicted GPA (β = .19, p = .02). Spearman's rho = 0.42 (p < 0.01). "
    "Men scored higher than women (Cohen's d = 0.45). Heavy users were more likely to fail, OR = 1.8 (95% CI 1.2-2.7). "
    "The model explained R² = .13 of the variance; the group effect was ηp² = .06 and f² = 0.15. "
    "Duration of use for learning correlated with performance (r = 0,554, p = 0,0001)."
)
NEGATIVE = (
    "Earlier work reported a small effect (Junco, 2012, r = .31) and a larger one (Kirschner & Karpinski, 2010; d = 0.52). "
    "See https://doi.org/10.1016/j.chb.2011.r=.31 and doi:10.5555/abc.d=0.77.x for details. "
    "The 2019 cohort used the platform more than the 2018 cohort."
)


def base_ns(**kw):
    ns = argparse.Namespace(test="corr", effect=0.3, effect_type=None, alpha=0.05, power=0.8, tails=2, n=None,
                            predictors=1, groups=2, ratio=1.0, source="", ledger="__none__.jsonl", method="fisher",
                            attrition=0, range="", label="", a=None, b=None, cprime=0.0, sims=1000, seed=1)
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def cmd_selftest(a):
    fails, checks = [], []

    def check(name, ok, detail=""):
        checks.append([name, "PASS" if ok else "FAIL", detail])
        if not ok:
            fails.append(name)

    pos = harvest_text(POSITIVE, relation="sleep|GPA")
    got = {(r["type"], round(r["value"], 3)) for r in pos}
    want = {("r", -0.31), ("beta", 0.19), ("rho", 0.42), ("d", 0.45), ("or", 1.8), ("r2", 0.13), ("eta2", 0.06),
            ("f2", 0.15), ("r", 0.554)}
    check("harvest: all 9 planted effect sizes found", want <= got, f"found {sorted(got)}")
    r1 = next((r for r in pos if r["type"] == "r" and r["value"] == -0.31), None)
    check("harvest: p-value next to r = -.31", bool(r1) and r1["p_op"] == "<" and r1["p"] == 0.001, str(r1 and fmt_p(r1)))
    check("harvest: N = 234 from the abstract", bool(r1) and r1["n"] == 234, str(r1 and r1["n"]))
    check("harvest: relation words sleep|GPA in the r sentence", bool(r1) and "gpa" in r1["relation_hits"], str(r1 and r1["relation_hits"]))
    o = next((r for r in pos if r["type"] == "or"), None)
    check("harvest: OR 95% CI captured", bool(o) and o["ci"] == [1.2, 2.7], str(o and o["ci"]))
    c = next((r for r in pos if r["type"] == "r" and r["value"] == 0.554), None)
    check("harvest: decimal comma r = 0,554 with p = 0,0001", bool(c) and c["p"] == 0.0001, str(c and fmt_p(c)))
    check("harvest: every record labelled as a candidate", all(r["status"] == CANDIDATE for r in pos))
    neg = harvest_text(NEGATIVE, relation="sleep|GPA")
    check("negative control: nothing extracted from citations, DOIs or years", not neg,
          "extracted: " + "; ".join(f"{r['type']}={r['value']}" for r in neg) if neg else "0 records")
    n_neg, _ = find_n(prepare(NEGATIVE))
    check("negative control: 2019/2018 cohorts are not N", n_neg is None, str(n_neg))

    # harvest on a candidate file without abstracts: the exact rerun hint, no crash.
    with tempfile.TemporaryDirectory() as tmp:
        cand = os.path.join(tmp, "cand_noabs.json")
        with open(cand, "w", encoding="utf-8") as f:
            json.dump({"query": "x", "date": TODAY, "source": "openalex",
                       "results": [{"doi": "10.1000/xyz1", "title": "No abstract here", "year": "2020", "abstract": ""}]}, f)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_harvest(argparse.Namespace(inp=[cand], ledger="__none__.jsonl", relation=None, relation_only=False,
                                           out=None, json=None, width=110))
        check("harvest: candidate file without abstracts prints the rerun hint",
              NO_ABSTRACTS.format(file=cand) in buf.getvalue(), "line present" if NO_ABSTRACTS.format(file=cand) in buf.getvalue() else buf.getvalue()[:200])

    # Published power values. G*Power 3.1 manual: two-sample t, d = 0.5, alpha .05 two-tailed, power .80 -> 64 per group.
    n_t = required_n(lambda n: power_t(0.5, n, 0.05, 2), 2, 0.8)
    check("power t: d = 0.5 -> 64 per group (G*Power manual)", n_t == 64, str(n_t))
    n_fz = required_n(lambda n: power_corr_fisher(0.3, n, 0.05, 2), 5, 0.8)
    check("power corr: r = .3 Fisher z -> 85 (Cohen 1988 table 3.4.1)", n_fz == 85, str(n_fz))
    n_ex = required_n(lambda n: power_corr_exact(0.3, n, 0.05, 2), 5, 0.8)
    check("power corr: r = .3 exact bivariate normal -> 84 (G*Power 3.1 exact test)", n_ex == 84, str(n_ex))
    dens = integrate.quad(_r_density, -1, 1, args=(0.3, 30))[0]
    check("exact corr density integrates to 1", abs(dens - 1) < 1e-6, f"{dens:.8f}")
    n_reg = required_n(lambda n: power_regression(0.15, n, 3, 0.05), 5, 0.8)
    check("power regression: f2 = .15, 3 predictors -> 77 (G*Power)", n_reg == 77, str(n_reg))
    n_an = required_n(lambda n: power_anova(0.25, n, 4, 0.05), 5, 0.8)
    # G*Power reports the balanced total (a multiple of k): 45 x 4 = 180; the unbalanced minimum is 179.
    check("power anova: f = .25, 4 groups -> balanced 180 (G*Power; minimum 179)", math.ceil(n_an / 4) * 4 == 180 and n_an == 179,
          f"min {n_an}, balanced {math.ceil(n_an / 4) * 4}")
    n_an3 = required_n(lambda n: power_anova(0.25, n, 3, 0.05), 5, 0.8)
    check("power anova: f = .25, 3 groups -> balanced 159 (G*Power)", math.ceil(n_an3 / 3) * 3 == 159, str(n_an3))
    ach = power_t(0.5, 64, 0.05, 2)
    check("reverse: achieved power at 64 per group is 0.80", abs(ach - 0.8015) < 0.002, f"{ach:.4f}")

    # beta -> f2 (partial-correlation approximation), one-predictor test, G*Power "R2 increase": f2 = .15, df1 = 1, u = 3 -> 55.
    f2_beta = to_native("regression", "beta", 0.3)
    check("beta 0.3 -> f2 = 0.0989 (beta^2 / (1 - beta^2))", abs(f2_beta - 0.09 / 0.91) < 1e-9, f"{f2_beta:.4f}")
    n_one = required_n(lambda n: power_regression_one(0.15, n, 3, 0.05), 5, 0.8)
    check("power regression one predictor: f2 = .15, numerator df 1, 3 predictors -> 55 (G*Power R2 increase)", n_one == 55, str(n_one))
    res_b = compute(base_ns(test="regression", effect=0.3, effect_type="beta", predictors=3, source="junco2012"))
    check("beta: output says partial correlation and approximation", "APPROXIMATION" in res_b.get("note", "") and "partial correlation" in res_b["note"]
          and any("given.beta = 0.3" in ln for ln in evidence_lines(res_b, base_ns(predictors=3))), f"N = {res_b['n']}")

    # Mediation: a = b = 0.3, c' = 0, alpha .05. Power at N = 200 must be high (> .9), at N = 50 low.
    p200 = power_mediation(0.3, 0.3, 0.0, 200, sims=1000, seed=1)
    p50 = power_mediation(0.3, 0.3, 0.0, 50, sims=1000, seed=1)
    check("mediation: a = b = .3, N = 200 -> power > .9 (Monte Carlo CI, 1000 sims)", p200 > 0.9, f"power {p200:.3f}")
    check("mediation: a = b = .3, N = 50 -> power low (< .75)", p50 < 0.75, f"power {p50:.3f}")
    check("mediation: power rises with N", p200 > p50, f"N=50 {p50:.3f} < N=200 {p200:.3f}")
    res_m = compute(base_ns(test="mediation", effect=None, a=0.3, b=0.3, cprime=0.0, sims=500, source="x2020"))
    ev_m = evidence_lines(res_m, base_ns())
    check("mediation: required N found by search and evidence lines carry the paths", bool(res_m["n"]) and 60 <= res_m["n"] <= 120
          and any(ln.startswith("power.mediation.path_a.beta = 0.3") for ln in ev_m), f"N = {res_m['n']}")
    check("mediation: method names the Monte Carlo CI and the verified DOI", MED_DOI in res_m["method"] and "Preacher" in res_m["method"], res_m["method"])

    # --label and --range: distinct keys and sensitivity evidence lines (justify path).
    res_r = compute(base_ns(source="junco2012", range="0.25,0.45", label="h1"))
    ev_r = evidence_lines(res_r, base_ns())
    check("label: evidence keys use power.h1.*", all(ln.startswith("power.h1.") for ln in ev_r if not ln.startswith("#")), ev_r[1])
    n25 = required_n(lambda n: power_corr_fisher(0.25, n, 0.05, 2), 5, 0.8)
    n45 = required_n(lambda n: power_corr_fisher(0.45, n, 0.05, 2), 5, 0.8)
    check("range: sensitivity N equals a direct run and reaches the evidence lines",
          [n for _, n in res_r["range"]] == [n25, n45] and any(ln == f"power.h1.range1.n = {n25}" for ln in ev_r)
          and any(ln == f"power.h1.range2.n = {n45}" for ln in ev_r), f"r = .25 -> {n25}, r = .45 -> {n45}")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_justify(base_ns(source="junco2012", range="0.25,0.45", label="h1", lang="en", claim=None, claim_ar=None,
                            evidence=None, append=False))
    check("justify: prints the sensitivity table and the range sentence", "Sensitivity" in buf.getvalue() and "sensitivity check" in buf.getvalue())

    res = compute(base_ns())
    check("negative control: power without --source warns UNJUSTIFIED", any("UNJUSTIFIED" in w for w in res["warnings"]))
    res = compute(base_ns(source="junco2012"))
    check("negative control: unknown ledger -> warning, not a silent pass", any("ledger" in w for w in res["warnings"]))
    print(table(checks, ["check", "result", "detail"]))
    print(f"mediation validation: a = b = .3, N = 200 -> power {p200:.3f}; N = 50 -> power {p50:.3f} (1000 sims, {MC_DRAWS} draws, seed 1)")
    print("Not checked: real abstracts (run `harvest --in cand.json` yourself), unequal-n t tests against a published value, "
          "one-tailed values, mediation power against a published table (only the a = b = .3 sanity bounds above).")
    print(f"RESULT: {'PASS' if not fails else 'FAIL'} ({len(checks) - len(fails)}/{len(checks)} checks)"
          + (": " + ", ".join(fails) if fails else ""))
    if fails:
        sys.exit(1)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("harvest", help="extract reported effect sizes from abstracts (candidates to confirm)",
                       epilog='example: effects.py harvest --in cand.json --ledger sources.jsonl --relation "sleep|GPA" --out effects.md')
    h.add_argument("--in", dest="inp", action="append", help="cand*.json from scholar.py search --out (repeatable)")
    h.add_argument("--ledger", default="sources.jsonl", help="source ledger; its abstracts are scanned and DOIs mapped to keys")
    h.add_argument("--relation", help='regex of the variables you care about, e.g. "sleep|GPA"; matched words are listed per sentence')
    h.add_argument("--relation-only", action="store_true", help="keep only sentences where --relation matched")
    h.add_argument("--out", help="write the report as markdown")
    h.add_argument("--json", help="write the records as JSON")
    h.add_argument("--width", type=int, default=110, help="sentence column width in the table (default 110)")
    h.set_defaults(func=cmd_harvest)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--test", required=True, choices=["corr", "t", "regression", "anova", "mediation"])
    common.add_argument("--effect", type=float, help="r (corr), d (t), f2, R2 or beta (regression), f or eta2 (anova); not used for mediation")
    common.add_argument("--effect-type", choices=["r", "d", "f2", "r2", "beta", "f", "eta2"],
                        help="what --effect is; default: the test's native one. beta (regression) = partial-correlation approximation")
    common.add_argument("--a", type=float, help="mediation: standardised path X -> M, e.g. 0.3")
    common.add_argument("--b", type=float, help="mediation: standardised path M -> Y, e.g. 0.3")
    common.add_argument("--cprime", type=float, default=0.0, help="mediation: standardised direct effect X -> Y (default 0)")
    common.add_argument("--sims", type=int, default=1000, help="mediation: simulated samples per N (default 1000)")
    common.add_argument("--seed", type=int, default=1, help="mediation: random seed (default 1)")
    common.add_argument("--alpha", type=float, default=0.05)
    common.add_argument("--power", type=float, default=0.80, help="target power (default 0.80)")
    common.add_argument("--tails", type=int, choices=[1, 2], default=2, help="corr and t only (default 2)")
    common.add_argument("--n", type=int, help="reverse mode: achieved power at this N (per group for t, total otherwise)")
    common.add_argument("--predictors", type=int, default=1, help="regression: number of predictors (default 1)")
    common.add_argument("--groups", type=int, default=2, help="anova: number of groups (default 2)")
    common.add_argument("--ratio", type=float, default=1.0, help="t: n2/n1 allocation ratio (default 1)")
    common.add_argument("--method", choices=["fisher", "exact"], default="fisher", help="corr: Fisher z (default) or exact bivariate normal")
    common.add_argument("--source", default="", help='ledger keys behind the effect size, e.g. "junco2012; lau2017"')
    common.add_argument("--ledger", default="sources.jsonl")
    common.add_argument("--attrition", type=float, default=0, help="percent expected dropout: inflates the recruitment N")
    common.add_argument("--range", default="", help='other plausible effect sizes to show N for, e.g. "0.25,0.45" (sensitivity table + evidence lines)')
    common.add_argument("--label", default="", help="evidence key prefix: power.<label>.n ... instead of power.<test>.n, so repeated runs do not collide")

    p = sub.add_parser("power", parents=[common], help="required N for a test and effect size, or achieved power with --n",
                       epilog='example: effects.py power --test corr --effect 0.3 --source "junco2012; lau2017"')
    p.set_defaults(func=cmd_power)

    j = sub.add_parser("justify", parents=[common], help="Methods paragraph (EN + AR), sensitivity table and evidence lines for the sample size",
                       epilog="example: effects.py justify --test t --effect 0.5 --source kolhar2021 --evidence analysis/output.txt --append")
    j.add_argument("--lang", choices=["en", "ar", "both"], default="both")
    j.add_argument("--claim", help='what the effect is, EN, e.g. "the correlation between sleep and GPA"')
    j.add_argument("--claim-ar", help="the same in Arabic")
    j.add_argument("--evidence", help="analysis/output.txt to append the evidence lines to (needs --append)")
    j.add_argument("--append", action="store_true")
    j.set_defaults(func=cmd_justify)

    st = sub.add_parser("selftest", help="planted abstracts + published power values; exits 1 on FAIL",
                        epilog="example: effects.py selftest")
    st.set_defaults(func=cmd_selftest)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
