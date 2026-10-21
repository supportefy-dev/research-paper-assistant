#!/usr/bin/env python3
"""analyze_sem.py - mediation, moderation, CFA (reliability / validity) and basic PLS-SEM
on the user's own CSV, written as evidence lines like analyze.py.

Every result is one `key.label = value` line (the LAST dot-segment is the statistic
label that `scholar.py numbers` matches), plus '# APA:' ready sentences and
'# note:' / '# order:' lines for anything the writer must know. Needs numpy and
scipy; `cfa` uses semopy when it is installed (full CFA with fit indices) and
otherwise falls back to a clearly labelled approximation.

Usage (append each run to the evidence file):
  python -X utf8 analyze_sem.py data.csv mediate --x cond --m pmi --y reaction [--covariates age gender] [--boot 5000] [--seed 1]
  python -X utf8 analyze_sem.py data.csv moderate --x frame --w skeptic --y justify [--center] [--boot 2000]
  python -X utf8 analyze_sem.py data.csv cfa --model "Stress = q1 q2 q3; Sleep = q4 q5 q6"
  python -X utf8 analyze_sem.py data.csv pls --model "A = a1 a2 a3; B = b1 b2 b3; Y = y1 y2 y3" --paths "A->Y; B->Y" [--boot 1000]
  python -X utf8 analyze_sem.py selftest [--pmi pmi.csv] [--disaster disaster.csv]   (seeded synthetic checks + Hayes examples)

Missing or non-numeric cells are dropped listwise per analysis; n is always reported.
All bootstraps are seeded (--seed, default 1) so a re-run reproduces the numbers.
"""

import argparse
import contextlib
import csv
import io
import math
import os
import re
import sys

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
try:
    from scholar import table
except ImportError:  # keep the statistics usable even if scholar.py moves
    def table(rows, headers):
        out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
        out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
        return "\n".join(out)

SEMOPY_HINT = "pip install semopy   (free, MIT; brings pandas, statsmodels, scikit-learn)"


# ---------------------------------------------------------------- shared (same conventions as analyze.py)

