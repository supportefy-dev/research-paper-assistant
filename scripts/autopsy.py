#!/usr/bin/env python3
"""autopsy.py - data autopsy: catch bad survey data and inconsistent statistics
before they reach a Results section. numpy + scipy only, no network.

Commands
  careless   flag careless / invalid survey rows (long-string, IRV, speeders,
             Mahalanobis outliers, out-of-range, duplicates) and write a cleaned CSV
  grim       GRIM test (is a reported mean possible for N integer responses?)
             plus GRIMMER for the SD when --sd is given
  harman     Harman's single-factor test (share of variance of the first component)
  statcheck  recompute p from every t / F / r / chi2 / z reported in a text and
             flag inconsistencies (Arabic-Indic digits and APA italics supported).
             statcheck logic: the printed statistic (and a decimal df) is a rounded
             value, so p is recomputed over its whole rounding interval; the reported
             p is consistent when its own rounding interval (or bound) overlaps it
  selftest   builds synthetic data with planted errors and checks every command

Usage
  python -X utf8 autopsy.py careless data.csv --items q1 q2 q3 q4 --scale 1 5 --duration secs --id id \
         --out analysis/autopsy.txt --clean analysis/cleaned.csv
  python -X utf8 autopsy.py grim --mean 3.42 --n 200 --items 1 [--sd 1.07] [--scale 1 5]
  python -X utf8 autopsy.py harman data.csv --items q1 q2 q3 --items2 q4 q5 q6
  python -X utf8 autopsy.py statcheck results.md [--alpha 0.05] [--one-tailed]
  python -X utf8 autopsy.py selftest

Evidence lines follow the shared format (key.path.label = value, last segment = the
statistic label scholar.py numbers reads): autopsy.before.n, autopsy.after.n,
autopsy.longstring.n, harman.pc1.pct ... Thresholds are heuristics from the
careless-responding literature; every flagged row is a candidate for the researcher
to confirm, not an automatic exclusion.
"""

import argparse
import csv
import math
import os
import re
import sys
import tempfile

try:
    import numpy as np
    from scipy import stats
except ImportError:
    sys.exit("numpy and scipy are needed: pip install numpy scipy")

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scholar import table, clean  # noqa: E402  (text helpers only; no network call in this module)

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫،", "01234567890123456789.,")
# Hyphen variants, en/em dashes, minus sign: all become "-" before numbers are parsed.
DASHES = dict.fromkeys([0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015, 0x2212], "-")

_LINES = []


def emit(line=""):
    """Print and remember, so --out gets the same text the user saw."""
    print(line)
    _LINES.append(line)


def flush_out(path):
    if not path:
        return
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(_LINES) + "\n")
    print(f"written: {os.path.abspath(path)}")


def ev(key, value):
    if isinstance(value, float):
        value = f"{value:.6g}" if abs(value) < 1e-4 and value != 0 else f"{value:.6f}".rstrip("0").rstrip(".")
    emit(f"{key} = {value}")


def fmt(x, dec=2):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return f"{x:.{dec}f}"


# ---------------------------------------------------------------- CSV

def load(path):
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
    s = str(v if v is not None else "").strip().translate(ARABIC_DIGITS)
    if s == "":
        return math.nan
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return math.nan


def need_columns(rows, names):
    missing = [n for n in names if n not in rows[0]]
    if missing:
        sys.exit(f"unknown column(s): {', '.join(missing)}. Available: {', '.join(rows[0].keys())}")


# ---------------------------------------------------------------- careless

def longest_run(values):
    """Longest run of identical consecutive answers; a missing answer breaks the run."""
    best = run = 0
    prev = None
    for v in values:
        if math.isnan(v):
            run, prev = 0, None
            continue
        run = run + 1 if prev is not None and v == prev else 1
        prev = v
        best = max(best, run)
    return best


