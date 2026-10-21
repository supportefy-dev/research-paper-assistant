#!/usr/bin/env python3
"""analyze.py - common statistics on the user's own CSV, written as evidence.

Every result is printed as one `analysis.variable.label = value` line, which is
the format `scholar.py numbers` checks a Results section against. A line
starting with '# APA:' gives the ready-to-paste APA string. Needs numpy and
scipy only (pandas is not required).

Usage (append each run to the evidence file):
  python -X utf8 analyze.py data.csv describe gpa sleep_hours        >> analysis/output.txt
  python -X utf8 analyze.py data.csv freq gender                     >> analysis/output.txt
  python -X utf8 analyze.py data.csv corr sleep_hours gpa [--spearman]
  python -X utf8 analyze.py data.csv regress gpa sleep_hours stress --diagnostics   (first variable = outcome)
  python -X utf8 analyze.py data.csv ttest gpa --by gender            (Welch t, Cohen's d, mean diff + CI, Levene)
  python -X utf8 analyze.py data.csv anova gpa --by faculty           (one-way, eta squared)
  python -X utf8 analyze.py data.csv alpha q1 q2 q3 q4 --composite stress   (Cronbach's alpha + composite check)
  python -X utf8 analyze.py data.csv describe stress --range 1 5      (warns on out-of-range values)
Evidence keys end with the statistic symbol (corr.x~y.r, regress.gpa.sleep.beta) because
scholar.py numbers reads the LAST segment of a key as its label.
Missing or non-numeric cells are dropped listwise per analysis; n is always reported.
"""

import argparse
import csv
import math
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
        x = float(str(v).strip().replace(",", ".")) if str(v).strip() != "" else math.nan
    except ValueError:
        return math.nan
    return x


def columns(rows, names):
    missing = [n for n in names if n not in rows[0]]
    if missing:
        sys.exit(f"unknown column(s): {', '.join(missing)}. Available: {', '.join(rows[0].keys())}")
    m = np.array([[num(r[n]) for n in names] for r in rows], dtype=float)
    keep = ~np.isnan(m).any(axis=1)
    return m[keep], int((~keep).sum())


def out(key, value):
    if isinstance(value, float):
        value = f"{value:.6g}" if abs(value) < 1e-4 and value != 0 else f"{value:.6f}".rstrip("0").rstrip(".")
    print(f"{key} = {value}")


def apa_num(x, lead=True, dec=2):
    s = f"{x:.{dec}f}"
    if not lead:
        s = s.replace("0.", ".", 1) if s.startswith(("0.", "-0.")) else s
    return s


def apa_p(p):
    return "p < .001" if p < 0.001 else f"p = {apa_num(p, lead=False, dec=3)}"


def describe(rows, a):
    for v in a.vars:
        x, dropped = columns(rows, [v])
        x = x[:, 0]
        k = f"describe.{v}"
        out(f"{k}.n", len(x))
        out(f"{k}.m", float(np.mean(x)))
        out(f"{k}.sd", float(np.std(x, ddof=1)))
        out(f"{k}.min", float(np.min(x)))
        out(f"{k}.max", float(np.max(x)))
        out(f"{k}.median", float(np.median(x)))
        out(f"{k}.skew", float(stats.skew(x)))
        out(f"{k}.kurtosis", float(stats.kurtosis(x)))
        out(f"{k}.excluded", dropped)
        print(f"# APA: {v}: M = {apa_num(np.mean(x))}, SD = {apa_num(np.std(x, ddof=1))}, n = {len(x)}")
        if a.range:
            lo, hi = a.range
            bad = int(((x < lo) | (x > hi)).sum())
            if bad:
                print(f"# WARNING: {bad} value(s) of {v} fall outside the valid range {lo}-{hi}: check data entry")


def freq(rows, a):
    for v in a.vars:
        vals = [str(r[v]).strip() for r in rows if str(r.get(v, "")).strip() != ""]
        total = len(vals)
        out(f"freq.{v}.n", total)
        for level in sorted(set(vals)):
            c = vals.count(level)
            out(f"freq.{v}.{level}.n", c)
            out(f"freq.{v}.{level}.pct", 100 * c / total)
            print(f"# APA: {level}: n = {c} ({100 * c / total:.1f}%)")