def load(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        rows = list(csv.DictReader(f, dialect=dialect))
    if not rows:
        sys.exit("empty file")
    return rows


def num(v):
    try:
        return float(str(v).strip().replace(",", ".")) if str(v).strip() != "" else math.nan
    except ValueError:
        return math.nan


def columns(rows, names):
    missing = [n for n in names if n not in rows[0]]
    if missing:
        sys.exit(f"unknown column(s): {', '.join(missing)}. Available: {', '.join(rows[0].keys())}")
    m = np.array([[num(r[n]) for n in names] for r in rows], dtype=float)
    keep = ~np.isnan(m).any(axis=1)
    return m[keep], int((~keep).sum())


def out(key, value):
    if isinstance(value, (float, np.floating)):
        value = float(value)
        if math.isnan(value):
            value = "NA"
        else:
            value = f"{value:.6g}" if abs(value) < 1e-4 and value != 0 else f"{value:.6f}".rstrip("0").rstrip(".")
    print(f"{key} = {value}")


def apa_num(x, lead=True, dec=2):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "NA"
    s = f"{x:.{dec}f}"
    if not lead:
        s = s.replace("0.", ".", 1) if s.startswith(("0.", "-0.")) else s
    return s


def apa_p(p):
    if p is None or math.isnan(p):
        return "p = NA"
    return "p < .001" if p < 0.001 else f"p = {apa_num(p, lead=False, dec=3)}"


def zscore(v):
    sd = v.std(ddof=1)
    return (v - v.mean()) / sd if sd > 0 else v - v.mean()


def ols(y, X, names):
    """OLS with intercept. names = predictor names (without the constant)."""
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    n = len(y)
    D = np.column_stack([np.ones(n), X])
    p = D.shape[1]
    coef, *_ = np.linalg.lstsq(D, y, rcond=None)
    resid = y - D @ coef
    dfe = n - p
    if dfe < 1:
        sys.exit(f"not enough rows ({n}) for {p} coefficients")
    sse = float(resid @ resid)
    sst = float(((y - y.mean()) ** 2).sum())
    cov = sse / dfe * np.linalg.pinv(D.T @ D)
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = coef / se
    pv = 2 * stats.t.sf(np.abs(t), dfe)
    tcrit = stats.t.ppf(0.975, dfe)
    return {"names": ["constant"] + list(names), "coef": coef, "se": se, "t": t, "p": pv,
            "ci_low": coef - tcrit * se, "ci_high": coef + tcrit * se, "dfe": dfe, "tcrit": tcrit,
            "r2": 1 - sse / sst if sst > 0 else math.nan, "cov": cov, "n": n}


def report_coef(key, fit, i, apa_label=None, beta=None):
    out(f"{key}.b", float(fit["coef"][i]))
    out(f"{key}.se", float(fit["se"][i]))
    out(f"{key}.t", float(fit["t"][i]))
    out(f"{key}.p", float(fit["p"][i]))
    out(f"{key}.ci_low", float(fit["ci_low"][i]))
    out(f"{key}.ci_high", float(fit["ci_high"][i]))
    if beta is not None:
        out(f"{key}.beta", float(beta))
    if apa_label:
        print(f"# APA: {apa_label}: B = {apa_num(fit['coef'][i])}, SE = {apa_num(fit['se'][i])}, "
              f"t({fit['dfe']}) = {apa_num(fit['t'][i])}, {apa_p(fit['p'][i])}, "
              f"95% CI [{apa_num(fit['ci_low'][i])}, {apa_num(fit['ci_high'][i])}]")


def percentile_ci(boot, alpha=0.05):
    boot = np.asarray(boot, dtype=float)
    boot = boot[~np.isnan(boot)]
    return float(np.percentile(boot, 100 * alpha / 2)), float(np.percentile(boot, 100 * (1 - alpha / 2)))


def bc_ci(boot, estimate, alpha=0.05):
    """Bias-corrected bootstrap CI (Efron): adjusts the percentiles for median bias."""
    boot = np.asarray(boot, dtype=float)
    boot = boot[~np.isnan(boot)]
    prop = float((boot < estimate).mean())
    if prop <= 0 or prop >= 1:
        return percentile_ci(boot, alpha)
    z0 = stats.norm.ppf(prop)
    lo = stats.norm.cdf(2 * z0 + stats.norm.ppf(alpha / 2))
    hi = stats.norm.cdf(2 * z0 + stats.norm.ppf(1 - alpha / 2))
    return float(np.percentile(boot, 100 * lo)), float(np.percentile(boot, 100 * hi))


def ci_text(lo, hi, lead=True):
    return f"95% CI [{apa_num(lo, lead=lead)}, {apa_num(hi, lead=lead)}]"


def header(rows, a, what):
    print(f"# {what} | file {a.csv} | rows {len(rows)}")


# ---------------------------------------------------------------- mediate (Hayes PROCESS Model 4)

def mediate(rows, a):
    covs = a.covariates or []
    names = [a.x, a.m, a.y] + covs
    data, dropped = columns(rows, names)
    n = len(data)
    X, M, Y = data[:, 0], data[:, 1], data[:, 2]
    C = data[:, 3:]
    key = f"mediate.{a.x}-{a.m}-{a.y}"
    header(rows, a, f"mediate {a.x} -> {a.m} -> {a.y}" + (f" | covariates {' '.join(covs)}" if covs else "")
           + f" | boot {a.boot} | seed {a.seed}")
    out(f"{key}.n", n)
    out(f"{key}.excluded", dropped)
    fit_a = ols(M, np.column_stack([X, C]), [a.x] + covs)
    fit_b = ols(Y, np.column_stack([X, M, C]), [a.x, a.m] + covs)
    fit_c = ols(Y, np.column_stack([X, C]), [a.x] + covs)
    av, bv, cv = fit_a["coef"][1], fit_b["coef"][2], fit_c["coef"][1]
    print(f"# path a: {a.m} on {a.x}" + (" + covariates" if covs else ""))
    out(f"{key}.m_model.r2", fit_a["r2"])
    out(f"{key}.m_model.constant.b", float(fit_a["coef"][0]))
    report_coef(f"{key}.a", fit_a, 1, f"a ({a.x} -> {a.m})")
    print(f"# paths b and c': {a.y} on {a.x} and {a.m}" + (" + covariates" if covs else ""))
    out(f"{key}.y_model.r2", fit_b["r2"])
    out(f"{key}.y_model.constant.b", float(fit_b["coef"][0]))
    report_coef(f"{key}.b", fit_b, 2, f"b ({a.m} -> {a.y})")
    report_coef(f"{key}.cprime", fit_b, 1, f"c' (direct {a.x} -> {a.y})")
    print(f"# path c: total effect, {a.y} on {a.x}" + (" + covariates" if covs else ""))
    out(f"{key}.total_model.r2", fit_c["r2"])
    report_coef(f"{key}.c", fit_c, 1, f"c (total {a.x} -> {a.y})")
    for j, cov in enumerate(covs):
        out(f"{key}.m_model.{cov}.b", float(fit_a["coef"][2 + j]))
        out(f"{key}.m_model.{cov}.p", float(fit_a["p"][2 + j]))
        out(f"{key}.y_model.{cov}.b", float(fit_b["coef"][3 + j]))
        out(f"{key}.y_model.{cov}.p", float(fit_b["p"][3 + j]))

    ind = float(av * bv)
    se_sobel = math.sqrt(av ** 2 * fit_b["se"][2] ** 2 + bv ** 2 * fit_a["se"][1] ** 2)
    z = ind / se_sobel if se_sobel > 0 else math.nan
    # Bootstrap: resample cases, refit both equations, keep a*b.
    rng = np.random.default_rng(a.seed)
    boot = np.empty(a.boot)
    Da = np.column_stack([np.ones(n), X, C])
    Db = np.column_stack([np.ones(n), X, M, C])
    for i in range(a.boot):
        idx = rng.integers(0, n, n)
        ca, *_ = np.linalg.lstsq(Da[idx], M[idx], rcond=None)
        cb, *_ = np.linalg.lstsq(Db[idx], Y[idx], rcond=None)
        boot[i] = ca[1] * cb[2]
    p_lo, p_hi = percentile_ci(boot)
    b_lo, b_hi = bc_ci(boot, ind)
    boot_se = float(boot.std(ddof=1))
    out(f"{key}.indirect.b", ind)
    out(f"{key}.indirect.se", boot_se)
    out(f"{key}.indirect.ci_low", p_lo)
    out(f"{key}.indirect.ci_high", p_hi)
    out(f"{key}.indirect.bc.ci_low", b_lo)
    out(f"{key}.indirect.bc.ci_high", b_hi)
    out(f"{key}.indirect.boot", a.boot)
    out(f"{key}.sobel.z", z)
    out(f"{key}.sobel.p", float(2 * stats.norm.sf(abs(z))) if not math.isnan(z) else math.nan)
    std_ind = ind * X.std(ddof=1) / Y.std(ddof=1)
    out(f"{key}.indirect.beta", std_ind)
    sig = "excludes" if (p_lo > 0 or p_hi < 0) else "includes"
    print(f"# APA: indirect effect (a x b) = {apa_num(ind, dec=3)}, boot SE = {apa_num(boot_se, dec=3)}, "
          f"{a.boot} bootstrap samples, percentile 95% CI [{apa_num(p_lo, dec=3)}, {apa_num(p_hi, dec=3)}] "
          f"({sig} zero); bias-corrected 95% CI [{apa_num(b_lo, dec=3)}, {apa_num(b_hi, dec=3)}]; "
          f"completely standardized indirect effect = {apa_num(std_ind, lead=False, dec=3)}")
    if abs(cv) > 1e-12 and (ind * cv) > 0:
        pm = ind / cv
        out(f"{key}.indirect.pm", pm)
        print(f"# APA: proportion mediated = {apa_num(pm, lead=False, dec=3)} (indirect / total)")
        if pm > 1:
            print("# note: proportion mediated above 1 (direct effect has the opposite sign): report the "
                  "indirect effect and its CI instead of a percentage")
    else:
        out(f"{key}.indirect.pm", math.nan)
        print("# note: proportion mediated not reported (total effect near zero or opposite in sign to the "
              "indirect effect); report the indirect effect with its bootstrap CI")
    if len(set(np.round(X, 9))) == 2:
        print(f"# note: {a.x} is dichotomous: the completely standardized indirect effect is not meaningful "
              "for a two-group X (Hayes recommends the unstandardized or partially standardized effect)")
    print("# order: paths are a (X -> M), b (M -> Y controlling X), c' (direct), c (total); indirect = a x b. "
          "Percentile CI is PROCESS v3+ default; bias-corrected matches PROCESS v2 output")
    print("# note: mediation here is a statistical decomposition; causal wording needs design support "
          "(experimental X or temporal ordering)")


# ---------------------------------------------------------------- moderate (Hayes PROCESS Model 1)

def moderate(rows, a):
    covs = a.covariates or []
    names = [a.x, a.w, a.y] + covs
    data, dropped = columns(rows, names)
    n = len(data)
    X, W, Y = data[:, 0].copy(), data[:, 1].copy(), data[:, 2]
    C = data[:, 3:]
    w_mean, w_sd = float(W.mean()), float(W.std(ddof=1))
    x_mean = float(X.mean())
    key = f"moderate.{a.x}-by-{a.w}-{a.y}"
    header(rows, a, f"moderate {a.x} x {a.w} -> {a.y}" + (f" | covariates {' '.join(covs)}" if covs else "")
           + f" | center {'yes' if a.center else 'no'}" + (f" | boot {a.boot} | seed {a.seed}" if a.boot else ""))
    out(f"{key}.n", n)
    out(f"{key}.excluded", dropped)
    if a.center:
        X = X - x_mean
        W = W - w_mean
        print(f"# note: {a.x} and {a.w} mean-centered before forming the product "
              f"(means {apa_num(x_mean, dec=3)} and {apa_num(w_mean, dec=3)}); coefficients of {a.x} and {a.w} "
              "are conditional effects at the other variable's mean")
    else:
        print(f"# note: variables not centered: the coefficient of {a.x} is its effect when {a.w} = 0 "
              f"(and vice versa); use --center if 0 is not meaningful")
    XW = X * W
    fit = ols(Y, np.column_stack([X, W, XW, C]), [a.x, a.w, f"{a.x}x{a.w}"] + covs)
    red = ols(Y, np.column_stack([X, W, C]), [a.x, a.w] + covs)
    r2, r2r = fit["r2"], red["r2"]
    d_r2 = r2 - r2r
    f2 = d_r2 / (1 - r2) if r2 < 1 else math.nan
    F_change = (d_r2 / 1) / ((1 - r2) / fit["dfe"]) if r2 < 1 else math.nan
    p_change = float(stats.f.sf(F_change, 1, fit["dfe"])) if not math.isnan(F_change) else math.nan
    out(f"{key}.r2", r2)
    out(f"{key}.delta_r2", d_r2)
    out(f"{key}.f2", f2)
    out(f"{key}.f_change", float(F_change))
    out(f"{key}.df1", 1)
    out(f"{key}.df2", fit["dfe"])
    out(f"{key}.p_change", p_change)
    out(f"{key}.constant.b", float(fit["coef"][0]))
    print(f"# APA: model R² = {apa_num(r2, lead=False)}; interaction ΔR² = {apa_num(d_r2, lead=False, dec=3)}, "
          f"F(1, {fit['dfe']}) = {apa_num(F_change)}, {apa_p(p_change)}, f² = {apa_num(f2, lead=False, dec=3)}")
    report_coef(f"{key}.x", fit, 1, f"{a.x}")
    report_coef(f"{key}.w", fit, 2, f"{a.w}")
    report_coef(f"{key}.xw", fit, 3, f"{a.x} x {a.w} (interaction)")
    for j, cov in enumerate(covs):
        out(f"{key}.{cov}.b", float(fit["coef"][4 + j]))
        out(f"{key}.{cov}.p", float(fit["p"][4 + j]))

    b1, b3 = fit["coef"][1], fit["coef"][3]
    v11, v13, v33 = fit["cov"][1, 1], fit["cov"][1, 3], fit["cov"][3, 3]
    tc, dfe = fit["tcrit"], fit["dfe"]

    def slope_at(w):
        s = b1 + b3 * w
        se = math.sqrt(max(v11 + 2 * w * v13 + w * w * v33, 0))
        t = s / se if se > 0 else math.nan
        p = 2 * stats.t.sf(abs(t), dfe) if not math.isnan(t) else math.nan
        return s, se, t, p

    # Simple slopes at W = mean - 1 SD, mean, mean + 1 SD (original scale shown in the APA line).
    offsets = [(-1, "low"), (0, "mean"), (1, "high")]
    probe = []
    for k_sd, lab in offsets:
        w_model = (k_sd * w_sd) if a.center else (w_mean + k_sd * w_sd)
        w_orig = w_mean + k_sd * w_sd
        s, se, t, p = slope_at(w_model)
        probe.append((lab, w_model, w_orig))
        kk = f"{key}.slope.{lab}"
        out(f"{kk}.w_value", w_orig)
        out(f"{kk}.b", s)
        out(f"{kk}.se", se)
        out(f"{kk}.t", t)
        out(f"{kk}.p", p)
        out(f"{kk}.ci_low", s - tc * se)
        out(f"{kk}.ci_high", s + tc * se)
        where = "mean" if k_sd == 0 else ("mean + 1 SD" if k_sd > 0 else "mean - 1 SD")
        print(f"# APA: simple slope of {a.x} at {a.w} = {apa_num(w_orig)} ({where}): "
              f"B = {apa_num(s)}, SE = {apa_num(se)}, t({dfe}) = {apa_num(t)}, {apa_p(p)}, "
              f"{ci_text(s - tc * se, s + tc * se)}")
    print(f"# order: {a.w} probed at mean - 1 SD, mean, mean + 1 SD ({apa_num(w_mean - w_sd)}, {apa_num(w_mean)}, "
          f"{apa_num(w_mean + w_sd)}); use observed percentiles instead if {a.w} is skewed")

    # Johnson-Neyman: W where the conditional effect of X crosses t_crit (quadratic in w).
    A = b3 ** 2 - tc ** 2 * v33
    B = 2 * b1 * b3 - 2 * tc ** 2 * v13
    Cq = b1 ** 2 - tc ** 2 * v11
    wmin, wmax = float(W.min()), float(W.max())
    roots = []
    if abs(A) > 1e-14:
        disc = B * B - 4 * A * Cq
        if disc >= 0:
            roots = sorted({(-B - math.sqrt(disc)) / (2 * A), (-B + math.sqrt(disc)) / (2 * A)})
    elif abs(B) > 1e-14:
        roots = [-Cq / B]
    inside = [r for r in roots if wmin < r < wmax]
    shift = w_mean if a.center else 0.0
    cuts = [wmin] + inside + [wmax]
    segs = []
    for lo, hi in zip(cuts[:-1], cuts[1:]):
        mid = (lo + hi) / 2
        _, _, t, _ = slope_at(mid)
        segs.append((lo, hi, abs(t) >= tc if not math.isnan(t) else False))
    sig_pct = 100 * sum(float(((W >= lo) & (W <= hi)).mean()) for lo, hi, s in segs if s)
    for i, r in enumerate(inside, 1):
        out(f"{key}.jn.boundary{i}", r + shift)
    out(f"{key}.jn.boundaries", len(inside))
    out(f"{key}.jn.pct_significant", sig_pct)
    if not inside:
        if all(s for _, _, s in segs):
            print(f"# APA: Johnson-Neyman: the effect of {a.x} is significant across the whole observed range of "
                  f"{a.w} ({apa_num(wmin + shift)} to {apa_num(wmax + shift)}); no transition point inside the range")
        elif not any(s for _, _, s in segs):
            print(f"# APA: Johnson-Neyman: the effect of {a.x} is not significant anywhere in the observed range of "
                  f"{a.w} ({apa_num(wmin + shift)} to {apa_num(wmax + shift)}); no region of significance")
        else:
            print("# note: Johnson-Neyman roots fall outside the observed range; see simple slopes")
    else:
        parts = [f"{apa_num(lo + shift)} to {apa_num(hi + shift)}" for lo, hi, s in segs if s]
        print(f"# APA: Johnson-Neyman transition point(s) at {a.w} = "
              f"{', '.join(apa_num(r + shift, dec=3) for r in inside)}; the effect of {a.x} is significant for "
              f"{a.w} in [{'; '.join(parts) if parts else 'none'}] ({apa_num(sig_pct, dec=1)}% of the sample)")
    if a.boot:
        rng = np.random.default_rng(a.seed)
        D = np.column_stack([np.ones(n), X, W, XW, C])
        bb = np.empty((a.boot, 4))
        for i in range(a.boot):
            idx = rng.integers(0, n, n)
            cf, *_ = np.linalg.lstsq(D[idx], Y[idx], rcond=None)
            bb[i, 0] = cf[3]
            for j, (lab, w_model, _) in enumerate(probe, 1):
                bb[i, j] = cf[1] + cf[3] * w_model
        lo, hi = percentile_ci(bb[:, 0])
        out(f"{key}.xw.boot.ci_low", lo)
        out(f"{key}.xw.boot.ci_high", hi)
        print(f"# APA: interaction bootstrap ({a.boot} samples) percentile {ci_text(lo, hi)}")
        for j, (lab, _, w_orig) in enumerate(probe, 1):
            lo, hi = percentile_ci(bb[:, j])
            out(f"{key}.slope.{lab}.boot.ci_low", lo)
            out(f"{key}.slope.{lab}.boot.ci_high", hi)
    if len(set(np.round(data[:, 0], 9))) == 2:
        print(f"# note: {a.x} is dichotomous: the simple slopes are group differences in {a.y} at each level of {a.w}")


# ---------------------------------------------------------------- measurement helpers (cfa + pls)

def parse_model(text):
    """'LV1 = q1 q2 q3; LV2 = q4 + q5' (also lavaan '=~') -> [(lv, [items])]."""
    model = []
    for part in re.split(r"[;\n]+", text):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^\s*([A-Za-z_][\w]*)\s*=~?\s*(.+)$", part)
        if not m:
            sys.exit(f"cannot parse model part '{part}': use 'LV = item1 item2 item3; ...'")
        items = [i for i in re.split(r"[\s+,]+", m.group(2).strip()) if i]
        model.append((m.group(1), items))
    if not model:
        sys.exit("empty model")
    seen = {}
    for lv, items in model:
        for it in items:
            if it in seen:
                sys.exit(f"item {it} appears in both {seen[it]} and {lv}: one item, one construct")
            seen[it] = lv
    return model


def parse_paths(text, lvs):
    paths = []
    for part in re.split(r"[;,\n]+", text):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^\s*(\w+)\s*->\s*(\w+)\s*$", part)
        if not m:
            sys.exit(f"cannot parse path '{part}': use 'A->B; C->B'")
        src, dst = m.group(1), m.group(2)
        for v in (src, dst):
            if v not in lvs:
                sys.exit(f"path {src}->{dst}: construct {v} is not in --model")
        paths.append((src, dst))
    return paths


def cronbach(m):
    k = m.shape[1]
    if k < 2:
        return math.nan
    tv = m.sum(axis=1).var(ddof=1)
    return k / (k - 1) * (1 - m.var(axis=0, ddof=1).sum() / tv) if tv > 0 else math.nan


def cr_ave(lams):
    lams = np.asarray(lams, dtype=float)
    s = lams.sum()
    err = (1 - lams ** 2).sum()
    cr = s * s / (s * s + err) if (s * s + err) > 0 else math.nan
    return cr, float((lams ** 2).mean())


def paf_single_factor(block):
    """Iterated principal-axis loadings of ONE factor on a standardized block (approximation, not CFA)."""
    k = block.shape[1]
    R = np.corrcoef(block.T)
    if k == 1:
        return np.array([1.0]), "single-item construct: loading fixed to 1"
    if k == 2:
        r = R[0, 1]
        lam = math.sqrt(abs(r))
        return np.array([lam, math.copysign(lam, r)]), "two-item construct: equal loadings sqrt(|r|), not identified alone"
    try:
        h = 1 - 1 / np.diag(np.linalg.inv(R))
    except np.linalg.LinAlgError:
        h = np.full(k, 0.5)
    h = np.clip(h, 0.05, 0.99)
    lam = np.zeros(k)
    note = ""
    for _ in range(500):
        Rr = R.copy()
        np.fill_diagonal(Rr, h)
        vals, vecs = np.linalg.eigh(Rr)
        v = max(vals[-1], 1e-9)
        new = vecs[:, -1] * math.sqrt(v)
        if new.sum() < 0:
            new = -new
        h_new = np.clip(new ** 2, 0, 0.9999)
        done = np.abs(h_new - h).max() < 1e-7
        h, lam = h_new, new
        if done:
            break
    else:
        note = "principal-axis iteration did not converge in 500 steps"
    if (np.abs(lam) > 0.999).any():
        note = (note + "; " if note else "") + "Heywood case (loading at 1): construct likely has a redundant item"
    return lam, note


def htmt_matrix(data, model):
    """Henseler et al. (2015) HTMT on absolute item correlations (reverse-code items first)."""
    names = [it for _, items in model for it in items]
    pos = {it: i for i, it in enumerate(names)}
    R = np.abs(np.corrcoef(data.T))
    J = len(model)
    H = np.full((J, J), math.nan)
    for i in range(J):
        for j in range(i + 1, J):
            a_items = [pos[x] for x in model[i][1]]
            b_items = [pos[x] for x in model[j][1]]
            if len(a_items) < 2 or len(b_items) < 2:
                continue
            hetero = R[np.ix_(a_items, b_items)].mean()
            ma = R[np.ix_(a_items, a_items)][np.triu_indices(len(a_items), 1)].mean()
            mb = R[np.ix_(b_items, b_items)][np.triu_indices(len(b_items), 1)].mean()
            H[i, j] = H[j, i] = hetero / math.sqrt(ma * mb) if ma > 0 and mb > 0 else math.nan
    return H


def report_measurement(prefix, model, data, loadings, lv_corr, corr_note, items_note=None):
    """Loadings, alpha, CR, AVE, Fornell-Larcker and HTMT. loadings: {lv: {item: lambda}}."""
    names = [it for _, items in model for it in items]
    pos = {it: i for i, it in enumerate(names)}
    sq_ave = []
    for lv, items in model:
        lams = np.array([loadings[lv][it] for it in items])
        block = data[:, [pos[it] for it in items]]
        al = cronbach(block)
        cr, ave = cr_ave(lams)
        sq_ave.append(math.sqrt(ave) if ave == ave else math.nan)
        out(f"{prefix}.{lv}.items", len(items))
        for it in items:
            out(f"{prefix}.{lv}.{it}.loading", float(loadings[lv][it]))
        out(f"{prefix}.{lv}.alpha", al)
        out(f"{prefix}.{lv}.cr", cr)
        out(f"{prefix}.{lv}.ave", ave)
        out(f"{prefix}.{lv}.sqrt_ave", sq_ave[-1])
        flags = []
        if len(items) >= 2 and not math.isnan(al) and al < 0.70:
            flags.append("α < .70")
        if cr == cr and cr < 0.70:
            flags.append("CR < .70")
        if ave == ave and ave < 0.50:
            flags.append("AVE < .50")
        low = [f"{it} ({loadings[lv][it]:.2f})" for it in items if abs(loadings[lv][it]) < 0.70]
        neg = [it for it in items if loadings[lv][it] < 0]
        print(f"# APA: {lv}: {len(items)} item{'s' if len(items) != 1 else ''}, standardized loadings "
              f"{apa_num(min(lams), lead=False)} to {apa_num(max(lams), lead=False)}, "
              f"α = {apa_num(al, lead=False)}, CR = {apa_num(cr, lead=False)}, AVE = {apa_num(ave, lead=False)}"
              + (f"  [{'; '.join(flags)}]" if flags else ""))
        if low:
            print(f"# note: {lv}: loading(s) below .70: {', '.join(low)} (keep if CR and AVE hold and the item "
                  "matters for content validity; .40-.70 is the usual deletion-consideration band)")
        if neg:
            print(f"# note: {lv}: negative loading(s) {', '.join(neg)}: reverse-coded item(s) not recoded?")
        if len(items) == 2:
            print(f"# note: {lv} has 2 items: reliability is Spearman-Brown territory; loadings are not "
                  "identified on their own")
    J = len(model)
    lvs = [lv for lv, _ in model]
    # Fornell-Larcker: sqrt(AVE) on the diagonal must exceed every construct correlation in its row/column.
    rows_fl, violations = [], []
    for i in range(J):
        row = [lvs[i]]
        for j in range(J):
            if i == j:
                row.append(f"({apa_num(sq_ave[i], lead=False, dec=3)})")
            elif j < i:
                r = float(lv_corr[i, j])
                row.append(apa_num(r, lead=False, dec=3))
                out(f"{prefix}.fl.{lvs[i]}-{lvs[j]}.r", r)
                if r == r and (abs(r) > sq_ave[i] or abs(r) > sq_ave[j]):
                    violations.append(f"{lvs[i]}-{lvs[j]} (r = {apa_num(r, lead=False, dec=3)})")
            else:
                row.append("")
        rows_fl.append(row)
    print("# Fornell-Larcker (diagonal = sqrt AVE in parentheses; below = construct correlations" + f", {corr_note})")
    print("\n".join("# " + ln for ln in table(rows_fl, [""] + lvs).splitlines()))
    out(f"{prefix}.fl.violations", len(violations))
    print("# APA: Fornell-Larcker criterion " + ("met: each sqrt(AVE) exceeds the construct's correlations with the others"
          if not violations else "NOT met for " + ", ".join(violations)))
    H = htmt_matrix(data, model)
    rows_h = []
    worst = 0.0
    for i in range(J):
        row = [lvs[i]]
        for j in range(J):
            if j < i:
                h = H[i, j]
                row.append(apa_num(h, lead=False, dec=3) if h == h else "NA")
                out(f"{prefix}.htmt.{lvs[i]}-{lvs[j]}", h)
                if h == h:
                    worst = max(worst, h)
            else:
                row.append("")
        rows_h.append(row)
    if J > 1:
        print("# HTMT (Henseler et al. 2015; threshold .85 conservative, .90 liberal)")
        print("\n".join("# " + ln for ln in table(rows_h, [""] + lvs).splitlines()))
        out(f"{prefix}.htmt.max", worst)
        print(f"# APA: all HTMT ratios {'below' if worst < 0.85 else 'NOT below'} .85 (max = {apa_num(worst, lead=False, dec=3)})"
              + ("; discriminant validity is in question for the pair(s) at or above .85" if worst >= 0.85 else ""))
        print("# note: HTMT uses absolute item correlations; single-item constructs have no HTMT (NA)")
    if items_note:
        print(f"# note: {items_note}")


# ---------------------------------------------------------------- cfa

def cfa_semopy(data, names, model):
    """Full CFA with semopy (ML). Returns (loadings, lv_corr, fit) or None when semopy is missing."""
    try:
        import semopy
        import pandas as pd
    except ImportError:
        return None
    desc = "\n".join(f"{lv} =~ " + " + ".join(items) for lv, items in model)
    df = pd.DataFrame(data, columns=names)
    mod = semopy.Model(desc)
    res = mod.fit(df)
    ins = mod.inspect(std_est=True)
    lvs = [lv for lv, _ in model]
    loadings = {lv: {} for lv in lvs}
    for _, r in ins.iterrows():
        if r["op"] == "~" and r["rval"] in loadings and r["lval"] in names:
            loadings[r["rval"]][r["lval"]] = float(r["Est. Std"])
    J = len(lvs)
    lv_corr = np.eye(J)
    for _, r in ins.iterrows():
        if r["op"] == "~~" and r["lval"] in lvs and r["rval"] in lvs and r["lval"] != r["rval"]:
            i, j = lvs.index(r["lval"]), lvs.index(r["rval"])
            lv_corr[i, j] = lv_corr[j, i] = float(r["Est. Std"])
    st = semopy.calc_stats(mod)
    fit = {k: float(st[k].iloc[0]) for k in ("DoF", "chi2", "chi2 p-value", "CFI", "TLI", "RMSEA", "GFI", "AGFI", "AIC", "BIC")
           if k in st.columns}
    if "CFI" in fit:
        fit["CFI"] = min(fit["CFI"], 1.0)   # lavaan convention: CFI is capped at 1 when chi2 < df; TLI is not
    # SRMR from the model-implied covariance versus the sample covariance.
    try:
        sigma, _ = mod.calc_sigma()
        obs = list(mod.vars["observed"])
        order = [names.index(v) for v in obs]
        S = np.cov(data[:, order].T, ddof=0)
        sig = np.asarray(sigma, dtype=float)
        d = np.sqrt(np.outer(np.diag(S), np.diag(S)))
        resid = (S - sig) / d
        iu = np.triu_indices(len(obs))
        fit["SRMR"] = float(np.sqrt((resid[iu] ** 2).mean()))
    except Exception:  # noqa: BLE001 - SRMR is optional
        pass
    fit["converged"] = bool(getattr(res, "success", True))
    return loadings, lv_corr, fit


def cfa(rows, a):
    model = parse_model(a.model)
    names = [it for _, items in model for it in items]
    data, dropped = columns(rows, names)
    n = len(data)
    header(rows, a, f"cfa {a.model}")
    out("cfa.n", n)
    out("cfa.excluded", dropped)
    out("cfa.constructs", len(model))
    out("cfa.items", len(names))
    res, failed = None, False
    if not a.no_semopy:
        try:
            res = cfa_semopy(data, names, model)
        except Exception as e:  # noqa: BLE001 - semopy failed on this data: say so, fall back
            failed = True
            print(f"# WARNING: semopy failed ({type(e).__name__}: {str(e)[:120]}); falling back to the approximation")
    if res is not None:
        loadings, lv_corr, fit = res
        print("# estimator: semopy ML confirmatory factor analysis (standardized loadings, latent correlations)")
        if not fit.get("converged", True):
            print("# WARNING: semopy reports the optimisation did not converge; treat every value as provisional")
        report_measurement("cfa", model, data, loadings, lv_corr, "latent correlations from the CFA")
        chi2, df_, pchi = fit.get("chi2", math.nan), fit.get("DoF", math.nan), fit.get("chi2 p-value", math.nan)
        out("cfa.fit.chi2", chi2)
        out("cfa.fit.df", df_)
        out("cfa.fit.p", pchi)
        for k, lab in (("CFI", "cfi"), ("TLI", "tli"), ("RMSEA", "rmsea"), ("SRMR", "srmr"), ("GFI", "gfi"),
                       ("AIC", "aic"), ("BIC", "bic")):
            if k in fit:
                out(f"cfa.fit.{lab}", fit[k])
        if not math.isnan(chi2):
            out("cfa.fit.chi2_df", chi2 / df_ if df_ else math.nan)
        print(f"# APA: model fit: χ²({int(df_) if df_ == df_ else 'NA'}) = {apa_num(chi2)}, {apa_p(pchi)}, "
              f"CFI = {apa_num(fit.get('CFI', math.nan), lead=False, dec=3)}, "
              f"TLI = {apa_num(fit.get('TLI', math.nan), lead=False, dec=3)}, "
              f"RMSEA = {apa_num(fit.get('RMSEA', math.nan), lead=False, dec=3)}"
              + (f", SRMR = {apa_num(fit['SRMR'], lead=False, dec=3)}" if "SRMR" in fit else ""))
        flags = []
        if fit.get("CFI", 1) < 0.90:
            flags.append("CFI < .90")
        if fit.get("TLI", 1) < 0.90:
            flags.append("TLI < .90")
        if fit.get("RMSEA", 0) > 0.08:
            flags.append("RMSEA > .08")
        if fit.get("SRMR", 0) > 0.08:
            flags.append("SRMR > .08")
        print("# note: fit " + ("acceptable by the usual cut-offs (CFI/TLI >= .90, RMSEA <= .08, SRMR <= .08); "
                                "stricter: CFI/TLI >= .95, RMSEA <= .06" if not flags else "flags: " + ", ".join(flags)))
        print("# note: RMSEA 90% CI is not computed by semopy's calc_stats; omit it or compute it in lavaan/AMOS")
        return
    if not a.no_semopy and not failed:
        print(f"# WARNING: semopy not installed: {SEMOPY_HINT}")
    print("# estimator: APPROXIMATION, NOT FULL CFA: one principal-axis factor per construct (numpy), "
          "construct correlations from unit-weighted mean scores; no fit indices")
    loadings = {}
    notes = []
    scores = []
    pos = {it: i for i, it in enumerate(names)}
    for lv, items in model:
        block = data[:, [pos[it] for it in items]]
        lam, note = paf_single_factor(zscore_cols(block))
        loadings[lv] = {it: float(l) for it, l in zip(items, lam)}
        if note:
            notes.append(f"{lv}: {note}")
        scores.append(zscore_cols(block).mean(axis=1))
    lv_corr = np.corrcoef(np.array(scores)) if len(scores) > 1 else np.eye(1)
    lv_corr = np.atleast_2d(lv_corr)
    report_measurement("cfa", model, data, loadings, lv_corr, "unit-weighted mean scores, attenuated by error",
                       "; ".join(notes) if notes else None)
    print("# note: for a reviewer-ready CFA (chi2, CFI, TLI, RMSEA, SRMR, modification indices) install semopy "
          "and re-run, or run the same model in lavaan / AMOS; report this run as an approximation")


def zscore_cols(m):
    sd = m.std(axis=0, ddof=1)
    sd[sd == 0] = 1
    return (m - m.mean(axis=0)) / sd


# ---------------------------------------------------------------- pls (basic PLS path modelling)

def pls_fit(blocks, adj, max_iter=300, tol=1e-7):
    """Basic PLS path algorithm: mode A outer weights, path weighting scheme, standardized data.

    blocks: list of (n x k_j) standardized arrays; adj[i, j] = 1 when LV i -> LV j.
    Returns weights (list), scores (n x J), loadings (list), iterations, converged.
    """
    J = len(blocks)
    n = blocks[0].shape[0]
    weights = [np.ones(b.shape[1]) for b in blocks]
    Y = np.column_stack([zscore(b @ w) for b, w in zip(blocks, weights)])
    converged = False
    it = 0
    for it in range(1, max_iter + 1):
        C = np.corrcoef(Y.T) if J > 1 else np.ones((1, 1))
        E = np.zeros((J, J))
        for j in range(J):
            preds = np.where(adj[:, j] == 1)[0]
            succ = np.where(adj[j, :] == 1)[0]
            if len(preds):
                beta, *_ = np.linalg.lstsq(Y[:, preds], Y[:, j], rcond=None)
                E[j, preds] = beta
            for s in succ:
                E[j, s] = C[j, s]
            if not len(preds) and not len(succ):
                E[j, j] = 1.0
        Z = Y @ E.T
        Z = np.column_stack([zscore(Z[:, j]) for j in range(J)])
        new_w, new_Y = [], []
        for j, b in enumerate(blocks):
            w = b.T @ Z[:, j] / (n - 1)
            y = b @ w
            sd = y.std(ddof=1)
            w = w / sd if sd > 0 else w
            y = zscore(y)
            if (b * y[:, None]).sum() < 0:  # orient so the block's loadings are positive on balance
                w, y = -w, -y
            new_w.append(w)
            new_Y.append(y)
        delta = max(np.abs(nw - ow).max() for nw, ow in zip(new_w, weights))
        weights, Y = new_w, np.column_stack(new_Y)
        if delta < tol:
            converged = True
            break
    loadings = [np.array([np.corrcoef(b[:, k], Y[:, j])[0, 1] for k in range(b.shape[1])]) for j, b in enumerate(blocks)]
    return weights, Y, loadings, it, converged


def pls_paths(Y, adj):
    """OLS of each endogenous LV on its predecessors (standardized). Returns {(i, j): beta}, {j: r2}, {(i,j): f2}."""
    J = Y.shape[1]
    paths, r2, f2 = {}, {}, {}
    for j in range(J):
        preds = list(np.where(adj[:, j] == 1)[0])
        if not preds:
            continue
        beta, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(Y)), Y[:, preds]]), Y[:, j], rcond=None)
        res = Y[:, j] - np.column_stack([np.ones(len(Y)), Y[:, preds]]) @ beta
        r2j = 1 - float(res @ res) / float(((Y[:, j] - Y[:, j].mean()) ** 2).sum())
        r2[j] = r2j
        for k, i in enumerate(preds):
            paths[(i, j)] = float(beta[k + 1])
            others = [p for p in preds if p != i]
            if others:
                b2, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(Y)), Y[:, others]]), Y[:, j], rcond=None)
                r_ = Y[:, j] - np.column_stack([np.ones(len(Y)), Y[:, others]]) @ b2
                r2_ex = 1 - float(r_ @ r_) / float(((Y[:, j] - Y[:, j].mean()) ** 2).sum())
            else:
                r2_ex = 0.0
            f2[(i, j)] = (r2j - r2_ex) / (1 - r2j) if r2j < 1 else math.nan
    return paths, r2, f2


