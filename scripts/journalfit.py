#!/usr/bin/env python3
"""journalfit.py - journal house profile and manuscript fit (research-paper-assistant).

What a journal actually publishes (reference counts, methods, sample sizes,
theories, countries, abstract length) and how close your abstract sits to its
recent papers. Everything is computed from OpenAlex records; nothing is
estimated. Similarity is lexical (TF-IDF cosine), so it measures vocabulary
overlap, not quality or novelty.

Commands
  profile   house profile of one journal from its recent articles
  fit       rank journals by similarity between your abstract and their recent abstracts
  compare   side-by-side of a manuscript against a saved profile (hints, never rules)
  selftest  offline checks on synthetic data (no network)

OpenAlex credits: profile = 1 per page of 100 papers (max 2) + 1 for the
reference-recency sample. fit reuses profile_<issn>.json from --cache-dir when
it carries enough abstracts (60 of 100), otherwise it fetches a separate
has_abstract batch into profile_<issn>_abstracts.json (about 2 list calls);
pass --cached-only to forbid any fetch. Every command prints the planned
number of list calls at the start and the real number at the end.

Run with:  python -X utf8 journalfit.py <command> --help
"""

import argparse
import datetime as dt
import json
import math
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scholar import (openalex, rebuild_abstract, clean, table, short, hyphen_issn, TODAY, ARABIC_RE,
                     strip_references, extract_citations, HTTPError)

try:
    import numpy as np
except ImportError:
    sys.exit("numpy is missing: pip install numpy")

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

THIS_YEAR = dt.date.today().year
RECENT_YEARS = 5                      # "recent reference" = within this many years of the citing paper
WORK_FIELDS = ("id,doi,display_name,publication_year,referenced_works_count,cited_by_count,biblio,"
               "abstract_inverted_index,authorships,open_access,language,referenced_works")
CALLS = {"list": 0}                   # OpenAlex list calls made in this run (1 credit each)
ABSTRACT_MIN = 60                     # below this many abstracts 'fit' fetches its own has_abstract batch
ZERO_REF_GAP = 0.30                   # share of papers with referenced_works_count = 0 that marks an OpenAlex data gap
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")


def planned_calls(n, no_recency):
    """List calls one fetch of n papers costs: 1 per page of 100 (max 2) + 1 for the recency sample."""
    return min(2, max(1, math.ceil(n / 100))) + (0 if no_recency else 1)


def say_plan(n, why=""):
    print(f"this will cost about {n} list call{'s' if n != 1 else ''}" + (f" ({why})" if why else ""))


def say_calls():
    print(f"OpenAlex list calls this run: {CALLS['list']} (1 credit each)")

# ---------------------------------------------------------------- regex families (candidates, not rulings)

METHODS = {
    "sem_pls_cfa": re.compile(r"\b(SEM|PLS(?:-SEM)?|CFA|structural equation|confirmatory factor|partial least squares|"
                              r"measurement invariance|النمذجة بالمعادلات البنائية)\b"),
    "regression": re.compile(r"\b(regressions?|logistic|hierarchical linear|multilevel|mixed[- ]effects|moderat(?:ion|ed|ing)|"
                             r"mediat(?:ion|ed|ing)|الانحدار)\b", re.I),
    "anova_ttest": re.compile(r"\b(ANOVA|ANCOVA|MANOVA|t[- ]tests?|chi[- ]square[d]?|تحليل التباين)\b", re.I),
    "experiment": re.compile(r"\b(experiments?|experimental|randomi[sz]ed|randomly assigned|RCT|controlled trial|"
                             r"between[- ]subjects|within[- ]subjects|تجريبي)\b", re.I),
    "qualitative": re.compile(r"\b(qualitative|semi[- ]structured|interviews?|focus groups?|thematic analysis|grounded theory|"
                              r"ethnograph\w*|content analysis|نوعي|مقابلات)\b", re.I),
    "meta_analysis": re.compile(r"\b(meta-?analy\w*|systematic review|scoping review|التحليل البعدي)\b", re.I),
    "machine_learning": re.compile(r"\b(machine learning|deep learning|neural networks?|natural language processing|"
                                   r"classifiers?|random forest|support vector|large language models?|LLMs?|تعلم الآلة)\b", re.I),
    "survey": re.compile(r"\b(surveys?|questionnaires?|cross-sectional|self-report\w*|استبانة|استبيان)\b", re.I),
    "longitudinal": re.compile(r"\b(longitudinal|panel data|diary study|waves?\b|follow-up|طولية)\b", re.I),
}
THEORY_WORD = re.compile(r"\btheor(?:y|ies|etical(?:ly)?)\b|نظري", re.I)
NAMED_THEORY = re.compile(r"\b((?:[A-Z][\w'-]*(?:\s+(?:of|and|the))?\s+){1,4}(?:Theory|Model|Framework|Hypothesis))\b")
THEORY_OF = re.compile(r"\b(theory of (?:[a-z]+\s?){1,3})", re.I)
N_EQUALS = re.compile(r"\b[Nn]\s*=\s*(\d[\d,]*)")
COUNT_NOUN = re.compile(r"\b(\d[\d,]*)\s+(?:[a-z\-]+\s+){0,2}(?:participants|respondents|students|users|adults|adolescents|"
                        r"children|employees|patients|subjects|individuals|workers|teachers|nurses|consumers|undergraduates|"
                        r"people|men|women|households|firms|companies|gamers|players|customers|tweets|posts|videos|"
                        r"مشارك\w*|طالب\w*|مستجيب\w*)\b", re.I)
SAMPLE_OF = re.compile(r"\b(?:sample of|sample comprised|sample consisted of|data from|responses from|surveyed)\s+(\d[\d,]*)", re.I)
GENERIC_THEORY = {"the", "this", "a", "an", "our", "these", "proposed", "research", "conceptual", "theoretical", "new"}

# ---------------------------------------------------------------- tokeniser (English + Arabic)

STOP_EN = set("""a about above after again against all also although am among an and any are as at be because been
before being below between both but by can could did do does doing down during each few for from further had has have
having he her here hers herself him himself his how however i if in into is it its itself just let may me might more
most much must my myself no nor not of off on once only or other ought our ours ourselves out over own same she should
so some such than that the their theirs them themselves then there these they this those through thus to too under until
up upon us very was we were what when where whether which while who whom whose why will with within without would you
your yours yourself yourselves study studies results findings paper article research based using used use two three one
however therefore moreover furthermore well also among via per across toward towards whereas yet respectively significantly
significant effect effects relationship relationships role aims aim purpose present examine examines examined investigate
investigated investigates explore explores explored propose proposed show shows showed found find finds suggest suggests
suggested implications discussed discuss discusses data analysis analyses level levels high low higher lower n et al
""".split())
STOP_AR = set("""في من على إلى الى عن أن ان إن ما لا و او أو هذا هذه ذلك تلك التي الذي الذين كما بين مع قد تم كان كانت هو هي
هم هن حيث عند بعد قبل خلال حول لم لن ثم إذ إذا اذا كل بعض غير حتى أي اي أيضا ايضا الدراسة دراسة البحث بحث نتائج النتائج
هدفت هدف تهدف أظهرت اظهرت توصلت الى إلى عينة العينة""".split())
TOKEN_RE = re.compile(r"[^\W\d_]+(?:['\-][^\W\d_]+)*")
AR_MARKS = re.compile(r"[ً-ْٰـ]")