def corr(rows, a):
    if len(a.vars) != 2:
        sys.exit("corr needs exactly two variables")
    m, dropped = columns(rows, a.vars)
    x, y = m[:, 0], m[:, 1]
    n = len(x)
    k = f"corr.{a.vars[0]}~{a.vars[1]}"
    if a.spearman:
        rho, p = stats.spearmanr(x, y)
        out(f"{k}.rho", float(rho))
        out(f"{k}.p", float(p))
        out(f"{k}.n", n)
        print(f"# APA: rs({n - 2}) = {apa_num(rho, lead=False)}, {apa_p(p)}")
        return
    r, p = stats.pearsonr(x, y)
    z, se = math.atanh(r), 1 / math.sqrt(n - 3)
    lo, hi = math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)
    out(f"{k}.r", float(r))
    out(f"{k}.df", n - 2)
    out(f"{k}.p", float(p))
    out(f"{k}.ci_low", lo)
    out(f"{k}.ci_high", hi)
    out(f"{k}.n", n)
    out(f"{k}.excluded", dropped)
    print(f"# APA: r({n - 2}) = {apa_num(r, lead=False)}, {apa_p(p)}, 95% CI "
          f"[{apa_num(lo, lead=False)}, {apa_num(hi, lead=False)}]")


def regress(rows, a):
    if len(a.vars) < 2:
        sys.exit("regress needs an outcome and at least one predictor")
    m, dropped = columns(rows, a.vars)
    y, X = m[:, 0], m[:, 1:]
    n, p_ = X.shape
    D = np.column_stack([np.ones(n), X])
    coef, *_ = np.linalg.lstsq(D, y, rcond=None)
    resid = y - D @ coef
    dfe = n - p_ - 1
    sse = float(resid @ resid)
    sst = float(((y - y.mean()) ** 2).sum())
    sigma2 = sse / dfe
    cov = sigma2 * np.linalg.inv(D.T @ D)
    se = np.sqrt(np.diag(cov))
    t = coef / se
    pv = 2 * stats.t.sf(np.abs(t), dfe)
    tcrit = stats.t.ppf(0.975, dfe)
    r2 = 1 - sse / sst
    adj = 1 - (1 - r2) * (n - 1) / dfe
    F = (r2 / p_) / ((1 - r2) / dfe)
    pF = stats.f.sf(F, p_, dfe)
    k = f"regress.{a.vars[0]}"
    out(f"{k}.n", n)
    out(f"{k}.excluded", dropped)
    out(f"{k}.r2", r2)
    out(f"{k}.adj_r2", adj)
    out(f"{k}.f", float(F))
    out(f"{k}.df1", p_)
    out(f"{k}.df2", dfe)
    out(f"{k}.p", float(pF))
    print(f"# APA: R² = {apa_num(r2, lead=False)}, F({p_}, {dfe}) = {apa_num(F)}, {apa_p(pF)}")
    sy = float(np.std(y, ddof=1))
    for i, name in enumerate(["intercept"] + a.vars[1:]):
        kk = f"{k}.{name}"
        out(f"{kk}.b", float(coef[i]))
        out(f"{kk}.se", float(se[i]))
        out(f"{kk}.t", float(t[i]))
        out(f"{kk}.p", float(pv[i]))
        out(f"{kk}.ci_low", float(coef[i] - tcrit * se[i]))
        out(f"{kk}.ci_high", float(coef[i] + tcrit * se[i]))
        if i:
            beta = float(coef[i] * np.std(X[:, i - 1], ddof=1) / sy)
            out(f"{kk}.beta", beta)
            print(f"# APA: {name}: B = {apa_num(coef[i])}, SE = {apa_num(se[i])}, β = {apa_num(beta, lead=False)}, "
                  f"t({dfe}) = {apa_num(t[i])}, {apa_p(pv[i])}, 95% CI [{apa_num(coef[i] - tcrit * se[i])}, "
                  f"{apa_num(coef[i] + tcrit * se[i])}]")
    if p_ > 1:
        for i, name in enumerate(a.vars[1:]):
            others = np.delete(X, i, axis=1)
            Do = np.column_stack([np.ones(n), others])
            fit, *_ = np.linalg.lstsq(Do, X[:, i], rcond=None)
            res = X[:, i] - Do @ fit
            r2i = 1 - float(res @ res) / float(((X[:, i] - X[:, i].mean()) ** 2).sum())
            out(f"{k}.{name}.vif", 1 / (1 - r2i) if r2i < 1 else math.inf)
            # Squared semipartial: R2 lost when this predictor is dropped.
            fit_y, *_ = np.linalg.lstsq(Do, y, rcond=None)
            ry = y - Do @ fit_y
            out(f"{k}.{name}.sr2", r2 - (1 - float(ry @ ry) / sst))
    if a.diagnostics:
        h = np.diag(D @ np.linalg.inv(D.T @ D) @ D.T)
        std_res = resid / np.sqrt(sigma2 * (1 - h))
        cooks = (std_res ** 2 / (p_ + 1)) * h / (1 - h)
        w, pw = stats.shapiro(resid) if 3 <= n <= 5000 else (math.nan, math.nan)
        # Koenker's studentised Breusch-Pagan: n * R2 of squared residuals on the predictors.
        e2 = resid ** 2
        g, *_ = np.linalg.lstsq(D, e2, rcond=None)
        r2bp = 1 - float(((e2 - D @ g) ** 2).sum()) / float(((e2 - e2.mean()) ** 2).sum())
        bp = n * r2bp
        pbp = stats.chi2.sf(bp, p_)
        out(f"{k}.resid.shapiro.w", float(w))
        out(f"{k}.resid.shapiro.p", float(pw))
        out(f"{k}.breusch_pagan.bp", bp)
        out(f"{k}.breusch_pagan.df", p_)
        out(f"{k}.breusch_pagan.p", float(pbp))
        out(f"{k}.max_cooks_d", float(cooks.max()))
        out(f"{k}.cooks_d_over_4n", int((cooks > 4 / n).sum()))
        out(f"{k}.std_resid_over_3", int((np.abs(std_res) > 3).sum()))
        print(f"# APA: residual normality W = {apa_num(w, dec=3)}, {apa_p(pw)}; Breusch-Pagan χ²({p_}) = "
              f"{apa_num(bp)}, {apa_p(pbp)}; max Cook's D = {apa_num(cooks.max(), dec=3)}; "
              f"{int((np.abs(std_res) > 3).sum())} standardised residual(s) beyond ±3")