def pls(rows, a):
    model = parse_model(a.model)
    lvs = [lv for lv, _ in model]
    paths_spec = parse_paths(a.paths, lvs)
    names = [it for _, items in model for it in items]
    data, dropped = columns(rows, names)
    n = len(data)
    J = len(lvs)
    adj = np.zeros((J, J))
    for s, d in paths_spec:
        adj[lvs.index(s), lvs.index(d)] = 1
    # Cycles are not allowed in a PLS path model (recursive only).
    order, seen = [], set()

    def visit(v, stack):
        if v in stack:
            sys.exit("the structural model has a cycle; PLS path models must be recursive")
        if v in seen:
            return
        for d in np.where(adj[v] == 1)[0]:
            visit(int(d), stack | {v})
        seen.add(v)
        order.append(v)
    for v in range(J):
        visit(v, set())
    header(rows, a, f"pls {a.model} | paths {a.paths} | boot {a.boot} | seed {a.seed}")
    out("pls.n", n)
    out("pls.excluded", dropped)
    print("# estimator: basic PLS path algorithm (mode A reflective outer weights, path weighting scheme, "
          "standardized data, bootstrap percentile CIs); NOT SmartPLS: no PLSc, PLSpredict, MGA, IPMA, "
          "sign-change correction or higher-order constructs")
    pos = {it: i for i, it in enumerate(names)}
    std_all = zscore_cols(data)
    blocks = [std_all[:, [pos[it] for it in items]] for _, items in model]
    weights, Y, loadings, iters, conv = pls_fit(blocks, adj)
    out("pls.iterations", iters)
    if not conv:
        print("# WARNING: the PLS algorithm did not converge in 300 iterations; results are provisional")
    paths, r2, f2 = pls_paths(Y, adj)
    load_dict = {lv: {it: float(l) for it, l in zip(items, loadings[j])} for j, (lv, items) in enumerate(model)}
    for j, (lv, items) in enumerate(model):
        for it, w in zip(items, weights[j]):
            out(f"pls.{lv}.{it}.weight", float(w))
    lv_corr = np.corrcoef(Y.T) if J > 1 else np.eye(1)
    report_measurement("pls", model, data, load_dict, np.atleast_2d(lv_corr), "PLS construct score correlations")
    for j in r2:
        k = int(adj[:, j].sum())
        adj_r2 = 1 - (1 - r2[j]) * (n - 1) / (n - k - 1)
        out(f"pls.{lvs[j]}.r2", r2[j])
        out(f"pls.{lvs[j]}.adj_r2", adj_r2)
        print(f"# APA: {lvs[j]}: R² = {apa_num(r2[j], lead=False, dec=3)} (adjusted {apa_num(adj_r2, lead=False, dec=3)})")
    # Bootstrap the path coefficients (case resampling, re-standardized inside each sample).
    rng = np.random.default_rng(a.seed)
    keys = list(paths)
    bb = np.full((a.boot, len(keys)), math.nan)
    failed = 0
    for i in range(a.boot):
        idx = rng.integers(0, n, n)
        sample = zscore_cols(data[idx])
        bl = [sample[:, [pos[it] for it in items]] for _, items in model]
        try:
            _, Yb, _, _, _ = pls_fit(bl, adj, max_iter=100, tol=1e-6)
            pb, _, _ = pls_paths(Yb, adj)
            bb[i] = [pb[k] for k in keys]
        except (np.linalg.LinAlgError, ValueError, FloatingPointError):
            failed += 1
    if failed:
        print(f"# note: {failed} bootstrap sample(s) failed and were skipped")
    for c, (i, j) in enumerate(keys):
        kk = f"pls.path.{lvs[i]}->{lvs[j]}"
        b = paths[(i, j)]
        col = bb[:, c][~np.isnan(bb[:, c])]
        se = float(col.std(ddof=1)) if len(col) > 2 else math.nan
        t = b / se if se and se > 0 else math.nan
        p = 2 * stats.t.sf(abs(t), max(len(col) - 1, 1)) if t == t else math.nan
        lo, hi = percentile_ci(col) if len(col) > 2 else (math.nan, math.nan)
        out(f"{kk}.beta", b)
        out(f"{kk}.se", se)
        out(f"{kk}.t", t)
        out(f"{kk}.p", p)
        out(f"{kk}.ci_low", lo)
        out(f"{kk}.ci_high", hi)
        out(f"{kk}.f2", f2[(i, j)])
        size = "large" if f2[(i, j)] >= 0.35 else "medium" if f2[(i, j)] >= 0.15 else "small" if f2[(i, j)] >= 0.02 else "negligible"
        print(f"# APA: {lvs[i]} -> {lvs[j]}: β = {apa_num(b, lead=False, dec=3)}, boot SE = {apa_num(se, lead=False, dec=3)}, "
              f"t = {apa_num(t)}, {apa_p(p)}, {ci_text(lo, hi, lead=False)}, f² = {apa_num(f2[(i, j)], lead=False, dec=3)} ({size})")
    print(f"# order: path t and p use the bootstrap SE with {a.boot} resamples (t-distribution, df = resamples - 1); "
          "the percentile CI is the primary test. Paths are standardized (β)")
    print("# note: PLS composites are not latent variables: paths are slightly attenuated and loadings slightly "
          "inflated versus a covariance-based SEM of the same data; say 'PLS-SEM' in the Methods and cite the "
          "algorithm (Lohmöller 1989; Hair et al. 2022)")