def careless_analyse(rows, items, scale=None, duration=None, id_col=None, longstring=None,
                     irv_min=0.0, min_seconds=None, duration_unit="s", mahal_alpha=0.001,
                     dup_items=False):
    """Return a dict with per-row flags and summary counts. Pure computation, no printing."""
    k, N = len(items), len(rows)
    # Heuristic default: a run over every item on short scales, three quarters of the items on longer
    # ones. Runs of half the items happen by chance on 5-point scales with a real person factor.
    cutoff = longstring if longstring else (k if k <= 8 else max(8, math.ceil(0.75 * k)))
    min_s = min_seconds if min_seconds is not None else 2.0 * k
    unit = {"s": 1.0, "ms": 0.001, "min": 60.0}[duration_unit]

    M = np.full((N, k), np.nan)
    nonnum = [[] for _ in range(N)]
    for i, r in enumerate(rows):
        for j, it in enumerate(items):
            raw = str(r.get(it, "") or "").strip()
            v = num(raw)
            if raw and math.isnan(v):
                nonnum[i].append(it)
            M[i, j] = v

    recs = []
    for i, r in enumerate(rows):
        row = {"row": i + 1, "id": str(r.get(id_col, "")).strip() if id_col else "", "reasons": [],
               "longstring": longest_run(M[i]), "irv": math.nan, "duration": math.nan, "d2": math.nan,
               "d2_p": math.nan}
        avail = M[i][~np.isnan(M[i])]
        if len(avail) >= 2:
            row["irv"] = float(np.std(avail, ddof=1))
        recs.append(row)

    # 1. long-string and 2. IRV
    for i, row in enumerate(recs):
        if row["longstring"] >= cutoff:
            row["reasons"].append(f"longstring={row['longstring']}/{k}")
        if not math.isnan(row["irv"]) and row["irv"] <= irv_min + 1e-12:
            row["reasons"].append(f"irv={row['irv']:.2f}")

    # 3. speeders
    if duration:
        for i, (r, row) in enumerate(zip(rows, recs)):
            d = num(r.get(duration, ""))
            if math.isnan(d):
                row["reasons"].append("duration_missing")
                continue
            d *= unit
            row["duration"] = d
            if d < 0:
                row["reasons"].append(f"duration_negative={d:g}")
            elif d < min_s:
                row["reasons"].append(f"speeder={d:g}s<{min_s:g}s")

    # 4. out of range / not numeric / missing
    for i, row in enumerate(recs):
        if nonnum[i]:
            row["reasons"].append("not_numeric:" + ",".join(nonnum[i]))
        if scale:
            lo, hi = scale
            bad = [items[j] for j in range(k) if not math.isnan(M[i, j]) and not (lo <= M[i, j] <= hi)]
            if bad:
                row["reasons"].append("out_of_range:" + ",".join(f"{b}={M[i, items.index(b)]:g}" for b in bad))
        miss = [items[j] for j in range(k) if math.isnan(M[i, j]) and items[j] not in nonnum[i]]
        if miss:
            row["reasons"].append(f"missing_items={len(miss)}")

    # 5. duplicates: identical on every column except the id (a re-submission), or on the items only
    seen, seen_ids = {}, {}
    for i, (r, row) in enumerate(zip(rows, recs)):
        if dup_items:
            key = tuple(str(r.get(it, "")).strip() for it in items)
        else:
            key = tuple(str(v).strip() for c, v in r.items() if c != id_col)
        if key in seen:
            row["reasons"].append(f"duplicate_of_row={seen[key]}")
        else:
            seen[key] = i + 1
        if id_col:
            rid = row["id"]
            if rid in seen_ids:
                row["reasons"].append(f"duplicate_id_of_row={seen_ids[rid]}")
            else:
                seen_ids[rid] = i + 1

    # 6. Mahalanobis distance on complete rows (p < alpha against chi2 with k df)
    complete = ~np.isnan(M).any(axis=1)
    mahal_note = ""
    if complete.sum() > k + 1:
        X = M[complete]
        mu = X.mean(axis=0)
        cov = np.cov(X, rowvar=False, ddof=1)
        try:
            inv = np.linalg.inv(cov)
            if not np.all(np.isfinite(inv)):
                raise np.linalg.LinAlgError
        except np.linalg.LinAlgError:
            inv = np.linalg.pinv(cov)
            mahal_note = "covariance matrix singular (constant or collinear items): pseudo-inverse used"
        diff = X - mu
        d2 = np.einsum("ij,jk,ik->i", diff, inv, diff)
        p = stats.chi2.sf(d2, k)
        for idx, (dd, pp) in zip(np.where(complete)[0], zip(d2, p)):
            recs[idx]["d2"], recs[idx]["d2_p"] = float(dd), float(pp)
            if pp < mahal_alpha:
                recs[idx]["reasons"].append(f"mahalanobis_p={pp:.2g}")
    else:
        mahal_note = f"skipped: needs more than {k + 1} complete rows, found {int(complete.sum())}"

    # recommendation: on a short scale (< 10 items) an all-identical row is weak evidence of
    # straight-lining, so it is REVIEW unless the user set --longstring deliberately.
    short_scale = k < 10 and not longstring
    drop_kinds = (("speeder", "duration_negative", "not_numeric", "out_of_range", "duplicate_of_row", "duplicate_id")
                  + (() if short_scale else ("longstring", "irv")))
    counts = {"longstring": 0, "irv": 0, "speeder": 0, "mahalanobis": 0, "range": 0, "duplicate": 0,
              "missing": 0}
    for row in recs:
        rs = row["reasons"]
        if any(x.startswith(drop_kinds) for x in rs):
            row["rec"] = "DROP"
        elif rs:
            row["rec"] = "REVIEW"
        else:
            row["rec"] = "KEEP"
        joined = " ".join(rs)
        counts["longstring"] += "longstring=" in joined
        counts["irv"] += "irv=" in joined
        counts["speeder"] += "speeder=" in joined or "duration_negative" in joined
        counts["mahalanobis"] += "mahalanobis_p=" in joined
        counts["range"] += "out_of_range" in joined or "not_numeric" in joined
        counts["duplicate"] += "duplicate_of_row" in joined or "duplicate_id" in joined
        counts["missing"] += "missing_items" in joined or "duration_missing" in joined
    return {"recs": recs, "k": k, "n": N, "cutoff": cutoff, "min_seconds": min_s, "irv_min": irv_min,
            "mahal_alpha": mahal_alpha, "mahal_note": mahal_note, "counts": counts, "short_scale": short_scale,
            "irv_all": np.array([r["irv"] for r in recs]), "longstring_all": np.array([r["longstring"] for r in recs]),
            "duration_all": np.array([r["duration"] for r in recs])}