def groups(rows, a):
    if len(a.vars) != 1 or not a.by:
        sys.exit("needs one outcome variable and --by <group column>")
    v = a.vars[0]
    g = {}
    for r in rows:
        x, lab = num(r.get(v)), str(r.get(a.by, "")).strip()
        if lab and not math.isnan(x):
            g.setdefault(lab, []).append(x)
    return v, {k: np.array(x) for k, x in sorted(g.items())}


def ttest(rows, a):
    v, g = groups(rows, a)
    if len(g) != 2:
        sys.exit(f"ttest needs exactly 2 groups in {a.by}, found {len(g)}: {', '.join(g)}")
    (l1, x1), (l2, x2) = g.items()
    t, p = stats.ttest_ind(x1, x2, equal_var=False)
    v1, v2, n1, n2 = x1.var(ddof=1), x2.var(ddof=1), len(x1), len(x2)
    df = (v1 / n1 + v2 / n2) ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1))
    sp = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    d = (x1.mean() - x2.mean()) / sp
    k = f"ttest.{v}.by_{a.by}"
    for lab, x in g.items():
        out(f"{k}.{lab}.n", len(x))
        out(f"{k}.{lab}.m", float(x.mean()))
        out(f"{k}.{lab}.sd", float(x.std(ddof=1)))
    diff = x1.mean() - x2.mean()
    se_d = math.sqrt(v1 / n1 + v2 / n2)
    tc = stats.t.ppf(0.975, df)
    lev, plev = stats.levene(x1, x2)
    out(f"{k}.t", float(t))
    out(f"{k}.df", float(df))
    out(f"{k}.p", float(p))
    out(f"{k}.d", float(d))
    out(f"{k}.mean_diff", float(diff))
    out(f"{k}.diff.ci_low", float(diff - tc * se_d))
    out(f"{k}.diff.ci_high", float(diff + tc * se_d))
    out(f"{k}.levene.f", float(lev))
    out(f"{k}.levene.p", float(plev))
    print(f"# order: differences are {l1} minus {l2} (alphabetical); swap the sign if you report {l2} minus {l1}")
    print(f"# APA: {l1} (M = {apa_num(x1.mean())}, SD = {apa_num(x1.std(ddof=1))}) vs {l2} (M = {apa_num(x2.mean())}, "
          f"SD = {apa_num(x2.std(ddof=1))}), t({df:.2f}) = {apa_num(t)}, {apa_p(p)}, d = {apa_num(d)}, "
          f"mean difference = {apa_num(diff)}, 95% CI [{apa_num(diff - tc * se_d)}, {apa_num(diff + tc * se_d)}]")