# ---------------------------------------------------------------- selftest (seeded synthetic data + Hayes examples)

def _run(func, rows, **kw):
    defaults = {"csv": "<memory>", "covariates": None, "boot": 0, "seed": 1, "center": False, "no_semopy": False}
    defaults.update(kw)
    ns = argparse.Namespace(**defaults)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        func(rows, ns)
    text = buf.getvalue()
    vals = {}
    for line in text.splitlines():
        m = re.match(r"^([^#\s][^=]*?) = (.+)$", line)
        if m:
            try:
                vals[m.group(1).strip()] = float(m.group(2))
            except ValueError:
                vals[m.group(1).strip()] = m.group(2)
    return vals, text


def _rows(cols):
    n = len(next(iter(cols.values())))
    return [{k: f"{v[i]:.6f}" for k, v in cols.items()} for i in range(n)]


def selftest(a):
    rng = np.random.default_rng(20261021)
    checks = []

    def check(name, ok, detail):
        checks.append((name, bool(ok), detail))
        print(f"{'PASS' if ok else 'FAIL'} | {name} | {detail}")

    n = 300
    # 1. mediation, planted a = 0.5, b = 0.4, c' = 0.2
    X = rng.normal(size=n)
    M = 0.5 * X + rng.normal(size=n) * 0.8
    Y = 0.2 * X + 0.4 * M + rng.normal(size=n) * 0.8
    v, _ = _run(mediate, _rows({"x": X, "m": M, "y": Y}), x="x", m="m", y="y", boot=1000)
    k = "mediate.x-m-y"
    check("mediate recovers a=0.5", abs(v[f"{k}.a.b"] - 0.5) < 0.1, f"a = {v[f'{k}.a.b']:.3f}")
    check("mediate recovers b=0.4", abs(v[f"{k}.b.b"] - 0.4) < 0.1, f"b = {v[f'{k}.b.b']:.3f}")
    check("mediate indirect CI excludes 0 (planted 0.20)", v[f"{k}.indirect.ci_low"] > 0,
          f"ab = {v[f'{k}.indirect.b']:.3f}, CI [{v[f'{k}.indirect.ci_low']:.3f}, {v[f'{k}.indirect.ci_high']:.3f}]")
    # negative control: b = 0
    Y0 = 0.3 * X + rng.normal(size=n) * 0.8
    v, _ = _run(mediate, _rows({"x": X, "m": M, "y": Y0}), x="x", m="m", y="y", boot=1000)
    check("mediate negative control: indirect CI includes 0", v[f"{k}.indirect.ci_low"] < 0 < v[f"{k}.indirect.ci_high"],
          f"ab = {v[f'{k}.indirect.b']:.3f}, CI [{v[f'{k}.indirect.ci_low']:.3f}, {v[f'{k}.indirect.ci_high']:.3f}]")

    # 2. moderation, planted interaction 0.3 (centered metric)
    W = rng.normal(size=n)
    Ym = 0.4 * X + 0.2 * W + 0.3 * X * W + rng.normal(size=n) * 0.8
    v, _ = _run(moderate, _rows({"x": X, "w": W, "y": Ym}), x="x", w="w", y="y", center=True, boot=500)
    k = "moderate.x-by-w-y"
    check("moderate recovers interaction 0.3", abs(v[f"{k}.xw.b"] - 0.3) < 0.1 and v[f"{k}.xw.p"] < 0.05,
          f"b3 = {v[f'{k}.xw.b']:.3f}, p = {v[f'{k}.xw.p']:.4f}")
    check("moderate simple slopes ordered low < high", v[f"{k}.slope.low.b"] < v[f"{k}.slope.high.b"],
          f"low {v[f'{k}.slope.low.b']:.3f} mean {v[f'{k}.slope.mean.b']:.3f} high {v[f'{k}.slope.high.b']:.3f}")
    Ym0 = 0.4 * X + 0.2 * W + rng.normal(size=n) * 0.8
    v, _ = _run(moderate, _rows({"x": X, "w": W, "y": Ym0}), x="x", w="w", y="y", center=True)
    check("moderate negative control: interaction CI includes 0", v[f"{k}.xw.ci_low"] < 0 < v[f"{k}.xw.ci_high"],
          f"b3 = {v[f'{k}.xw.b']:.3f}, CI [{v[f'{k}.xw.ci_low']:.3f}, {v[f'{k}.xw.ci_high']:.3f}]")

    # 3. CFA / reliability: two factors (r = .3), loadings .80/.75/.70 and .85/.80/.75; one junk construct
    n2 = 1000
    F1 = rng.normal(size=n2)
    F2 = 0.3 * F1 + math.sqrt(1 - 0.09) * rng.normal(size=n2)
    cols = {}
    for name, F, lams in (("A", F1, (0.80, 0.75, 0.70)), ("B", F2, (0.85, 0.80, 0.75))):
        for i, l in enumerate(lams, 1):
            cols[f"{name.lower()}{i}"] = l * F + math.sqrt(1 - l * l) * rng.normal(size=n2)
    for i in range(1, 4):
        cols[f"z{i}"] = rng.normal(size=n2)
    rows3 = _rows(cols)
    for mode in ("semopy", "approx"):
        v, txt = _run(cfa, rows3, model="A = a1 a2 a3; B = b1 b2 b3; Z = z1 z2 z3", no_semopy=(mode == "approx"))
        if mode == "semopy" and "semopy not installed" in txt:
            print("SKIP | cfa semopy path | semopy not installed; approximation path tested instead")
            continue
        got = [v[f"cfa.A.a{i}.loading"] for i in (1, 2, 3)] + [v[f"cfa.B.b{i}.loading"] for i in (1, 2, 3)]
        want = [0.80, 0.75, 0.70, 0.85, 0.80, 0.75]
        err = max(abs(g - w) for g, w in zip(got, want))
        check(f"cfa ({mode}) loadings within .10 of planted", err < 0.10,
              "got " + " ".join(f"{g:.2f}" for g in got) + f" (max error {err:.3f})")
        check(f"cfa ({mode}) A and B: CR > .70, AVE > .50", all(v[f"cfa.{c}.cr"] > 0.7 and v[f"cfa.{c}.ave"] > 0.5 for c in "AB"),
              f"CR A {v['cfa.A.cr']:.3f} B {v['cfa.B.cr']:.3f}; AVE A {v['cfa.A.ave']:.3f} B {v['cfa.B.ave']:.3f}")
        check(f"cfa ({mode}) negative control: junk construct Z flagged", v["cfa.Z.ave"] < 0.5 and v["cfa.Z.cr"] < 0.7,
              f"Z: alpha {v['cfa.Z.alpha']:.3f} CR {v['cfa.Z.cr']:.3f} AVE {v['cfa.Z.ave']:.3f}")
        check(f"cfa ({mode}) HTMT A-B below .85, construct r near .3", v["cfa.htmt.B-A"] < 0.85 and abs(v["cfa.fl.B-A.r"] - 0.3) < 0.12,
              f"HTMT {v['cfa.htmt.B-A']:.3f}, r {v['cfa.fl.B-A.r']:.3f}")
        if mode == "semopy":
            check("cfa (semopy) fit indices present and CFI > .90", "cfa.fit.cfi" in v and v["cfa.fit.cfi"] > 0.9,
                  f"chi2({v.get('cfa.fit.df')}) = {v.get('cfa.fit.chi2')}, CFI {v.get('cfa.fit.cfi')}, RMSEA {v.get('cfa.fit.rmsea')}, SRMR {v.get('cfa.fit.srmr')}")

    # 4. PLS: Yl = 0.5 A + 0.3 B + e, with reflective indicators (loadings .85); negative control: C -> Y = 0
    n4 = 1000
    A_ = rng.normal(size=n4)
    B_ = 0.3 * A_ + math.sqrt(0.91) * rng.normal(size=n4)
    C_ = rng.normal(size=n4)
    Yl = 0.5 * A_ + 0.3 * B_ + math.sqrt(1 - 0.43) * rng.normal(size=n4)
    cols = {}
    for name, F in (("a", A_), ("b", B_), ("c", C_), ("y", Yl)):
        for i in range(1, 4):
            cols[f"{name}{i}"] = 0.85 * F + math.sqrt(1 - 0.85 ** 2) * rng.normal(size=n4)
    v, _ = _run(pls, _rows(cols), model="A = a1 a2 a3; B = b1 b2 b3; C = c1 c2 c3; Y = y1 y2 y3",
                paths="A->Y; B->Y; C->Y", boot=300)
    pa, pb, pc = v["pls.path.A->Y.beta"], v["pls.path.B->Y.beta"], v["pls.path.C->Y.beta"]
    check("pls recovers A->Y (0.5) and B->Y (0.3) within .10 (composite attenuation expected)",
          abs(pa - 0.5) < 0.10 and abs(pb - 0.3) < 0.10, f"A->Y {pa:.3f}, B->Y {pb:.3f}")
    check("pls A->Y and B->Y bootstrap CIs exclude 0", v["pls.path.A->Y.ci_low"] > 0 and v["pls.path.B->Y.ci_low"] > 0,
          f"A->Y CI [{v['pls.path.A->Y.ci_low']:.3f}, {v['pls.path.A->Y.ci_high']:.3f}], "
          f"B->Y CI [{v['pls.path.B->Y.ci_low']:.3f}, {v['pls.path.B->Y.ci_high']:.3f}]")
    check("pls negative control: C->Y (planted 0) CI includes 0", v["pls.path.C->Y.ci_low"] < 0 < v["pls.path.C->Y.ci_high"],
          f"C->Y {pc:.3f}, CI [{v['pls.path.C->Y.ci_low']:.3f}, {v['pls.path.C->Y.ci_high']:.3f}]")
    check("pls outer loadings near .85 and R2(Y) near .43", abs(v["pls.Y.y1.loading"] - 0.85) < 0.08 and abs(v["pls.Y.r2"] - 0.43) < 0.12,
          f"loading y1 {v['pls.Y.y1.loading']:.3f}, R2 {v['pls.Y.r2']:.3f}")

    # 5. Published examples (Hayes 2018, Introduction to Mediation, Moderation, and Conditional Process Analysis, 2nd ed.)
    if a.pmi:
        rows = load(a.pmi)
        v, _ = _run(mediate, rows, x="cond", m="pmi", y="reaction", boot=5000, seed=1)
        k = "mediate.cond-pmi-reaction"
        pub = {"a.b": 0.4765, "b.b": 0.5064, "cprime.b": 0.2544, "c.b": 0.4957, "indirect.b": 0.2413}
        got = {p: v[f"{k}.{p}"] for p in pub}
        ok = all(abs(got[p] - pub[p]) < 0.001 for p in pub)
        check("Hayes ch.3 PROCESS Model 4 (pmi: cond -> pmi -> reaction) point estimates match to 3 dp", ok,
              "; ".join(f"{p} got {got[p]:.4f} vs published {pub[p]:.4f}" for p in pub)
              + f"; boot CI [{v[f'{k}.indirect.ci_low']:.4f}, {v[f'{k}.indirect.ci_high']:.4f}] vs published [.0070, .5260] (resampling varies)")
    if a.disaster:
        rows = load(a.disaster)
        v, _ = _run(moderate, rows, x="frame", w="skeptic", y="justify")
        k = "moderate.frame-by-skeptic-justify"
        pub = {"x.b": -0.5625, "w.b": 0.1051, "xw.b": 0.2012, "constant.b": 2.4515}
        got = {p: v[f"{k}.{p}"] for p in pub}
        ok = all(abs(got[p] - pub[p]) < 0.001 for p in pub)
        check("Hayes ch.7 PROCESS Model 1 (disaster: frame x skeptic -> justify) coefficients match to 3 dp", ok,
              "; ".join(f"{p} got {got[p]:.4f} vs published {pub[p]:.4f}" for p in pub))
        jn = v.get(f"{k}.jn.boundary1", math.nan)
        check("Hayes ch.7 Johnson-Neyman transition point 1.171", abs(jn - 1.1713) < 0.002, f"JN boundary got {jn:.4f} vs published 1.1713")
    bad = [c for c in checks if not c[1]]
    print(f"RESULT: {'PASS' if not bad else 'FAIL'} ({len(checks) - len(bad)}/{len(checks)} checks passed"
          + (f"; failed: {', '.join(c[0] for c in bad)}" if bad else "") + ")")
    print("# not checked: covariate paths against a published result (they run, see --covariates), non-normal data, "
          "missing-data patterns beyond listwise deletion, mode B / formative PLS, moderated mediation (PROCESS 7/14)")
    sys.exit(1 if bad else 0)