def careless(a):
    rows = load(a.csv)
    need_columns(rows, a.items + ([a.duration] if a.duration else []) + ([a.id] if a.id else []))
    res = careless_analyse(rows, a.items, scale=a.scale, duration=a.duration, id_col=a.id,
                           longstring=a.longstring, irv_min=a.irv_min, min_seconds=a.min_seconds,
                           duration_unit=a.duration_unit, mahal_alpha=a.mahal_alpha, dup_items=a.dup_items)
    recs, c = res["recs"], res["counts"]
    n_drop = sum(r["rec"] == "DROP" for r in recs)
    n_review = sum(r["rec"] == "REVIEW" for r in recs)
    n_flag = n_drop + n_review
    n_after = res["n"] - n_drop - (n_review if a.drop_review else 0)

    emit(f"# careless {os.path.basename(a.csv)} | rows {res['n']} | items {res['k']} | flagged {n_flag} "
         f"(drop {n_drop}, review {n_review}) | after cleaning {n_after}")
    emit(f"# thresholds: longstring >= {res['cutoff']} of {res['k']} items; IRV <= {res['irv_min']:g}; "
         + (f"duration < {res['min_seconds']:g} s; " if a.duration else "duration: not checked (no --duration); ")
         + f"Mahalanobis p < {res['mahal_alpha']:g}; "
         + (f"range {a.scale[0]:g}-{a.scale[1]:g}; " if a.scale else "range: not checked (no --scale); ")
         + ("duplicates on item columns only" if a.dup_items else "duplicates on all non-id columns"))
    if res["short_scale"]:
        emit(f"# short scale ({res['k']} items): identical answers on every item are weak evidence of straight-lining, "
             "so long-string / zero-IRV rows are REVIEW, not DROP. Set --longstring to make them DROP.")
    if res["mahal_note"]:
        emit(f"# Mahalanobis: {res['mahal_note']}")
    ls, irv, dur = res["longstring_all"], res["irv_all"], res["duration_all"]
    irv_ok = irv[~np.isnan(irv)]
    dist = [f"longstring median {np.median(ls):g}, 95th pct {np.percentile(ls, 95):g}, max {ls.max():g}"]
    if len(irv_ok):
        dist.append(f"IRV 5th pct {np.percentile(irv_ok, 5):.2f}, median {np.median(irv_ok):.2f}")
    if a.duration and not np.isnan(dur).all():
        d_ok = dur[~np.isnan(dur)]
        dist.append(f"duration median {np.median(d_ok):g} s, min {d_ok.min():g} s")
    emit("# distribution: " + "; ".join(dist) + " (raise --irv-min or --longstring if the sample calls for it)")
    emit()
    flagged = [r for r in recs if r["reasons"]]
    if flagged:
        emit(table([[str(r["row"]), r["id"], str(r["longstring"]), fmt(r["irv"]),
                     fmt(r["duration"], 0) if a.duration else "-", fmt(r["d2"], 1), "; ".join(r["reasons"]), r["rec"]]
                    for r in flagged],
                   ["row", "id", "longstring", "IRV", "duration_s", "D2", "reasons", "recommendation"]))
    else:
        emit("no row flagged")
    emit()
    emit(f"recommendation: keep {res['n'] - n_flag}, review {n_review}, drop {n_drop} "
         f"(review rows are {'dropped too (--drop-review)' if a.drop_review else 'kept in the cleaned file; pass --drop-review to drop them'})")
    emit("# Each flag is a candidate: a straight-liner on a 4-item scale or a Mahalanobis outlier can be an honest "
         "respondent. Run this on RAW responses (before reverse coding). Report the rule and the counts in Methods.")
    ev("autopsy.before.n", res["n"])
    ev("autopsy.flagged.n", n_flag)
    ev("autopsy.drop.n", n_drop)
    ev("autopsy.review.n", n_review)
    ev("autopsy.after.n", n_after)
    ev("autopsy.excluded.pct", 100.0 * (res["n"] - n_after) / res["n"])
    ev("autopsy.longstring.cutoff", res["cutoff"])
    ev("autopsy.longstring.n", c["longstring"])
    ev("autopsy.irv.n", c["irv"])
    ev("autopsy.speeder.min_seconds", res["min_seconds"] if a.duration else "not_checked")
    ev("autopsy.speeder.n", c["speeder"] if a.duration else "not_checked")
    ev("autopsy.mahalanobis.alpha", res["mahal_alpha"])
    ev("autopsy.mahalanobis.n", c["mahalanobis"])
    ev("autopsy.range.n", c["range"] if a.scale else "not_checked")
    ev("autopsy.duplicate.n", c["duplicate"])
    ev("autopsy.missing.n", c["missing"])
    emit(f"# APA: Of {res['n']} responses, {res['n'] - n_after} were excluded after data screening "
         f"(long-string >= {res['cutoff']}: {c['longstring']}; zero IRV: {c['irv']}; "
         + (f"completion under {res['min_seconds']:g} s: {c['speeder']}; " if a.duration else "")
         + (f"out-of-range values: {c['range']}; " if a.scale else "")
         + f"duplicates: {c['duplicate']}; multivariate outliers at p < {res['mahal_alpha']:g}: {c['mahalanobis']}), "
         f"leaving N = {n_after}."
         + ("" if a.duration else " Response time was not screened (no completion-time variable was available)."))
    if a.clean:
        keep_rows = [r for r, rec in zip(rows, recs) if rec["rec"] == "KEEP" or (rec["rec"] == "REVIEW" and not a.drop_review)]
        d = os.path.dirname(os.path.abspath(a.clean))
        os.makedirs(d, exist_ok=True)
        with open(a.clean, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(keep_rows)
        emit(f"cleaned CSV: {os.path.abspath(a.clean)} ({len(keep_rows)} rows)")
    flush_out(a.out)
    return res


# ---------------------------------------------------------------- GRIM / GRIMMER

def decimals_of(s):
    s = str(s).strip().translate(ARABIC_DIGITS)
    return len(s.split(".")[1]) if "." in s else 0


def grim_test(mean, n, items=1, decimals=None):
    """Possible means are S / (n * items) for integer S. Consistent if one of them rounds
    to the reported mean under either rounding convention (|possible - reported| <= half unit)."""
    d = decimals_of(mean) if decimals is None else decimals
    m = float(str(mean).translate(ARABIC_DIGITS))
    g = n * items                                   # denominator: total number of item responses
    half = 0.5 * 10 ** (-d) + 1e-9
    lo, hi = math.floor((m - half) * g), math.ceil((m + half) * g)
    sums = sorted((S for S in range(max(lo, 0), hi + 1) if abs(S / g - m) <= half), key=lambda S: abs(S / g - m))
    base = math.floor(m * g)
    near = sorted({S / g for S in (base - 1, base, base + 1, base + 2) if S >= 0})
    return {"mean": m, "n": n, "items": items, "decimals": d, "granularity": 1 / g, "sums": sums,
            "consistent": bool(sums), "power": g < 10 ** d, "nearest": near}


def grimmer_test(mean, sd, n, items=1, decimals=None, sd_decimals=None, ddof=1, scale=None):
    """GRIMMER (Anaya 2016; Allard 2018 rounding version): for every sum S that passes GRIM,
    the sum of squared (item-summed) integers must be an integer with the parity of S whose
    implied SD rounds to the reported SD. --scale adds the Bhatia-Davis bound on the SD."""
    g = grim_test(mean, n, items, decimals)
    sd_d = decimals_of(sd) if sd_decimals is None else sd_decimals
    s = float(str(sd).translate(ARABIC_DIGITS))
    out = {"grim": g, "sd": s, "sd_decimals": sd_d, "consistent": None, "reason": "", "power": True}
    if not g["consistent"]:
        out["consistent"], out["reason"] = False, "mean already fails GRIM"
        return out
    if n < 2:
        out["consistent"], out["reason"] = None, "needs n >= 2"
        return out
    half = 0.5 * 10 ** (-sd_d)
    k = items
    sd_lo, sd_hi = max(0.0, s - half), s + half
    dof = n - ddof
    bhatia = None
    if scale:
        # Bhatia-Davis: var <= (max - mean)(mean - min). Evaluate at every exact mean the GRIM
        # step allows, not at the rounded reported mean, or honest data half a unit away fails.
        lo_v, hi_v = scale
        bhatia = max(math.sqrt(max(0.0, (hi_v - S / (n * k)) * (S / (n * k) - lo_v)) * n / dof) for S in g["sums"])
        if sd_lo > bhatia + 1e-9:
            out["consistent"] = False
            out["reason"] = f"SD exceeds the maximum possible on a {lo_v:g}-{hi_v:g} scale for this mean ({bhatia:.3f})"
            return out
    found, examined = None, 0
    for S in g["sums"]:                              # S = sum over persons of the item-sum integers y_i
        mean_y = S / n
        L = dof * (k * sd_lo) ** 2 + n * mean_y ** 2   # sum of y_i^2 (integers) bounds
        U = dof * (k * sd_hi) ** 2 + n * mean_y ** 2
        a_, b_ = math.ceil(L - 1e-9), math.floor(U + 1e-9)
        if b_ - a_ > 200000:
            out["power"] = False
            out["consistent"], out["reason"] = True, "too many possible sums of squares: GRIMMER has no power here"
            return out
        for SS in range(a_, b_ + 1):
            examined += 1
            if SS % 2 != S % 2:                      # y^2 and y share parity, so do their sums
                continue
            var = (SS - n * mean_y ** 2) / dof
            if var < 0:
                continue
            implied = math.sqrt(var) / k
            if abs(round(implied, sd_d) - round(s, sd_d)) < 1e-9 or abs(implied - s) <= half + 1e-9:
                found = (S, SS, implied)
                break
        if found:
            break
    if found:
        out["consistent"] = True
        out["reason"] = f"sum {found[0]}, sum of squares {found[1]} gives SD {found[2]:.4f}"
    else:
        out["consistent"] = False
        out["reason"] = (f"no integer sum of squares with the right parity yields an SD rounding to {s} "
                         f"(examined {examined} candidates over {len(g['sums'])} possible sums)")
    out["bhatia"] = bhatia
    return out


def grim(a):
    g = grim_test(a.mean, a.n, a.items, a.decimals)
    emit(f"# grim mean {a.mean} | N {a.n} | items {a.items} | decimals {g['decimals']} | "
         f"granularity 1/{a.n * a.items} = {g['granularity']:.6g}")
    if not g["power"]:
        emit(f"GRIM has no power here: with N x items = {a.n * a.items} >= 10^{g['decimals']} every mean with "
             f"{g['decimals']} decimals is possible. Report more decimals or use GRIMMER on the SD.")
    emit("possible means near the reported one: " + ", ".join(f"{x:.{g['decimals'] + 2}f}" for x in g["nearest"]))
    if g["consistent"]:
        emit(f"GRIM: CONSISTENT (sum {g['sums'][0]} of {a.n * a.items} integer responses gives "
             f"{g['sums'][0] / (a.n * a.items):.{g['decimals'] + 2}f})")
    else:
        emit(f"GRIM: INCONSISTENT - no integer sum over {a.n * a.items} responses rounds to {a.mean}. "
             "Check N, the number of items, whether responses are integers, and the rounding.")
    ev("grim.mean.consistent", int(g["consistent"]))
    ev("grim.power", int(g["power"]))
    verdict = g["consistent"]
    if a.sd is not None:
        r = grimmer_test(a.mean, a.sd, a.n, a.items, a.decimals, a.sd_decimals, a.ddof, a.scale)
        tag = {True: "CONSISTENT", False: "INCONSISTENT", None: "NOT CHECKED"}[r["consistent"]]
        emit(f"GRIMMER (SD {a.sd}, ddof {a.ddof}): {tag} - {r['reason']}")
        if r.get("bhatia") is not None:
            emit(f"# maximum SD on this scale for this mean (Bhatia-Davis): {r['bhatia']:.3f}")
        ev("grimmer.sd.consistent", -1 if r["consistent"] is None else int(r["consistent"]))
        if r["consistent"] is False:
            verdict = False
    else:
        emit("# SD not given: GRIMMER not run (add --sd to test the standard deviation).")
    emit("# GRIM assumes integer responses (Likert items) averaged over --items items; "
         "it does not apply to continuous measures.")
    emit(f"RESULT: {'PASS' if verdict else 'FAIL'} ({'reported values are possible' if verdict else 'impossible for integer data'})")
    flush_out(a.out)
    return verdict


# ---------------------------------------------------------------- Harman

def harman_analyse(rows, items):
    X = np.array([[num(r.get(it, "")) for it in items] for r in rows], dtype=float)
    keep = ~np.isnan(X).any(axis=1)
    X = X[keep]
    sd = X.std(axis=0, ddof=1)
    const = [it for it, s in zip(items, sd) if s == 0 or math.isnan(s)]
    use = [j for j, it in enumerate(items) if it not in const]
    X = X[:, use]
    k = X.shape[1]
    if k < 2 or X.shape[0] < k + 1:
        sys.exit(f"need at least 2 non-constant items and more rows than items (rows {X.shape[0]}, items {k})")
    R = np.corrcoef(X, rowvar=False)
    eig = np.sort(np.linalg.eigvalsh(R))[::-1]
    return {"n": int(X.shape[0]), "dropped": int((~keep).sum()), "k": k, "const": const, "eig": eig,
            "pc1_pct": 100.0 * eig[0] / k, "pc2_pct": 100.0 * eig[1] / k, "gt1": int((eig > 1).sum())}


def harman(a):
    items = []
    groups = [g for g in (a.items or []) if g]
    for grp in groups:
        items += grp
    items += a.items2 or []
    items = list(dict.fromkeys(items))
    if len(items) < 2:
        sys.exit("give at least two items (--items q1 q2 ... [--items2 ...])")
    n_constructs = len(groups) + (1 if a.items2 else 0)
    rows = load(a.csv)
    need_columns(rows, items)
    h = harman_analyse(rows, items)
    emit(f"# harman {os.path.basename(a.csv)} | rows {h['n']} (listwise, {h['dropped']} dropped) | items {h['k']}"
         f" | constructs {n_constructs}"
         + (f" | constant items dropped: {', '.join(h['const'])}" if h["const"] else ""))
    emit(f"unrotated principal components of the correlation matrix: first component explains "
         f"{h['pc1_pct']:.1f}% of the total variance (eigenvalue {h['eig'][0]:.3f}); "
         f"{h['gt1']} component(s) with eigenvalue > 1")
    emit("eigenvalues: " + ", ".join(f"{e:.3f}" for e in h["eig"][:10]) + (" ..." if h["k"] > 10 else ""))
    if n_constructs < 2:
        emit("# WARNING: only one construct was given (--items without --items2). Harman's test pools the items of "
             "ALL the study's constructs and asks whether one factor explains most of their shared variance; on a "
             "single scale the first component is expected to dominate, so the number above measures the scale's "
             "unidimensionality, not common method bias. No verdict is given: rerun with --items2 (or a second "
             "--items group) listing the other construct(s).")
        emit("verdict: NOT GIVEN (single construct; Harman's test needs the items of at least two constructs)")
    elif h["pc1_pct"] >= 50:
        emit(f"verdict: first factor explains {h['pc1_pct']:.1f}% >= 50%: common method bias SUSPECTED "
             "(Harman's criterion)")
    elif h["gt1"] == 1:
        emit(f"verdict: only one component with eigenvalue > 1 (first factor {h['pc1_pct']:.1f}%): "
             "a single general factor dominates; treat as a warning")
    else:
        emit(f"verdict: first factor {h['pc1_pct']:.1f}% < 50% and {h['gt1']} components > 1: "
             "no single-factor dominance by Harman's criterion")
    emit("# WARNING: Harman's single-factor test is a weak, insensitive test (Podsakoff et al., 2003): "
         "passing it does not rule out common method variance. Prefer a marker variable, an unmeasured latent "
         "method factor in CFA, or procedural remedies, and say in Limitations that the test is only indicative. "
         "This implementation uses PCA; an unrotated EFA gives slightly smaller shares.")
    ev("harman.n", h["n"])
    ev("harman.items.n", h["k"])
    ev("harman.pc1.eigen", float(h["eig"][0]))
    ev("harman.pc1.pct", float(h["pc1_pct"]))
    ev("harman.pc2.pct", float(h["pc2_pct"]))
    ev("harman.eigen_gt1.n", h["gt1"])
    ev("harman.constructs.n", n_constructs)
    if n_constructs < 2:
        emit(f"# APA: not written. The first unrotated component of the {h['k']} items of one scale accounted for "
             f"{h['pc1_pct']:.1f}% of their variance (n = {h['n']}), which describes that scale's dimensionality "
             "and must not be reported as Harman's single-factor test of common method bias.")
    else:
        emit(f"# APA: Harman's single-factor test on the {h['k']} items of {n_constructs} constructs: the first "
             f"unrotated component accounted for {h['pc1_pct']:.1f}% of the variance "
             f"({'above' if h['pc1_pct'] >= 50 else 'below'} the 50% threshold), n = {h['n']}.")
    flush_out(a.out)
    return h


# ---------------------------------------------------------------- statcheck

TEST_RE = re.compile(
    r"(?<![A-Za-z؀-ۿ])"
    r"(?P<test>chi2|t|F|r|z|Z|ت|ف|ر|ز)"
    r"\s*(?:\(\s*(?P<df1>\d+(?:\.\d+)?)\s*(?:,\s*(?P<df2>\d+(?:\.\d+)?))?\s*(?:,\s*[Nn]\s*=\s*\d+)?\s*\))?"
    r"\s*(?P<op1>=|<|>)\s*(?P<stat>-?(?:\d+\.\d+|\.\d+|\d+))"
    r"\s*[,;،؛]?\s*(?:and\s+|with\s+|at\s+|عند\s+)?(?:مستوى\s+)?\(?\s*(?:p|ب|الدلالة|sig\.?)\s*"
    r"(?P<op2>=|<|>|≤|≥)\s*(?P<p>(?:\d+\.\d+|\.\d+|\d+))",
    re.UNICODE)
AR_TEST = {"ت": "t", "ف": "F", "ر": "r", "ز": "z", "Z": "z"}


def normalize_stat_line(line):
    s = line.translate(ARABIC_DIGITS).translate(DASHES)
    s = re.sub(r"<\s*/?\s*(i|em|b|strong|sub|sup)\s*>", "", s, flags=re.I)
    s = re.sub(r"(?<![\w*])[*_]{1,3}(?=[^\s*_])|(?<=[^\s*_])[*_]{1,3}(?![\w*])", "", s)   # *t* -> t, *p* -> p
    s = re.sub(r"(χ|Χ|X|x|chi|كا)\s*(?:2|²|\^2|-square[d]?|\s*square[d]?)", "chi2", s)
    s = s.replace("≤", "<").replace("≥", ">")
    return s


def computed_p(test, stat, df1, df2, one_tailed=False):
    if test == "t":
        p = 2 * stats.t.sf(abs(stat), df1)
    elif test == "F":
        p = stats.f.sf(stat, df1, df2)
    elif test == "r":
        if abs(stat) >= 1:
            return None
        t = stat * math.sqrt(df1 / (1 - stat ** 2))
        p = 2 * stats.t.sf(abs(t), df1)
    elif test == "chi2":
        p = stats.chi2.sf(stat, df1)
    elif test == "z":
        p = 2 * stats.norm.sf(abs(stat))
    else:
        return None
    if one_tailed and test in ("t", "r", "z"):
        p /= 2
    return float(p)


def rounding_interval(x, dec, lo_floor=None):
    """A printed value with dec decimals stands for any true value within half a unit of the last decimal."""
    h = 0.5 * 10 ** (-dec)
    lo, hi = x - h, x + h
    if lo_floor is not None:
        lo = max(lo, lo_floor)
    return lo, hi


def p_range(test, stat, stat_dec, df1, df2, df1_dec=0, df2_dec=0, one_tailed=False):
    """statcheck logic (Nuijten et al., 2016): the reported statistic is rounded, so recompute p at both ends
    of its rounding interval (and of a decimal df, e.g. Welch or Greenhouse-Geisser) and return (p_lo, p_hi).
    p is monotone in |stat| for every supported test, so the ends of the interval bound the range."""
    s_lo, s_hi = rounding_interval(stat, stat_dec)
    if test in ("t", "r", "z"):
        if s_lo <= 0 <= s_hi:                           # interval straddles zero: |stat| runs from 0
            ends = [0.0, max(abs(s_lo), abs(s_hi))]
        else:
            ends = sorted([abs(s_lo), abs(s_hi)])
        if test == "r":
            if ends[0] >= 1:
                return None
            ends[1] = min(ends[1], 1 - 1e-9)             # r = 1.00 printed: the interval touches 1 (p = 0)
    else:
        ends = [max(0.0, s_lo), s_hi]

    def df_ends(df, dec):
        if df is None:
            return [None]
        if dec == 0:
            return [df]
        lo, hi = rounding_interval(df, dec, lo_floor=1e-9)
        return [lo, hi]

    ps = []
    for s in ends:
        for d1 in df_ends(df1, df1_dec):
            for d2 in df_ends(df2, df2_dec):
                p = computed_p(test, s, d1, d2, one_tailed)
                if p is None:
                    return None
                ps.append(p)
    return min(ps), max(ps)


def p_consistent(p_lo, p_hi, op, rep, dec):
    """The reported p is itself rounded (op '=') or a bound ('<', '>'): consistent when its interval
    overlaps the recomputed range."""
    if op == "=":
        r_lo, r_hi = rounding_interval(rep, dec, lo_floor=0.0)
        return p_lo <= r_hi + 1e-12 and p_hi >= r_lo - 1e-12
    if op == "<":
        return p_lo < rep
    return p_hi > rep


def fmt_range(p_lo, p_hi):
    a_, b_ = f"{p_lo:.3g}", f"{p_hi:.3g}"
    return a_ if a_ == b_ else f"{a_} to {b_}"


def statcheck_text(text, alpha=0.05, one_tailed=False):
    found = []
    auto_one = bool(re.search(r"one[- ]tailed|one[- ]sided|أحادي الذيل|أحادي الطرف", text, re.I))
    for ln, raw in enumerate(text.splitlines(), 1):
        line = normalize_stat_line(raw)
        for m in TEST_RE.finditer(line):
            test = AR_TEST.get(m.group("test"), m.group("test"))
            stat = float(m.group("stat"))
            stat_dec = decimals_of(m.group("stat"))
            df1 = float(m.group("df1")) if m.group("df1") else None
            df2 = float(m.group("df2")) if m.group("df2") else None
            df1_dec = decimals_of(m.group("df1")) if m.group("df1") else 0
            df2_dec = decimals_of(m.group("df2")) if m.group("df2") else 0
            op2 = m.group("op2").replace("≤", "<").replace("≥", ">")
            rep = float(m.group("p"))
            dec = decimals_of(m.group("p"))
            item = {"line": ln, "test": test, "stat": stat, "df1": df1, "df2": df2, "op": op2, "p_reported": rep,
                    "reported": clean(m.group(0)), "p_computed": None, "p_lo": None, "p_hi": None,
                    "verdict": "unchecked", "note": ""}
            if m.group("op1") != "=":
                item["note"] = "statistic given as an inequality: not checked"
                found.append(item)
                continue
            if test in ("t", "r", "chi2") and df1 is None or test == "F" and (df1 is None or df2 is None):
                item["note"] = "degrees of freedom missing: not checked"
                found.append(item)
                continue
            comp = computed_p(test, stat, df1, df2, one_tailed)
            rng = p_range(test, stat, stat_dec, df1, df2, df1_dec, df2_dec, one_tailed)
            if comp is None or rng is None:
                item["note"] = "cannot compute (|r| >= 1 or unknown test)"
                found.append(item)
                continue
            p_lo, p_hi = rng
            item["p_computed"], item["p_lo"], item["p_hi"] = comp, p_lo, p_hi
            if op2 == "=" and rep == 0:
                item["verdict"] = "inconsistent" if p_lo >= 0.5 * 10 ** (-dec) else "style"
                item["note"] = "p = 0 is never exact: write p < .001"
                found.append(item)
                continue
            if p_consistent(p_lo, p_hi, op2, rep, dec):
                item["verdict"] = "consistent"
            else:
                alt = p_range(test, stat, stat_dec, df1, df2, df1_dec, df2_dec, not one_tailed) \
                    if test in ("t", "r", "z") else None
                if alt is not None and p_consistent(alt[0], alt[1], op2, rep, dec):
                    item["verdict"] = "consistent" if auto_one and not one_tailed else "inconsistent"
                    item["note"] = ("matches a one-tailed p" if not one_tailed else "matches a two-tailed p") + \
                                   (" (text mentions one-tailed)" if auto_one else ": say which tail was used")
                else:
                    item["verdict"] = "inconsistent"
                rep_sig = (op2 == "<" and rep <= alpha) or (op2 == "=" and rep < alpha)
                rep_nonsig = (op2 == ">" and rep >= alpha) or (op2 == "=" and rep >= alpha)
                all_sig, all_nonsig = p_hi < alpha, p_lo >= alpha     # the whole recomputed range on one side
                if item["verdict"] == "inconsistent" and ((rep_sig and all_nonsig) or (rep_nonsig and all_sig)):
                    item["verdict"] = "decision error"
                    item["note"] = (item["note"] + "; " if item["note"] else "") + \
                                   f"reported {'significant' if rep_sig else 'non-significant'} at alpha {alpha:g}, " \
                                   f"recomputed p {fmt_range(p_lo, p_hi)} says the opposite (gross error)"
            found.append(item)
    return found


def statcheck(a):
    with open(a.file, encoding="utf-8", errors="replace") as f:
        text = f.read()
    items = statcheck_text(text, a.alpha, a.one_tailed)
    n_inc = sum(i["verdict"] == "inconsistent" for i in items)
    n_dec = sum(i["verdict"] == "decision error" for i in items)
    n_ok = sum(i["verdict"] == "consistent" for i in items)
    n_un = sum(i["verdict"] in ("unchecked", "style") for i in items)
    emit(f"# statcheck {os.path.basename(a.file)} | tests found {len(items)} | consistent {n_ok} | "
         f"inconsistent {n_inc} | decision errors {n_dec} | unchecked {n_un} | "
         f"{'one' if a.one_tailed else 'two'}-tailed, alpha {a.alpha:g}")
    if items:
        rows = []
        for i in items:
            df = "" if i["df1"] is None else (f"{i['df1']:g}" + (f", {i['df2']:g}" if i["df2"] is not None else ""))
            rows.append([str(i["line"]), i["reported"], f"{i['test']}({df})" if df else i["test"],
                         "-" if i["p_lo"] is None else fmt_range(i["p_lo"], i["p_hi"]), i["verdict"], i["note"]])
        emit(table(rows, ["line", "as reported", "test", "recomputed p range", "verdict", "note"]))
    else:
        emit("no test statistics in the form t(df) = x, p = y / F(df1, df2) = x / r(df) = x / chi2(df) = x / z = x found")
    emit("# Not checked: tests reported without df, inequalities on the statistic, p = ns, corrected p values "
         "(Bonferroni, FDR), robust or exact tests whose p does not follow the standard distribution.")
    emit("# statcheck logic (Nuijten et al., 2016): the printed statistic (and a decimal df) is a rounded value, so p "
         "is recomputed with scipy over its whole rounding interval; a reported p = x is consistent when its own "
         "rounding interval overlaps that range, p < x or p > x when the range reaches past the bound.")
    emit(f"# 'decision error' = reported significant at alpha {a.alpha:g} while the whole recomputed range is not "
         "(or the reverse).")
    fail = n_inc + n_dec > 0
    emit(f"RESULT: {'FAIL' if fail else 'PASS'} ({n_inc + n_dec} inconsistent of {len(items)} tests"
         + (f", {n_un} not checked" if n_un else "") + ")")
    flush_out(a.out)
    return not fail


# ---------------------------------------------------------------- selftest

def synth_rows(seed=7, n_honest=60, k=12):
    """Honest Likert respondents (1-5, a person factor so items correlate) plus planted problems."""
    rng = np.random.RandomState(seed)
    items = [f"q{i + 1}" for i in range(k)]
    rows = []

    def person(i, vals, dur):
        r = {"id": f"P{i:03d}"}
        r.update({it: str(int(v)) for it, v in zip(items, vals)})
        r["secs"] = f"{dur:.0f}"
        return r

    for i in range(1, n_honest + 1):
        f = rng.normal(0, 1)
        vals = np.clip(np.round(3 + 0.7 * f + rng.normal(0, 0.8, k)), 1, 5)
        rows.append(person(i, vals, rng.uniform(45, 150)))
    plant = {}
    rows.append(person(901, [4] * k, 70)); plant["straight_4"] = len(rows)
    rows.append(person(902, [1] * k, 60)); plant["straight_1"] = len(rows)
    sp = np.clip(np.round(3 + rng.normal(0, 0.9, k)), 1, 5)
    rows.append(person(903, sp, 9)); plant["speeder"] = len(rows)
    oor = np.clip(np.round(3 + rng.normal(0, 0.9, k)), 1, 5); oor[4] = 7
    rows.append(person(904, oor, 80)); plant["out_of_range"] = len(rows)
    dup = dict(rows[4]); dup["id"] = "P905"
    rows.append(dup); plant["duplicate_of_5"] = len(rows)
    alt = [1, 5] * (k // 2)
    rows.append(person(906, alt, 90)); plant["alternating_(mahalanobis_candidate)"] = len(rows)
    return rows, items, plant


def selftest(a):
    d = a.dir or tempfile.mkdtemp(prefix="autopsy-selftest-")
    os.makedirs(d, exist_ok=True)
    fails = []

    def check(cond, msg):
        emit(("ok   " if cond else "FAIL ") + msg)
        if not cond:
            fails.append(msg)

    rows, items, plant = synth_rows()
    path = os.path.join(d, "selftest_data.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    emit(f"# selftest data: {path} ({len(rows)} rows, {len(items)} items, planted rows {plant})")
    emit("## careless")
    res = careless_analyse(load(path), items, scale=(1, 5), duration="secs", id_col="id")
    by = {r["row"]: r for r in res["recs"]}
    rs = lambda n: " ".join(by[n]["reasons"])
    check("longstring=12/12" in rs(plant["straight_4"]) and by[plant["straight_4"]]["rec"] == "DROP", "straight-liner (all 4) flagged longstring + DROP")
    check("irv=0.00" in rs(plant["straight_1"]) and by[plant["straight_1"]]["rec"] == "DROP", "straight-liner (all 1) flagged IRV 0 + DROP")
    check("speeder=" in rs(plant["speeder"]), "speeder (9 s for 12 items) flagged")
    check("out_of_range:q5=7" in rs(plant["out_of_range"]), "out-of-range value (q5 = 7 on 1-5) flagged")
    check("duplicate_of_row=5" in rs(plant["duplicate_of_5"]), "duplicate of row 5 flagged on the copy, not the original")
    check(by[5]["rec"] == "KEEP", "original of the duplicate (row 5) kept")
    honest = [by[i] for i in range(1, 61)]
    n_hd = sum(r["rec"] == "DROP" for r in honest)
    check(n_hd == 0, f"no honest row recommended DROP ({n_hd} of 60)")
    n_hr = sum(r["rec"] == "REVIEW" for r in honest)
    check(n_hr <= 2, f"honest rows under REVIEW (Mahalanobis p < .001) at most 2 ({n_hr} of 60)")
    emit(f"     alternating 1/5 row: D2 = {by[plant['alternating_(mahalanobis_candidate)']]['d2']:.1f}, "
         f"reasons: {rs(plant['alternating_(mahalanobis_candidate)']) or 'none'} (informational)")
    emit("## grim")
    check(grim_test("3.42", 200)["consistent"], "GRIM: mean 3.42, N 200 is possible (684/200)")
    check(not grim_test("3.42", 20)["consistent"], "GRIM: mean 3.42, N 20 is impossible (step 0.05)")
    check(grim_test("3.42", 20, items=5)["consistent"], "GRIM: mean 3.42, N 20 over 5 items is possible (342/100)")
    check(not grim_test("3.42", 1000)["power"], "GRIM: N 1000 with 2 decimals has no power (reported)")
    emit("## grimmer")
    x = np.array([1, 2, 3, 4, 5])
    r1 = grimmer_test("3.00", f"{x.std(ddof=1):.2f}", 5)
    check(r1["consistent"] is True, f"GRIMMER: data 1..5, mean 3.00, SD 1.58 consistent ({r1['reason']})")
    r2 = grimmer_test("3.00", "0.10", 5)
    check(r2["consistent"] is False, f"GRIMMER: mean 3.00, SD 0.10, N 5 impossible ({r2['reason']})")
    r3 = grimmer_test("4.80", "1.90", 30, scale=(1, 5))
    check(r3["consistent"] is False, f"GRIMMER: SD 1.90 at mean 4.80 on a 1-5 scale impossible ({r3['reason']})")
    rng = np.random.RandomState(3)
    y = rng.randint(1, 6, size=(40, 3)).mean(axis=1)
    r4 = grimmer_test(f"{y.mean():.2f}", f"{y.std(ddof=1):.2f}", 40, items=3)
    check(r4["consistent"] is True, f"GRIMMER: real 40 x 3-item averages, mean {y.mean():.2f}, SD {y.std(ddof=1):.2f} consistent")
    emit("## statcheck")
    text = ("Sleep predicted GPA, *t*(194) = 4.57, *p* < .001. The interaction was not supported, "
            "F(2, 196) = 2.10, p < .05. Gender differed, χ²(1, N = 196) = 4.20, p = .04. "
            "z = 1.20, p = .03. بلغ معامل الارتباط ر(١٩٤) = ٠٫٣١، ب < ٠٫٠٠١.")
    sc = statcheck_text(text)
    check(len(sc) == 5, f"statcheck found 5 tests ({len(sc)})")
    check(sc[0]["verdict"] == "consistent", f"t(194) = 4.57, p < .001 consistent ({sc[0]['p_computed']:.2g})")
    check(sc[1]["verdict"] == "decision error", f"F(2, 196) = 2.10, p < .05 is a decision error (computed {sc[1]['p_computed']:.3f})")
    check(sc[2]["verdict"] == "consistent", f"chi2(1) = 4.20, p = .04 consistent (computed {sc[2]['p_computed']:.3f})")
    check(sc[3]["verdict"] == "decision error", f"z = 1.20, p = .03 is a decision error (computed {sc[3]['p_computed']:.3f})")
    check(sc[4]["verdict"] == "consistent" and sc[4]["test"] == "r", "Arabic-Indic r(194) = .31, p < .001 parsed and consistent")
    apa = ("Correct APA lines: t(196) = 4.40, p < .001; r(197) = .31, p < .001; F(2, 196) = 15.15, p < .001; "
           "t(20) = 2.09, p = .049; t(23.5) = 2.07, p = .05. Wrong line: t(196) = 1.40, p < .001.")
    sa = statcheck_text(apa)
    check(len(sa) == 6, f"statcheck found 6 APA tests ({len(sa)})")
    for i, lab in enumerate(["t(196) = 4.40, p < .001", "r(197) = .31, p < .001", "F(2, 196) = 15.15, p < .001"]):
        check(sa[i]["verdict"] == "consistent", f"{lab} consistent (recomputed {fmt_range(sa[i]['p_lo'], sa[i]['p_hi'])})")
    point_off = abs(sa[3]["p_computed"] - 0.049) > 0.0005
    check(sa[3]["verdict"] == "consistent" and point_off,
          f"t(20) = 2.09, p = .049 consistent only through the rounding interval (point p {sa[3]['p_computed']:.4f}, "
          f"range {fmt_range(sa[3]['p_lo'], sa[3]['p_hi'])})")
    check(sa[4]["verdict"] == "consistent" and sa[4]["p_lo"] < sa[4]["p_hi"],
          f"t(23.5) = 2.07, p = .05: decimal df widens the range ({fmt_range(sa[4]['p_lo'], sa[4]['p_hi'])}) and is consistent")
    check(sa[5]["verdict"] == "decision error",
          f"t(196) = 1.40, p < .001 inconsistent and a decision error (recomputed {fmt_range(sa[5]['p_lo'], sa[5]['p_hi'])})")
    n_bad = sum(x["verdict"] in ("inconsistent", "decision error") for x in sa)
    check(n_bad == 1, f"exactly 1 of the 6 APA lines flagged ({n_bad})")
    emit("## harman")
    rng = np.random.RandomState(11)
    noise = rng.normal(size=(150, 8))
    rows_n = [{f"q{j + 1}": f"{v:.3f}" for j, v in enumerate(r)} for r in noise]
    hn = harman_analyse(rows_n, [f"q{j + 1}" for j in range(8)])
    check(hn["pc1_pct"] < 35, f"uncorrelated items: first component {hn['pc1_pct']:.1f}% (< 35)")
    f = rng.normal(size=(150, 1))
    common = 0.85 * f + 0.35 * rng.normal(size=(150, 8))
    rows_c = [{f"q{j + 1}": f"{v:.3f}" for j, v in enumerate(r)} for r in common]
    hc = harman_analyse(rows_c, [f"q{j + 1}" for j in range(8)])
    check(hc["pc1_pct"] >= 50, f"one strong common factor: first component {hc['pc1_pct']:.1f}% (>= 50)")

    def run_quiet(fn, **kw):
        """Run a CLI command silently and return the report lines it emitted."""
        import contextlib
        import io
        start = len(_LINES)
        with contextlib.redirect_stdout(io.StringIO()):
            fn(argparse.Namespace(**kw))
        out = list(_LINES[start:])
        del _LINES[start:]
        return out

    path_c = os.path.join(d, "selftest_common.csv")
    with open(path_c, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[f"q{j + 1}" for j in range(8)])
        w.writeheader()
        w.writerows(rows_c)
    one = run_quiet(harman, csv=path_c, items=[["q1", "q2", "q3", "q4"]], items2=None, out=None)
    check(any(x.startswith("# WARNING: only one construct") for x in one) and any(x.startswith("verdict: NOT GIVEN") for x in one)
          and not any("SUSPECTED" in x for x in one), "harman with --items only: WARNING printed, no SUSPECTED verdict")
    two = run_quiet(harman, csv=path_c, items=[["q1", "q2", "q3", "q4"]], items2=["q5", "q6", "q7", "q8"], out=None)
    check(any("SUSPECTED" in x for x in two), "harman with --items2: verdict given (SUSPECTED on the common-factor data)")
    emit("## careless APA sentence")
    base = dict(csv=path, items=items, scale=(1, 5), duration=None, duration_unit="s", min_seconds=None, id="id",
                longstring=None, irv_min=0.0, mahal_alpha=0.001, dup_items=False, drop_review=False, clean=None, out=None)
    no_dur = [x for x in run_quiet(careless, **base) if x.startswith("# APA:")]
    check(no_dur and "Response time was not screened" in no_dur[0], "careless without --duration: APA sentence says response time was not screened")
    with_dur = [x for x in run_quiet(careless, **dict(base, duration="secs")) if x.startswith("# APA:")]
    check(with_dur and "not screened" not in with_dur[0] and "completion under" in with_dur[0],
          "careless with --duration: APA sentence reports the speeder screen")
    emit(f"RESULT: {'PASS' if not fails else 'FAIL'} ({len(fails)} failed checks)")
    return not fails


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("careless", help="flag careless or invalid survey rows and write a cleaned CSV",
                       epilog="example: autopsy.py careless data.csv --items q1 q2 q3 q4 --scale 1 5 "
                              "--duration secs --id id --out analysis/autopsy.txt --clean analysis/cleaned.csv")
    c.add_argument("csv")
    c.add_argument("--items", nargs="+", required=True, help="item columns in questionnaire order")
    c.add_argument("--scale", nargs=2, type=float, metavar=("LO", "HI"), help="valid range, e.g. 1 5")
    c.add_argument("--duration", help="completion-time column")
    c.add_argument("--duration-unit", choices=["s", "ms", "min"], default="s")
    c.add_argument("--min-seconds", type=float, help="speeder threshold (default 2 s per item)")
    c.add_argument("--id", help="respondent id column (excluded from duplicate matching)")
    c.add_argument("--longstring", type=int, help="flag runs of identical answers >= this (default: all items "
                                                  "if <= 8 items, else three quarters of the items)")
    c.add_argument("--irv-min", type=float, default=0.0, help="flag intra-individual SD <= this (default 0)")
    c.add_argument("--mahal-alpha", type=float, default=0.001, help="Mahalanobis outlier p threshold")
    c.add_argument("--dup-items", action="store_true", help="duplicates = identical item answers only")
    c.add_argument("--drop-review", action="store_true", help="also drop REVIEW rows from the cleaned CSV")
    c.add_argument("--clean", help="write the cleaned CSV here")
    c.add_argument("--out", help="write this report (with evidence lines) here, e.g. analysis/autopsy.txt")
    c.set_defaults(fn=careless)

    g = sub.add_parser("grim", help="GRIM test of a reported mean (and GRIMMER of its SD with --sd)",
                       epilog="example: autopsy.py grim --mean 3.42 --n 200 --items 1 --sd 1.07 --scale 1 5")
    g.add_argument("--mean", required=True, help="as printed, e.g. 3.42 (decimals are read from it)")
    g.add_argument("--n", type=int, required=True)
    g.add_argument("--items", type=int, default=1, help="items averaged into the score (default 1)")
    g.add_argument("--decimals", type=int, help="override the decimals of the reported mean")
    g.add_argument("--sd", help="reported SD, runs GRIMMER")
    g.add_argument("--sd-decimals", type=int)
    g.add_argument("--ddof", type=int, default=1, help="1 = sample SD (default), 0 = population SD")
    g.add_argument("--scale", nargs=2, type=float, metavar=("LO", "HI"), help="response range, adds the max-SD bound")
    g.add_argument("--out")
    g.set_defaults(fn=grim)

    h = sub.add_parser("harman", help="Harman's single-factor test on pooled items",
                       epilog="example: autopsy.py harman data.csv --items q1 q2 q3 --items2 q4 q5 q6")
    h.add_argument("csv")
    h.add_argument("--items", nargs="+", action="append", required=True, help="repeatable item group")
    h.add_argument("--items2", nargs="+", help="second construct's items")
    h.add_argument("--out")
    h.set_defaults(fn=harman)

    s = sub.add_parser("statcheck", help="recompute p values reported in a text and flag inconsistencies",
                       epilog="example: autopsy.py statcheck results.md --alpha 0.05")
    s.add_argument("file")
    s.add_argument("--alpha", type=float, default=0.05)
    s.add_argument("--one-tailed", action="store_true", help="treat t, r and z tests as one-tailed")
    s.add_argument("--out")
    s.set_defaults(fn=statcheck)

    t = sub.add_parser("selftest", help="synthetic data with planted errors; every command must catch them",
                       epilog="example: autopsy.py selftest --dir scratch/")
    t.add_argument("--dir", help="where to write selftest_data.csv (default: a temp folder)")
    t.set_defaults(fn=selftest)

    a = ap.parse_args()
    ok = a.fn(a)
    if a.cmd in ("grim", "statcheck", "selftest") and not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