def anova(rows, a):
    v, g = groups(rows, a)
    if len(g) < 2:
        sys.exit("anova needs at least 2 groups")
    F, p = stats.f_oneway(*g.values())
    allx = np.concatenate(list(g.values()))
    ssb = sum(len(x) * (x.mean() - allx.mean()) ** 2 for x in g.values())
    sst = float(((allx - allx.mean()) ** 2).sum())
    dfb, dfw = len(g) - 1, len(allx) - len(g)
    k = f"anova.{v}.by_{a.by}"
    for lab, x in g.items():
        out(f"{k}.{lab}.n", len(x))
        out(f"{k}.{lab}.m", float(x.mean()))
        out(f"{k}.{lab}.sd", float(x.std(ddof=1)))
    out(f"{k}.f", float(F))
    out(f"{k}.df_between", dfb)
    out(f"{k}.df_within", dfw)
    out(f"{k}.p", float(p))
    out(f"{k}.eta2", ssb / sst)
    print(f"# APA: F({dfb}, {dfw}) = {apa_num(F)}, {apa_p(p)}, η² = {apa_num(ssb / sst, lead=False)}")


def alpha(rows, a):
    m, dropped = columns(rows, a.vars)
    kitems = m.shape[1]
    if kitems < 2:
        sys.exit("alpha needs at least 2 items")
    item_var = m.var(axis=0, ddof=1).sum()
    total_var = m.sum(axis=1).var(ddof=1)
    al = kitems / (kitems - 1) * (1 - item_var / total_var)
    k = "alpha." + "_".join(a.vars[:2]) + ("_etc" if kitems > 2 else "")
    out(f"{k}.alpha", float(al))
    out(f"{k}.items", kitems)
    out(f"{k}.n", m.shape[0])
    print(f"# APA: Cronbach's α = {apa_num(al, lead=False)} ({kitems} items, n = {m.shape[0]})")
    if a.composite:
        comp, _ = columns(rows, a.vars + [a.composite])
        mean_items = comp[:, :-1].mean(axis=1)
        gap = float(np.abs(mean_items - comp[:, -1]).max())
        out(f"{k}.composite_max_gap", gap)
        if gap > 0.01:
            print(f"# WARNING: column '{a.composite}' differs from the mean of the items by up to {gap:.2f}: "
                  "it is not the item mean (different items, weights or reverse-coding). Say how it was built")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("analysis", choices=["describe", "freq", "corr", "regress", "ttest", "anova", "alpha"])
    ap.add_argument("vars", nargs="+")
    ap.add_argument("--by", help="group column for ttest / anova")
    ap.add_argument("--spearman", action="store_true")
    ap.add_argument("--diagnostics", action="store_true",
                    help="regress: residual normality, Breusch-Pagan, Cook's D, standardised residuals")
    ap.add_argument("--range", nargs=2, type=float, metavar=("LO", "HI"), help="describe: warn on values outside LO-HI")
    ap.add_argument("--composite", help="alpha: check this column equals the mean of the items")
    a = ap.parse_args()
    rows = load(a.csv)
    print(f"# {a.analysis} {' '.join(a.vars)}{' by ' + a.by if a.by else ''} | file {a.csv} | rows {len(rows)}")
    globals()[a.analysis](rows, a)


if __name__ == "__main__":
    main()