def normalize(text):
    t = clean(text).lower()
    t = AR_MARKS.sub("", t)
    t = re.sub("[أإآ]", "ا", t).replace("ى", "ي").replace("ة", "ه")
    return t


def tokens(text, bigrams=False):
    """Unigrams by default: bigrams inflate the vocabulary of short abstracts and flatten every cosine."""
    toks = [t for t in TOKEN_RE.findall(normalize(text))
            if len(t) > 1 and t not in STOP_EN and t not in STOP_AR]
    out = list(toks)
    if bigrams:
        out += [a + "_" + b for a, b in zip(toks, toks[1:])]
    return out


class TfIdf:
    """Sublinear tf, smoothed idf, L2 rows. Own implementation (numpy only)."""

    def __init__(self, docs, min_df=1):
        df = Counter()
        for toks in docs:
            df.update(set(toks))
        self.vocab = {t: i for i, t in enumerate(sorted(t for t, c in df.items() if c >= min_df))}
        self.df = df
        n = len(docs)
        self.idf = np.zeros(len(self.vocab))
        for t, i in self.vocab.items():
            self.idf[i] = math.log((1 + n) / (1 + df[t])) + 1

    def vector(self, toks):
        v = np.zeros(len(self.vocab))
        for t, c in Counter(toks).items():
            i = self.vocab.get(t)
            if i is not None:
                v[i] = (1 + math.log(c)) * self.idf[i]
        norm = np.linalg.norm(v)
        return v / norm if norm else v

    def matrix(self, docs):
        return np.vstack([self.vector(d) for d in docs]) if docs else np.zeros((0, len(self.vocab)))

    def top_terms(self, weights, k, min_df=1):
        inv = {i: t for t, i in self.vocab.items()}
        order = np.argsort(-weights)
        out = []
        for i in order:
            if weights[i] <= 0:
                break
            t = inv[int(i)]
            if self.df[t] >= min_df:
                out.append(t)
            if len(out) >= k:
                break
        return out


# ---------------------------------------------------------------- statistics helpers

def q_stats(values):
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return {"n": 0, "median": None, "q1": None, "q3": None, "mean": None}
    a = np.array(vals)
    return {"n": len(vals), "median": float(np.median(a)), "q1": float(np.percentile(a, 25)),
            "q3": float(np.percentile(a, 75)), "mean": float(a.mean())}


def fmt(v, d=0):
    if v is None:
        return "n/a"
    return f"{v:.{d}f}"


def pct(num, den):
    return f"{100.0 * num / den:.0f}%" if den else "n/a"


def to_int(s):
    try:
        return int(s.replace(",", ""))
    except ValueError:
        return None


def sample_sizes(text):
    """Candidate N values in a text (regex; the agent confirms). Returns the list of ints found."""
    found = []
    for rx in (N_EQUALS, COUNT_NOUN, SAMPLE_OF):
        for m in rx.finditer(text):
            v = to_int(m.group(1))
            if v is not None and 5 <= v <= 50_000_000 and not (1900 <= v <= THIS_YEAR and rx is COUNT_NOUN and "," not in m.group(1)
                                                                 and re.search(r"\bin\s*$", text[max(0, m.start() - 4): m.start()])):
                found.append(v)
    return found


def named_theories(text):
    out = set()
    for m in NAMED_THEORY.finditer(text):
        name = re.sub(r"\s+", " ", m.group(1)).strip()
        words = name.lower().split()
        if len(words) >= 2 and words[0] not in GENERIC_THEORY and not all(w in GENERIC_THEORY | {"theory", "model", "framework", "hypothesis"} for w in words):
            out.add(" ".join(words))
    for m in THEORY_OF.finditer(text):
        out.add(re.sub(r"\s+", " ", m.group(1)).strip().lower())
    # 'spike model' inside 'cvm-based spike model': keep the longer name only.
    return {t for t in out if not any(o != t and o.endswith(" " + t) for o in out)}


def method_hits(text):
    return {k: bool(rx.search(text)) for k, rx in METHODS.items()}


# ---------------------------------------------------------------- OpenAlex fetch

def resolve_source(issn):
    issn = hyphen_issn(issn)
    if not issn:
        sys.exit(f"ERROR: '{issn}' is not an ISSN (expected 8 digits, e.g. 0747-5632)")
    src = openalex("sources/issn:" + issn, {"select": "id,display_name,issn_l,issn,works_count,is_core,host_organization_name"})
    if not src:
        sys.exit(f"ERROR: OpenAlex has no source with ISSN {issn}. Check the ISSN on the journal's own site.")
    return issn, src


def fetch_works(issn, n, since, has_abstract=False):
    """Recent articles of one journal, newest first. 1 credit per page, at most 2 pages."""
    filters = [f"primary_location.source.issn:{issn}", "type:article", f"from_publication_date:{since}-01-01"]
    if has_abstract:
        filters.append("has_abstract:true")
    works, page = [], 1
    while len(works) < n and page <= 2:
        per_page = min(100, n - len(works))
        data = openalex("works", {"filter": ",".join(filters), "sort": "publication_date:desc", "per_page": per_page,
                                  "page": page, "select": WORK_FIELDS})
        CALLS["list"] += 1
        res = (data or {}).get("results", [])
        works += res
        if len(res) < per_page:
            break
        page += 1
    total = (data or {}).get("meta", {}).get("count")
    return works, total, ",".join(filters)


def paper_row(w):
    auths = w.get("authorships") or []
    countries = sorted({c for a in auths for c in (a.get("countries") or [])})
    bib = w.get("biblio") or {}
    return {
        "id": (w.get("id") or "").rsplit("/", 1)[-1],
        "doi": re.sub(r"^https?://doi\.org/", "", w.get("doi") or ""),
        "title": clean(w.get("display_name")),
        "year": w.get("publication_year"),
        "n_refs": w.get("referenced_works_count"),
        "cited_by": w.get("cited_by_count"),
        "n_authors": len(auths),
        "countries": countries,
        "is_oa": bool((w.get("open_access") or {}).get("is_oa")),
        "language": w.get("language"),
        "volume": bib.get("volume"),
        "abstract": rebuild_abstract(w.get("abstract_inverted_index")),
        "referenced_works": [r.rsplit("/", 1)[-1] for r in (w.get("referenced_works") or [])],
    }