# ---------------------------------------------------------------- CLI

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        sp = argparse.ArgumentParser(prog="analyze_sem.py selftest",
                                     description="seeded synthetic checks for every command (+ Hayes examples when given)",
                                     epilog="example: analyze_sem.py selftest --pmi pmi.csv --disaster disaster.csv")
        sp.add_argument("--pmi", help="Hayes pmi.csv (cond, pmi, reaction) to compare with the published Model 4 output")
        sp.add_argument("--disaster", help="Hayes disaster.csv (frame, skeptic, justify) to compare with the published Model 1 output")
        selftest(sp.parse_args(sys.argv[2:]))
        return
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="self-test: analyze_sem.py selftest [--pmi pmi.csv] [--disaster disaster.csv]")
    ap.add_argument("csv", help="the user's data file (CSV; ',', ';' or tab separated)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, boot_default):
        p.add_argument("--boot", type=int, default=boot_default, help=f"bootstrap resamples (default {boot_default})")
        p.add_argument("--seed", type=int, default=1, help="random seed for the bootstrap (default 1)")

    p = sub.add_parser("mediate", help="simple mediation X -> M -> Y (PROCESS Model 4) with bootstrap CI",
                       epilog="example: analyze_sem.py data.csv mediate --x cond --m pmi --y reaction --boot 5000")
    p.add_argument("--x", required=True)
    p.add_argument("--m", required=True)
    p.add_argument("--y", required=True)
    p.add_argument("--covariates", nargs="*", help="covariates in both equations")
    common(p, 5000)
    p.set_defaults(func=mediate)

    p = sub.add_parser("moderate", help="moderation X x W -> Y (PROCESS Model 1): simple slopes + Johnson-Neyman",
                       epilog="example: analyze_sem.py data.csv moderate --x frame --w skeptic --y justify --center")
    p.add_argument("--x", required=True)
    p.add_argument("--w", required=True)
    p.add_argument("--y", required=True)
    p.add_argument("--covariates", nargs="*")
    p.add_argument("--center", action="store_true", help="mean-center X and W before forming the product")
    common(p, 0)
    p.set_defaults(func=moderate)

    p = sub.add_parser("cfa", help="CFA (semopy) or labelled approximation; alpha, CR, AVE, Fornell-Larcker, HTMT",
                       epilog='example: analyze_sem.py data.csv cfa --model "Stress = q1 q2 q3; Sleep = q4 q5 q6"')
    p.add_argument("--model", required=True, help='"LV1 = q1 q2 q3; LV2 = q4 q5 q6"')
    p.add_argument("--no-semopy", action="store_true", help="force the numpy approximation even if semopy is installed")
    p.set_defaults(func=cfa)

    p = sub.add_parser("pls", help="basic PLS-SEM: paths with bootstrap t/p/CI, R2, f2, loadings, CR/AVE/HTMT",
                       epilog='example: analyze_sem.py data.csv pls --model "A = a1 a2 a3; Y = y1 y2" --paths "A->Y" --boot 1000')
    p.add_argument("--model", required=True)
    p.add_argument("--paths", required=True, help='"LV1->Y; LV2->Y"')
    common(p, 1000)
    p.set_defaults(func=pls)

    a = ap.parse_args()
    rows = load(a.csv)
    a.func(rows, a)


if __name__ == "__main__":
    main()