def reference_recency(papers, per_paper=10, n_papers=10):
    """Sample up to 10 refs from each of 10 papers, fetch their years in ONE batch call (1 credit)."""
    sample = []                                   # (paper id, paper year, referenced work id)
    for p in [p for p in papers if p["referenced_works"] and p["year"]][:n_papers]:
        ids = p["referenced_works"]
        step = max(1, len(ids) // per_paper)
        for rid in ids[::step][:per_paper]:
            sample.append((p["id"], p["year"], rid))
    if not sample:
        return {"sampled_refs": 0, "from_papers": 0, "share_recent": None, "median_age": None, "note": "no referenced_works in the batch"}
    ids = sorted({rid for _, _, rid in sample})[:100]
    try:
        data = openalex("works", {"filter": "openalex_id:" + "|".join(ids), "per_page": 100, "select": "id,publication_year"})
        CALLS["list"] += 1
    except HTTPError as e:
        return {"sampled_refs": len(ids), "from_papers": 0, "share_recent": None, "median_age": None, "note": f"batch call failed: {e}"}
    years = {(w.get("id") or "").rsplit("/", 1)[-1]: w.get("publication_year") for w in (data or {}).get("results", [])}
    ages = [(pid, py - years[rid]) for pid, py, rid in sample if years.get(rid)]
    if not ages:
        return {"sampled_refs": len(ids), "from_papers": 0, "share_recent": None, "median_age": None, "note": "no years returned"}
    recent = sum(1 for _, age in ages if age <= RECENT_YEARS)
    n_from = len({pid for pid, _ in ages})
    return {"sampled_refs": len(ages), "from_papers": n_from, "share_recent": recent / len(ages),
            "median_age": float(np.median([age for _, age in ages])),
            "note": f"{len(ages)} references sampled from {n_from} papers, not the full reference lists"}


# ---------------------------------------------------------------- profile

def build_profile(papers, src, issn, since, filters, total, recency=None):
    n = len(papers)
    with_abs = [p for p in papers if p["abstract"]]
    abs_words = [len(p["abstract"].split()) for p in with_abs]
    meth = Counter()
    ns, theory_hits, named = [], 0, Counter()
    for p in with_abs:
        for k, hit in method_hits(p["abstract"]).items():
            meth[k] += hit
        sizes = sample_sizes(p["abstract"])
        if sizes:
            ns.append(max(sizes))
        if THEORY_WORD.search(p["abstract"]):
            theory_hits += 1
        for t in named_theories(p["abstract"]):
            named[t] += 1
    countries = Counter(c for p in papers for c in p["countries"])
    langs = Counter(p["language"] or "unknown" for p in papers)
    docs = [tokens(p["abstract"]) for p in with_abs]
    top_terms = []
    if docs:
        tf = TfIdf(docs)
        top_terms = tf.top_terms(tf.matrix(docs).mean(axis=0), 40, min_df=2)
    # OpenAlex stores referenced_works_count = 0 when it has no reference list for a paper (common for
    # regional and non-English journals): a median over those zeros would be a data gap, not a house style.
    refs_zero = sum(1 for p in papers if not p["n_refs"])
    return {
        "issn": issn, "issn_l": src.get("issn_l"), "journal": src.get("display_name"), "openalex_source": src.get("id"),
        "publisher": src.get("host_organization_name"), "built": TODAY, "filter": filters, "since": since,
        "n_papers": n, "n_matching_total": total, "n_with_abstract": len(with_abs),
        "refs": q_stats([p["n_refs"] for p in papers]),
        "refs_zero": refs_zero, "refs_gap": bool(n) and refs_zero / n > ZERO_REF_GAP,
        "refs_nonzero": q_stats([p["n_refs"] for p in papers if p["n_refs"]]),
        "authors": q_stats([p["n_authors"] for p in papers]),
        "abstract_words": q_stats(abs_words),
        "oa_share": (sum(p["is_oa"] for p in papers) / n) if n else None,
        "languages": dict(langs.most_common(5)),
        "methods_share": {k: (meth[k] / len(with_abs) if with_abs else None) for k in METHODS},
        "sample_n": q_stats(ns), "sample_n_hits": len(ns),
        "theory_share": (theory_hits / len(with_abs)) if with_abs else None,
        "named_theories": named.most_common(10),
        "countries": [(c, k) for c, k in countries.most_common(12)],
        "top_terms": top_terms,
        "recency_sample": recency,
        "papers": [{k: p[k] for k in ("id", "doi", "title", "year", "n_refs", "n_authors", "is_oa", "abstract")} for p in papers],
    }


def ref_stats(pr):
    """(quartile stats, label) for the reference count. Profiles saved before the data-gap check lack the
    new keys, so the gap is recomputed from the paper rows when needed."""
    if "refs_gap" not in pr:
        n_refs = [p.get("n_refs") for p in pr.get("papers", [])]
        pr["refs_zero"] = sum(1 for v in n_refs if not v)
        pr["refs_gap"] = bool(n_refs) and pr["refs_zero"] / len(n_refs) > ZERO_REF_GAP
        pr["refs_nonzero"] = q_stats([v for v in n_refs if v])
    if pr["refs_gap"]:
        return pr["refs_nonzero"], (f"papers with refs only: {pr['refs_zero']} of {pr['n_papers']} have no reference "
                                    "list in OpenAlex (data gap)")
    return pr["refs"], "OpenAlex referenced_works_count"


def profile_markdown(pr):
    L = [f"# House profile: {pr['journal']} (ISSN {pr['issn']})",
         f"Source: OpenAlex, {pr['n_papers']} most recent articles since {pr['since']} "
         f"(of {pr['n_matching_total']} matching), built {pr['built']}. Abstracts available for {pr['n_with_abstract']}.",
         "All shares below are computed on the papers WITH abstracts; sample sizes, methods and theories are regex candidates.", ""]
    r, a, w = pr["refs"], pr["authors"], pr["abstract_words"]
    rows = []
    if pr["refs_gap"]:
        rn = pr["refs_nonzero"]
        rows.append(["references per paper", f"not available in OpenAlex for {pr['refs_zero']} of {pr['n_papers']} papers (data gap)",
                     "referenced_works_count = 0 means OpenAlex has no reference list, not a paper without references"])
        rows.append(["references per paper (papers with refs only)",
                     f"median {fmt(rn['median'])} (IQR {fmt(rn['q1'])} to {fmt(rn['q3'])}) over {rn['n']} papers" if rn["n"] else "NOT FOUND",
                     "referenced_works_count > 0; check a few reference lists in the journal itself"])
    else:
        rows.append(["references per paper", f"median {fmt(r['median'])} (IQR {fmt(r['q1'])} to {fmt(r['q3'])})",
                     "OpenAlex referenced_works_count" + (f" ({pr['refs_zero']} papers with 0: possible gaps)" if pr["refs_zero"] else "")])
    rows += [["authors per paper", f"median {fmt(a['median'])}, mean {fmt(a['mean'], 1)}", "authorships"],
            ["abstract length (words)", f"median {fmt(w['median'])} (IQR {fmt(w['q1'])} to {fmt(w['q3'])})", f"{w['n']} abstracts"],
            ["open access share", pct(round((pr['oa_share'] or 0) * pr['n_papers']), pr['n_papers']), "open_access.is_oa"],
            ["languages", ", ".join(f"{k} {v}" for k, v in pr["languages"].items()), "language"],
            ["mentions theory", pct(round((pr['theory_share'] or 0) * pr['n_with_abstract']), pr['n_with_abstract']), "regex 'theory/theoretical'"]]
    sn = pr["sample_n"]
    if sn["n"]:
        rows.append(["typical sample size (N)", f"median {fmt(sn['median'])} (IQR {fmt(sn['q1'])} to {fmt(sn['q3'])}) from {sn['n']} abstracts with an N",
                     "regex 'N =', '<n> participants', 'sample of': CONFIRM in the papers"])
    else:
        rows.append(["typical sample size (N)", "NOT FOUND in abstracts", "regex found no N"])
    rec = pr.get("recency_sample") or {}
    if rec.get("share_recent") is not None:
        rows.append([f"references within {RECENT_YEARS} years of the paper", f"{rec['share_recent'] * 100:.0f}% (median age {fmt(rec['median_age'])} years)",
                     f"SAMPLE: {rec['note']}"])
    else:
        rows.append([f"references within {RECENT_YEARS} years", "NOT CHECKED", rec.get("note", "no sample")])
    L.append(table(rows, ["measure", "value", "basis"]))
    L += ["", "## Method families (share of abstracts matching the regex)",
          table([[k, pct(round((v or 0) * pr['n_with_abstract']), pr['n_with_abstract'])] for k, v in pr["methods_share"].items()],
                ["family", "share"])]
    if pr["named_theories"]:
        L += ["", "## Named theories / models (regex candidates)",
              table([[t, str(c)] for t, c in pr["named_theories"]], ["name", "papers"])]
    L += ["", "## Author countries (institution country codes, papers with at least one author there)",
          table([[c, str(k), pct(k, pr['n_papers'])] for c, k in pr["countries"]], ["country", "papers", "share"])]
    L += ["", "## Top terms (mean TF-IDF over abstracts)", ", ".join(pr["top_terms"][:40]) or "n/a"]
    L += ["", "## Newest papers in the batch",
          table([[short(p["title"], 70), str(p["year"]), p["doi"] or "no DOI", str(p["n_refs"])] for p in pr["papers"][:8]],
                ["title", "year", "DOI", "refs"])]
    L += ["", "Not checked: acceptance rate, review time, APC, scope statement (read the journal's own site). "
              "Method and theory shares depend on abstract wording and miss what the abstract does not say."]
    return "\n".join(L)


def cmd_profile(a):
    say_plan(planned_calls(a.n, a.no_recency), f"{math.ceil(a.n / 100)} page(s) of works"
             + ("" if a.no_recency else " + 1 reference-recency batch") + "; the source lookup is free")
    issn, src = resolve_source(a.issn)
    print(f"profile: {src.get('display_name')} | ISSN {issn} | fetching up to {a.n} articles since {a.since}")
    works, total, filters = fetch_works(issn, a.n, a.since, a.has_abstract)
    papers = [paper_row(w) for w in works]
    if not papers:
        sys.exit(f"ERROR: no articles found for ISSN {issn} since {a.since} (filter: {filters})")
    rec = None if a.no_recency else reference_recency(papers)
    pr = build_profile(papers, src, issn, a.since, filters, total, rec)
    md = profile_markdown(pr)
    out = a.out or f"profile_{issn}.md"
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(md + "\n")
    print(md)
    print(f"\nwritten: {os.path.abspath(out)}")
    if a.json:
        jpath = os.path.splitext(out)[0] + ".json"
        with open(jpath, "w", encoding="utf-8", newline="\n") as f:
            json.dump(pr, f, ensure_ascii=False, indent=1)
        print(f"written: {os.path.abspath(jpath)} (reused by 'fit' and 'compare')")
    if pr["n_with_abstract"] < ABSTRACT_MIN:
        print(f"WARNING: only {pr['n_with_abstract']} of {pr['n_papers']} papers carry an abstract in OpenAlex (fewer than {ABSTRACT_MIN}). "
              f"'fit' at its default --n 100 needs {ABSTRACT_MIN}, so it will not reuse this profile: it fetches a separate "
              f"has_abstract batch into profile_{issn}_abstracts.json (2 list calls: 1 page + 1 recency sample) unless you pass --cached-only.")
    if pr["refs_gap"]:
        print(f"NOTE: {pr['refs_zero']} of {pr['n_papers']} papers have referenced_works_count = 0: OpenAlex has no reference list "
              "for them, so the reference count is a data gap, not a house norm.")


# ---------------------------------------------------------------- fit

def load_abstract(path):
    if not os.path.exists(path):
        sys.exit(f"ERROR: abstract file not found: {path}")
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    text = re.sub(r"^#.*$", "", text, flags=re.M).strip()
    if len(tokens(text, bigrams=False)) < 5:
        sys.exit(f"ERROR: abstract file is empty or has fewer than 5 content words: {path}. "
                 "Paste the abstract text (English for English-language journals) and run again.")
    return text


def check_language(text):
    """fit is lexical, so an abstract must share a script with the journal's abstracts. No Latin words at all
    means nothing can match an English-language journal: stop with exit 1 and say what to do."""
    latin = len(LATIN_WORD.findall(text))
    arabic = sum(1 for w in text.split() if ARABIC_RE.search(w))
    if latin == 0:
        sys.exit("ERROR: the abstract has no Latin-script words (Arabic only). Fit compares vocabulary (TF-IDF) with the "
                 "journal's OpenAlex abstracts, and English-language journals need an English abstract: translate it to "
                 "English, save that text to a file and run fit again. Keep the Arabic file for an Arabic-language journal.")
    if arabic > latin:
        print(f"NOTE: the abstract is mostly Arabic ({arabic} Arabic words, {latin} Latin words). Only the Latin words can "
              "match an English-language journal, so the fit score will be low: translate the whole abstract to English "
              "for a meaningful fit.")
    return latin, arabic


def cached_profiles(issn, cache_dir):
    """[(file name, profile)] for one ISSN: the user's profile first, then fit's own has_abstract batch."""
    out = []
    for name in (f"profile_{issn}.json", f"profile_{issn}_abstracts.json"):
        path = os.path.join(cache_dir, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                out.append((name, json.load(f)))
    return out


def abstracts_needed(a):
    return max(10, int(0.6 * a.n))


def fit_plan(a):
    """List calls fit will make: 0 for every ISSN with a usable cache (or under --cached-only), one fetch otherwise."""
    total, missing = 0, []
    for raw in a.issn:
        issn = hyphen_issn(raw) or raw
        if any(pr.get("n_with_abstract", 0) >= abstracts_needed(a) for _, pr in cached_profiles(issn, a.cache_dir)):
            continue
        missing.append(issn)
        if not a.cached_only:
            total += planned_calls(a.n, a.no_recency)
    return total, missing


def load_or_build_profile(issn_raw, a):
    """A cached profile_<issn>.json (from 'profile --json') is reused when at least 60% of its papers carry an
    abstract; otherwise fit fetches abstract-bearing papers into profile_<issn>_abstracts.json (never overwriting
    the user's profile, whose reference and OA statistics are unbiased). --cached-only never fetches: it takes the
    best cached file with a warning, or stops with exit 1 when none exists."""
    issn = hyphen_issn(issn_raw)
    if not issn:
        sys.exit(f"ERROR: '{issn_raw}' is not an ISSN (expected 8 digits, e.g. 0747-5632)")
    need = abstracts_needed(a)
    cached = cached_profiles(issn, a.cache_dir)
    for name, pr in cached:
        if pr.get("n_with_abstract", 0) >= need:
            print(f"[{issn}] using cached {name} (built {pr.get('built')}, {pr['n_with_abstract']} abstracts)")
            return pr
        print(f"[{issn}] {name} has only {pr.get('n_with_abstract')} abstracts (need {need})")
    if a.cached_only:
        if cached:
            name, pr = max(cached, key=lambda x: x[1].get("n_with_abstract", 0))
            print(f"[{issn}] --cached-only: using {name} anyway ({pr.get('n_with_abstract')} abstracts, no fetch); "
                  "the fit score rests on fewer papers than intended")
            return pr
        sys.exit(f"ERROR: --cached-only but no cached profile for {issn} in {os.path.abspath(a.cache_dir)}: expected "
                 f"profile_{issn}_abstracts.json (written by a previous 'fit') or profile_{issn}.json (from 'profile --json'). "
                 f"Run fit without --cached-only to fetch it (about {planned_calls(a.n, a.no_recency)} list calls).")
    cache = os.path.join(a.cache_dir, f"profile_{issn}_abstracts.json")
    issn, src = resolve_source(issn)
    print(f"[{issn}] fetching up to {a.n} articles with abstracts since {a.since} for {src.get('display_name')}")
    works, total, filters = fetch_works(issn, a.n, a.since, has_abstract=True)
    papers = [paper_row(w) for w in works]
    if not papers:
        sys.exit(f"ERROR: no articles with abstracts for ISSN {issn} since {a.since}")
    rec = None if a.no_recency else reference_recency(papers)
    pr = build_profile(papers, src, issn, a.since, filters, total, rec)
    with open(cache, "w", encoding="utf-8", newline="\n") as f:
        json.dump(pr, f, ensure_ascii=False, indent=1)
    print(f"[{issn}] profile cached: {os.path.abspath(cache)}")
    return pr


def score_fit(user_text, pr, threshold, top_k=10):
    """Returns a dict of similarity measures between the user's abstract and one journal's abstracts."""
    papers = [p for p in pr["papers"] if p.get("abstract")]
    docs = [tokens(p["abstract"]) for p in papers]
    user = tokens(user_text)
    tf = TfIdf(docs + [user])
    M = tf.matrix(docs)
    u = tf.vector(user)
    sims = M @ u
    order = np.argsort(-sims)
    top = order[:top_k]
    mean_top = float(sims[top].mean()) if len(top) else 0.0
    share_above = float((sims >= threshold).mean()) if len(sims) else 0.0
    # Self-calibration: how close the journal's own papers sit to their nearest sibling. A manuscript whose
    # top-10 mean reaches that level reads like one of them; the ratio is capped at 1.
    ref_level = 0.0
    if len(docs) >= 2:
        MM = M @ M.T
        np.fill_diagonal(MM, -1.0)
        ref_level = float(np.median(MM.max(axis=1)))
    closeness = min(1.0, mean_top / ref_level) if ref_level > 0 else 0.0
    journal_terms = tf.top_terms(M.mean(axis=0), 30, min_df=2) if len(docs) else []
    user_terms = tf.top_terms(u, 15)
    overlap = len(set(user_terms) & set(journal_terms)) / 15.0 if user_terms else 0.0
    key_terms = set(user_terms[:10])
    recent_share2 = []
    for p, toks in zip(papers, docs):
        if p.get("year") and p["year"] >= THIS_YEAR - 3:
            shared = key_terms & set(toks)
            if len(shared) >= 2:
                recent_share2.append((p, sorted(shared)))
    fit = 100 * (0.5 * closeness + 0.3 * share_above + 0.2 * overlap)
    if fit >= 50 and recent_share2:
        risk = "low"
    elif fit < 25 or not recent_share2:
        risk = "high"
    else:
        risk = "medium"
    return {"fit": fit, "mean_top": mean_top, "ref_level": ref_level, "closeness": closeness, "share_above": share_above,
            "overlap": overlap, "nearest": [(papers[int(i)], float(sims[int(i)])) for i in order[:3]],
            "user_terms": user_terms, "journal_terms": journal_terms, "shared_terms": sorted(key_terms & set(journal_terms)),
            "recent_share2": recent_share2, "risk": risk, "n_docs": len(docs)}


def expects(pr):
    r, label = ref_stats(pr)
    sn = pr["sample_n"]
    ms = sorted(((k, v or 0) for k, v in pr["methods_share"].items()), key=lambda x: -x[1])[:3]
    meth = ", ".join(f"{k} {v * 100:.0f}%" for k, v in ms)
    n_txt = f"N median {fmt(sn['median'])}" if sn["n"] else "N not found"
    if not pr["refs_gap"]:
        refs = f"refs median {fmt(r['median'])} (IQR {fmt(r['q1'])} to {fmt(r['q3'])})"
    elif r["n"]:
        refs = (f"refs median {fmt(r['median'])} over papers with refs; {pr['refs_zero']} of {pr['n_papers']} "
                "lack refs in OpenAlex (data gap)")
    else:
        refs = f"refs: not available in OpenAlex for {pr['refs_zero']} of {pr['n_papers']} papers (data gap)"
    return f"{refs}; {meth}; {n_txt}"


def cmd_fit(a):
    text = load_abstract(a.abstract)
    check_language(text)
    plan, missing = fit_plan(a)
    if a.cached_only:
        say_plan(0, "--cached-only: no fetch" + (f"; no usable cache for {', '.join(missing)}" if missing else ""))
    else:
        say_plan(plan, f"{len(a.issn) - len(missing)} of {len(a.issn)} journals cached"
                 + (f"; fetching has_abstract batches for {', '.join(missing)}" if missing else ""))
    results = []
    for issn in a.issn:
        pr = load_or_build_profile(issn, a)
        s = score_fit(text, pr, a.threshold)
        if s["n_docs"] < 10:
            print(f"[{pr['issn']}] WARNING: only {s['n_docs']} abstracts; the fit score is unreliable")
        results.append((pr, s))
    results.sort(key=lambda x: -x[1]["fit"])
    L = [f"# Journal fit for {os.path.basename(a.abstract)} ({TODAY})",
         f"Fit = 0.5*closeness + 0.3*share(sim >= {a.threshold}) + 0.2*keyword overlap, scaled to 100, where closeness = "
         "mean of your top-10 cosines divided by the journal's own median nearest-neighbour cosine (capped at 1). "
         "TF-IDF cosine on abstracts (lexical: vocabulary overlap, not quality). Desk-reject risk is a heuristic: "
         "low = fit 50+ and a paper of the last 3 years shares 2+ of your key terms; high = fit under 25 or no such paper.", ""]
    rows = []
    for pr, s in results:
        near = "; ".join(f"{short(p['title'], 60)} ({p['year']}, {p['doi'] or 'no DOI'})" for p, _ in s["nearest"])
        rows.append([f"{pr['journal']} ({pr['issn']})", f"{s['fit']:.0f}", near, s["risk"], expects(pr)])
    L.append(table(rows, ["journal", "fit score", "nearest 3 papers (title, year, DOI)", "desk-reject risk", "what the profile expects"]))
    for pr, s in results:
        L += ["", f"## {pr['journal']} ({pr['issn']})",
              f"- abstracts compared: {s['n_docs']} (since {pr['since']}, built {pr['built']})",
              f"- mean of top-10 similarities: {s['mean_top']:.3f} vs the journal's own nearest-neighbour median {s['ref_level']:.3f} "
              f"(closeness {s['closeness'] * 100:.0f}%); share of papers with sim >= {a.threshold}: {s['share_above'] * 100:.0f}%",
              f"- your key terms: {', '.join(s['user_terms'][:10])}",
              f"- journal top terms: {', '.join(s['journal_terms'][:20])}",
              f"- shared key terms: {', '.join(s['shared_terms']) or 'none'} (overlap {s['overlap'] * 100:.0f}%)",
              f"- papers in the last 3 years sharing 2+ key terms: {len(s['recent_share2'])}"
              + (f", e.g. {short(s['recent_share2'][0][0]['title'], 70)} ({s['recent_share2'][0][0]['year']}): "
                 f"{', '.join(s['recent_share2'][0][1])}" if s["recent_share2"] else ""),
              "- nearest papers:"]
        for p, sim in s["nearest"]:
            L.append(f"  - {sim:.3f} | {p['title']} ({p['year']}) https://doi.org/{p['doi']}" if p["doi"] else f"  - {sim:.3f} | {p['title']} ({p['year']})")
    L += ["", "Not checked: the journal's stated scope, special issues, APC, review time. A high fit means your vocabulary "
              "matches recent papers; read the nearest 3 before deciding."]
    md = "\n".join(L)
    print(md)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(md + "\n")
        print(f"\nwritten: {os.path.abspath(a.out)}")


# ---------------------------------------------------------------- compare

def manuscript_facts(path, evidence=None):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    body, refs = strip_references(text)
    entries = [e.strip() for e in re.split(r"\n\s*\n", refs) if e.strip() and not e.strip().startswith("#")] if refs else []
    ref_years = []
    for e in entries:
        m = re.search(r"\b((?:19|20)\d{2})\b", e)
        if m:
            ref_years.append(int(m.group(1)))
    cites = extract_citations(body)
    cite_years = [int(y[:4]) for _, y, _ in cites if re.match(r"(19|20)\d{2}", y)]
    n_from, n_vals = "", []
    if evidence and os.path.exists(evidence):
        with open(evidence, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r"\s*([\w.~\-]+)\.n\s*=\s*(\d+)", line)
                if m:
                    n_vals.append(int(m.group(2)))
        if n_vals:
            n_from = f"evidence {os.path.basename(evidence)} (max of *.n)"
    if not n_vals:
        n_vals = sample_sizes(body)
        if n_vals:
            n_from = "manuscript text (regex candidate: CONFIRM)"
    abs_m = re.search(r"^#{1,6}\s*(abstract|الملخص|ملخص)\s*$(.*?)(?=^#{1,6}\s|\Z)", text, re.I | re.M | re.S)
    abs_words = len(abs_m.group(2).split()) if abs_m else None
    return {"n_refs": len(entries), "ref_years": ref_years, "n_cites": len(cites), "cite_years": cite_years,
            "N": max(n_vals) if n_vals else None, "N_from": n_from, "methods": {k: len(rx.findall(body)) for k, rx in METHODS.items()},
            "theories": sorted(named_theories(body)), "abstract_words": abs_words, "has_ref_list": bool(refs)}


def verdict(value, q1, q3):
    if value is None or q1 is None:
        return "n/a"
    if value < q1:
        return "below"
    if value > q3:
        return "above"
    return "ok"


def cmd_compare(a):
    say_plan(0, "compare reads a saved profile, no network")
    if not os.path.exists(a.profile):
        sys.exit(f"ERROR: profile not found: {a.profile} (run 'profile --issn X --json' first)")
    with open(a.profile, encoding="utf-8") as f:
        pr = json.load(f)
    if not os.path.exists(a.manuscript):
        sys.exit(f"ERROR: manuscript not found: {a.manuscript}")
    m = manuscript_facts(a.manuscript, a.evidence)
    print(f"compare: {os.path.basename(a.manuscript)} vs {pr['journal']} ({pr['issn']}, profile built {pr['built']}, "
          f"{pr['n_papers']} papers since {pr['since']})")
    print("Hints only: a journal publishes outside its typical range all the time. 'below/above' means outside the IQR.\n")
    rows = []
    r, label = ref_stats(pr)
    if pr["refs_gap"] and not r["n"]:
        rows.append(["references in list", str(m["n_refs"]) if m["has_ref_list"] else "no reference list found",
                     f"not available in OpenAlex for {pr['refs_zero']} of {pr['n_papers']} papers (data gap)", "n/a"])
    else:
        rows.append(["references in list", str(m["n_refs"]) if m["has_ref_list"] else "no reference list found",
                     f"median {fmt(r['median'])} (IQR {fmt(r['q1'])} to {fmt(r['q3'])})" + (f"; {label}" if pr["refs_gap"] else ""),
                     verdict(m["n_refs"], r["q1"], r["q3"]) if m["has_ref_list"] else "n/a"])
    years = m["ref_years"] or m["cite_years"]
    basis = "reference list years" if m["ref_years"] else "in-text citation years"
    rec = pr.get("recency_sample") or {}
    if years:
        recent = sum(1 for y in years if y >= THIS_YEAR - RECENT_YEARS) / len(years)
        js = rec.get("share_recent")
        hint = "n/a" if js is None else ("ok" if recent >= js - 0.15 else "below")
        rows.append([f"share of references from the last {RECENT_YEARS} years", f"{recent * 100:.0f}% ({basis}, {len(years)} years)",
                     f"{js * 100:.0f}% (sample, {rec.get('note')})" if js is not None else "not sampled", hint])
    else:
        rows.append([f"share of references from the last {RECENT_YEARS} years", "no years found", "", "n/a"])
    rows.append(["in-text citations (author-year)", str(m["n_cites"]), "", ""])
    sn = pr["sample_n"]
    rows.append(["sample size N", f"{m['N']} ({m['N_from']})" if m["N"] else "NOT FOUND",
                 f"median {fmt(sn['median'])} (IQR {fmt(sn['q1'])} to {fmt(sn['q3'])}, {sn['n']} abstracts)" if sn["n"] else "not found in abstracts",
                 verdict(m["N"], sn["q1"], sn["q3"]) if sn["n"] else "n/a"])
    if m["abstract_words"] is not None:
        w = pr["abstract_words"]
        rows.append(["abstract length (words)", str(m["abstract_words"]), f"median {fmt(w['median'])} (IQR {fmt(w['q1'])} to {fmt(w['q3'])})",
                     verdict(m["abstract_words"], w["q1"], w["q3"])])
    for k, cnt in m["methods"].items():
        share = pr["methods_share"].get(k)
        if cnt or (share or 0) >= 0.3:
            js = f"{share * 100:.0f}% of abstracts" if share is not None else "n/a"
            if cnt and share is not None:
                hint = "common here" if share >= 0.2 else ("seen here" if share >= 0.05 else "rare here (under 5%): explain the choice")
            elif cnt:
                hint = "n/a"
            else:
                hint = "frequent here, absent in your text"
            rows.append([f"method words: {k}", f"{cnt} mention(s)", js, hint])
    print(table(rows, ["item", "manuscript", "journal profile", "hint"]))
    if m["theories"]:
        named = [t for t, _ in pr.get("named_theories", [])]
        print("\nTheories named in the manuscript (regex): " + "; ".join(
            f"{t} ({'also in the journal sample' if t in named else 'not in the journal sample'})" for t in m["theories"]))
    print("\nNot checked: writing style, scope, figures, word count. Confirm N and methods against the manuscript itself.")


# ---------------------------------------------------------------- selftest (offline)

SYN_SOCIAL = [
    "Facebook use and academic performance among university students: self-reported grade point average and hours studying per week.",
    "Social media multitasking while studying predicts lower academic performance in undergraduates; N = 403 students completed a survey.",
    "Social networking sites, sleep duration and learning activities: a cross-sectional questionnaire among 300 female students.",
    "Smartphone addiction, social comparison and well-being: Social Cognitive Theory guides a survey of 250 adolescents.",
    "Instagram use, body image and self-esteem among young adults: a regression study with 512 respondents.",
    "Problematic social media use and academic procrastination: structural equation modelling of 620 participants.",
    "Online gaming, flow and academic engagement: an experiment with randomly assigned conditions.",
    "Technology Acceptance Model and e-learning adoption during the pandemic: PLS-SEM with 380 university students.",
    "Digital distraction in lectures: a longitudinal diary study of laptop and phone use.",
    "Parasocial relationships with influencers and purchase intention: a survey of 410 followers.",
    "Cyberbullying victimisation and depressive symptoms in adolescents: a meta-analysis of 54 studies.",
    "Screen time and sleep quality among children: machine learning classifiers on wearable data.",
]
SYN_MEDICAL = [
    "Efficacy and safety of a novel anticoagulant in atrial fibrillation: a randomised controlled trial.",
    "Global burden of ischaemic heart disease 1990 to 2021: a systematic analysis.",
    "Chemotherapy versus immunotherapy in non-small-cell lung cancer: phase 3 trial results.",
    "Maternal mortality trends in low-income countries: cross-national analysis of vital registration data.",
    "Antimicrobial resistance in bloodstream infections: a multicentre cohort study.",
    "Dengue vaccine effectiveness in children: a cluster randomised trial.",
    "Hypertension control and stroke incidence: a population cohort of 1.2 million adults.",
    "Tuberculosis treatment outcomes with shortened regimens: a non-inferiority trial.",
    "Malaria prevention with seasonal chemoprevention: cluster trial in the Sahel.",
    "Cardiovascular outcomes of SGLT2 inhibitors in heart failure: pooled analysis.",
    "Neonatal sepsis management in district hospitals: a stepped-wedge trial.",
    "Surgical site infection rates after colorectal surgery: a prospective cohort.",
]


def synthetic_profile(abstracts, name, issn, zero_refs=0):
    """zero_refs: how many of the papers get referenced_works_count = 0 (the OpenAlex data-gap case)."""
    papers = [{"id": f"W{i}", "doi": f"10.0000/syn.{i}", "title": ab.split(":")[0], "year": THIS_YEAR - (i % 4),
               "n_refs": 0 if i < zero_refs else 40 + 3 * i, "cited_by": 0, "n_authors": 2 + i % 4,
               "countries": ["US"] if i % 2 else ["CN"], "is_oa": bool(i % 3), "language": "en", "volume": "1",
               "abstract": ab, "referenced_works": []}
              for i, ab in enumerate(abstracts)]
    src = {"id": "S0", "display_name": name, "issn_l": issn, "host_organization_name": "synthetic"}
    return build_profile(papers, src, issn, THIS_YEAR - 4, "synthetic", len(papers), None)


def cmd_selftest(a):
    say_plan(0, "selftest is offline")
    fails = []

    def check(cond, label):
        print(f"{'PASS' if cond else 'FAIL'}: {label}")
        if not cond:
            fails.append(label)

    # 1. TF-IDF sanity
    d1, d2, d3 = tokens("social media use and academic performance"), tokens("social media use and academic performance"), tokens("cardiac surgery outcomes")
    tf = TfIdf([d1, d2, d3])
    v1, v2, v3 = tf.vector(d1), tf.vector(d2), tf.vector(d3)
    check(abs(float(v1 @ v2) - 1.0) < 1e-9, "identical documents have cosine 1.0")
    check(float(v1 @ v3) == 0.0, "disjoint documents have cosine 0.0")
    # 2. Arabic tokens
    ar1 = tokens("أثر استخدام وسائل التواصل الاجتماعي على التحصيل الأكاديمي لطلبة الجامعة")
    ar2 = tokens("استخدام وسائل التواصل الاجتماعي والتحصيل الأكاديمي لدى الطلبة")
    ar3 = tokens("فعالية العلاج الكيميائي في سرطان الرئة")
    tfa = TfIdf([ar1, ar2, ar3])
    check(float(tfa.vector(ar1) @ tfa.vector(ar2)) > float(tfa.vector(ar1) @ tfa.vector(ar3)), "Arabic: similar abstracts score higher than unrelated")
    # 3. Fit ranking on synthetic journals
    user = ("This survey study examines Facebook and social media use among university students and its relation to "
            "academic performance measured by self-reported grade point average and hours spent studying per week.")
    pa, pb = synthetic_profile(SYN_SOCIAL, "Synthetic Behaviour", "0000-0001"), synthetic_profile(SYN_MEDICAL, "Synthetic Medicine", "0000-0002")
    sa, sb = score_fit(user, pa, 0.10), score_fit(user, pb, 0.10)
    print(f"  fit social={sa['fit']:.1f} (risk {sa['risk']}) medical={sb['fit']:.1f} (risk {sb['risk']})")
    check(sa["fit"] > sb["fit"], "social-media abstract fits the behaviour journal better than the medical one")
    check(sa["nearest"][0][0]["title"].startswith("Facebook use"), "nearest paper is the Facebook/GPA one")
    check(sb["risk"] == "high" and sa["risk"] != "high", "desk-reject risk: high for the medical journal, not for the behaviour one")
    # 4. Profile statistics on synthetic data
    # 403, 300, 250, 512, 620, 380 carry a counted noun; '410 followers' and '54 studies' must NOT count.
    check(pa["sample_n"]["n"] == 6 and pa["sample_n"]["median"] == 391.5,
          f"sample N regex: 6 abstracts with N, median 391.5 (got n={pa['sample_n']['n']}, median={pa['sample_n']['median']})")
    check(pa["methods_share"]["sem_pls_cfa"] == 2 / 12, "methods share: SEM/PLS in 2 of 12 abstracts")
    check(pa["refs"]["median"] == 56.5, f"median refs 56.5 (got {pa['refs']['median']})")
    named = dict(pa["named_theories"])
    check("social cognitive theory" in named and "technology acceptance model" in named, f"named theories found: {list(named)}")
    # 5. Negative control: empty abstract must error
    empty = os.path.join(a.tmp, "empty_abstract.txt")
    os.makedirs(a.tmp, exist_ok=True)
    with open(empty, "w", encoding="utf-8") as f:
        f.write("   \n\n")
    try:
        load_abstract(empty)
        check(False, "empty abstract rejected")
    except SystemExit as e:
        check("empty" in str(e), f"empty abstract rejected: {str(e)[:70]}")
    # 6. compare on a synthetic manuscript
    man = os.path.join(a.tmp, "syn_paper.md")
    with open(man, "w", encoding="utf-8") as f:
        f.write("# Title\n\n## Abstract\n\nA survey of social media use. We used regression.\n\n## Methods\n\n"
                "A questionnaire was completed by 350 students (Smith, 2021; Lee et al., 2024). Regression was used.\n\n"
                "## References\n\nSmith, A. (2021). Paper one. *J*, 1, 1-2.\n\nLee, B. (2024). Paper two. *J*, 2, 3-4.\n")
    mf = manuscript_facts(man)
    check(mf["n_refs"] == 2 and mf["N"] == 350 and mf["methods"]["regression"] == 2 and mf["ref_years"] == [2021, 2024],
          f"manuscript facts: 2 refs, N 350, regression x2, years 2021/2024 (got {mf['n_refs']}, {mf['N']}, {mf['methods']['regression']}, {mf['ref_years']})")
    # 7. Reference data gap: 5 of 12 papers with referenced_works_count = 0 (42%) must be flagged, and the
    #    median must be taken over the 7 papers with refs (55, 58, ..., 73 -> 64), not drag down to 40-ish.
    pg = synthetic_profile(SYN_SOCIAL, "Synthetic Gap", "0000-0003", zero_refs=5)
    check(pg["refs_gap"] and pg["refs_zero"] == 5 and pg["refs_nonzero"]["n"] == 7 and pg["refs_nonzero"]["median"] == 64.0,
          f"zero-reference gap flagged: 5 of 12 at 0, median over papers with refs 64 (got gap={pg['refs_gap']}, "
          f"zero={pg['refs_zero']}, n={pg['refs_nonzero']['n']}, median={pg['refs_nonzero']['median']})")
    md_gap = profile_markdown(pg)
    check("not available in OpenAlex for 5 of 12 papers (data gap)" in md_gap and "median 64" in md_gap,
          "profile table says 'not available in OpenAlex for 5 of 12 papers (data gap)' and gives the labelled median")
    check(not pa["refs_gap"] and "data gap" not in profile_markdown(pa), "no gap flagged when every paper has references")
    check("data gap" in expects(pg) and "data gap" not in expects(pa), "fit's 'what the profile expects' carries the gap label")
    # 8. Negative control: an Arabic-only abstract must stop with exit 1 and name the fix
    try:
        check_language("أثر استخدام وسائل التواصل الاجتماعي على التحصيل الأكاديمي لطلبة الجامعة في الأردن")
        check(False, "Arabic-only abstract rejected")
    except SystemExit as e:
        check(e.code and "English abstract" in str(e), f"Arabic-only abstract rejected with exit 1: {str(e)[:60]}")
    latin, arabic = check_language("أثر استخدام وسائل التواصل الاجتماعي على التحصيل (social media use and academic performance)")
    check(latin == 6 and arabic == 7, f"mixed abstract passes with a note (Latin {latin}, Arabic {arabic})")
    # 9. Negative control: --cached-only with no cached profile must stop with exit 1, no fetch
    empty_dir = os.path.join(a.tmp, "no_cache")
    os.makedirs(empty_dir, exist_ok=True)
    fake = argparse.Namespace(n=100, since=THIS_YEAR - 4, cache_dir=empty_dir, cached_only=True, no_recency=False, issn=["0747-5632"])
    try:
        load_or_build_profile("0747-5632", fake)
        check(False, "--cached-only without a cache rejected")
    except SystemExit as e:
        check("profile_0747-5632_abstracts.json" in str(e) and CALLS["list"] == 0,
              f"--cached-only without a cache rejected, 0 list calls: {str(e)[:60]}")
    check(fit_plan(fake) == (0, ["0747-5632"]), "fit plan under --cached-only is 0 calls and names the missing journal")
    fake.cached_only = False
    check(fit_plan(fake) == (2, ["0747-5632"]), "fit plan without cache is 2 list calls (1 page + recency)")
    print(f"\nRESULT: {'PASS' if not fails else 'FAIL'} ({len(fails)} failed; no network used)")
    sys.exit(1 if fails else 0)


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("profile", help="house profile of one journal",
                       epilog="example: journalfit.py profile --issn 0747-5632 --n 100 --since 2022 --json")
    p.add_argument("--issn", required=True)
    p.add_argument("--n", type=int, default=100, help="papers to fetch, max 200 (default 100)")
    p.add_argument("--since", type=int, default=THIS_YEAR - 4, help=f"first publication year (default {THIS_YEAR - 4})")
    p.add_argument("--out", help="markdown output (default profile_<issn>.md)")
    p.add_argument("--json", action="store_true", help="also write profile_<issn>.json for fit/compare")
    p.add_argument("--has-abstract", action="store_true", help="only papers with an abstract (biases refs/OA stats)")
    p.add_argument("--no-recency", action="store_true", help="skip the reference-recency sample (saves 1 credit)")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("fit", help="rank journals by similarity to your abstract",
                       epilog="example: journalfit.py fit --abstract my_abstract.txt --issn 0747-5632 --issn 0140-6736 --out fit.md")
    p.add_argument("--abstract", required=True, help="text file with your abstract")
    p.add_argument("--issn", action="append", required=True, help="repeat for each journal")
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--since", type=int, default=THIS_YEAR - 4)
    p.add_argument("--threshold", type=float, default=0.10, help="cosine similarity counted as 'related' (default 0.10)")
    p.add_argument("--cache-dir", default=".", help="where profile_<issn>.json files live (default: current folder)")
    p.add_argument("--cached-only", action="store_true",
                   help="never call OpenAlex: use the cached profile_<issn>_abstracts.json / profile_<issn>.json, exit 1 if none")
    p.add_argument("--no-recency", action="store_true")
    p.add_argument("--out")
    p.set_defaults(func=cmd_fit)

    p = sub.add_parser("compare", help="manuscript vs a saved profile",
                       epilog="example: journalfit.py compare --manuscript paper.md --profile profile_0747-5632.json --evidence analysis/output.txt")
    p.add_argument("--manuscript", required=True)
    p.add_argument("--profile", required=True, help="profile_<issn>.json from 'profile --json' or 'fit'")
    p.add_argument("--evidence", default="analysis/output.txt", help="labelled analysis output; its *.n lines give N")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("selftest", help="offline checks on synthetic data", epilog="example: journalfit.py selftest")
    p.add_argument("--tmp", default=os.path.join(os.environ.get("TEMP", "."), "journalfit_selftest"))
    p.set_defaults(func=cmd_selftest)

    a = ap.parse_args()
    if getattr(a, "n", None) is not None:
        a.n = max(1, min(a.n, 200))
    try:
        a.func(a)
    finally:
        say_calls()                   # also on an ERROR exit, so a failed run still shows what it cost


if __name__ == "__main__":
    main()
