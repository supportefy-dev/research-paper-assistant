#!/usr/bin/env python3
"""deliverables.py - one study, five outputs, one set of numbers.

Companion to references/deliverables.md (templates for the conference abstract,
the Arabic policy brief, the LinkedIn post, the 3-minute lay summary and the
visual abstract). The script does the two things a human cannot be trusted to
do by eye: it draws the visual abstract ONLY from analysis output, and it checks
that every number in a derived text exists in that output.

Commands
  visual    draw a self-contained SVG visual abstract from labelled evidence lines
  check     every number in an abstract / brief / post / lay summary must be in the evidence
  selftest  positive case + negative controls on synthetic evidence

Examples
  python -X utf8 deliverables.py visual --evidence analysis/output.txt \
      --labels "corr.sleep~gpa.r:Sleep and GPA" "regress.gpa.sleep.beta:Sleep, GPA regression" \
      --title "More sleep, higher GPA among 199 students" --out visual_abstract.svg
  python -X utf8 deliverables.py visual --evidence analysis/output.txt --lang ar \
      --labels "corr.sleep~gpa.r:النوم والمعدل التراكمي" --title "نوم أكثر، معدل أعلى" --out visual_ar.svg
  python -X utf8 deliverables.py check brief.md --evidence analysis/output.txt --kind brief
  python -X utf8 deliverables.py selftest

A label whose key is not in the evidence file is refused and nothing is written.
"""

import argparse
import difflib
import os
import re
import sys
import tempfile
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scholar import (numbers_in_text, evidence_numbers, number_supported, canon_label,  # noqa: E402
                     table, clean, short, ARABIC_RE, ARABIC_DIGITS, EN_EM, TODAY)

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# ---------------------------------------------------------------- evidence

EVIDENCE_LINE = re.compile(r"^\s*([^#=\s][^=]*?)\s*=\s*(-?(?:\d+\.\d+|\.\d+|\d+)(?:[eE][-+]?\d+)?)\s*$")


def load_evidence(path):
    """'key.path.label = value' lines -> ordered {key: float}. Comment and APA lines are skipped."""
    ev = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = EVIDENCE_LINE.match(line.translate(ARABIC_DIGITS))
            if m:
                ev[m.group(1).strip()] = float(m.group(2))
    return ev


# Symbol shown before the value on a card, by canonical label (scholar.canon_label).
SYMBOL = {
    "r": "r", "rho": "ρ", "beta": "β", "b": "B", "se": "SE", "t": "t", "z": "z", "f": "F", "p": "p",
    "df": "df", "m": "M", "sd": "SD", "n": "n", "d": "d", "alpha": "α", "r2": "R²", "adj_r2": "adj. R²",
    "eta2": "η²", "chi2": "χ²", "ci": "95% CI", "median": "Mdn", "vif": "VIF", "u": "U", "h": "H",
    "w": "W", "or": "OR", "min": "min", "max": "max", "diff": "diff", "skew": "skew", "kurtosis": "kurtosis",
}
NO_LEADING_ZERO = {"r", "rho", "beta", "p", "alpha", "r2", "adj_r2", "eta2"}   # APA: cannot exceed 1
INTEGER_LABELS = {"n", "df"}


def fmt_value(key, value, lang="en", decimals=2):
    """APA-style text for one evidence value: 'r = .31', 'p < .001', 'n = 199', '55%'.

    English drops the leading zero for statistics bounded by 1 (APA 7); Arabic keeps it
    (0.31), as Arab universities expect and as writing-style.md says.
    """
    last = key.split(".")[-1]
    lab = canon_label(last) or last.lower()
    if last.lower() in ("pct", "percent") or lab == "pct":
        s = f"{value:.{max(decimals - 1, 0)}f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))
        return s + "%", "pct"
    if lab == "p":
        if value < 0.001:
            txt = "< .001" if lang == "en" else "< 0.001"
        else:
            txt = f"{value:.3f}"
            txt = "= " + (txt[1:] if lang == "en" and txt.startswith("0") else txt)
        return f"p {txt}", "p"
    if lab in INTEGER_LABELS and float(value).is_integer():
        return f"{SYMBOL.get(lab, last)} = {int(value)}", lab
    num = f"{value:.{decimals}f}"
    if lab in NO_LEADING_ZERO and lang == "en":
        num = re.sub(r"^(-?)0\.", r"\1.", num)
    return f"{SYMBOL.get(lab, last)} = {num}", lab


# ---------------------------------------------------------------- text helpers for the SVG

def is_arabic(s):
    return bool(ARABIC_RE.search(s or ""))


def wrap(text, max_chars):
    """Greedy word wrap on character count (SVG has no automatic wrapping)."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def text_el(x, y, s, size, weight="normal", fill="#1A1A1A", anchor="start", rtl=False, extra=""):
    direction = ' direction="rtl" unicode-bidi="embed"' if rtl else ' direction="ltr"'
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}"{direction}{extra}>{escape(s)}</text>')


UI = {
    "en": {"source": "Source", "evidence": "Numbers from", "n": "n", "design": "Design"},
    "ar": {"source": "المصدر", "evidence": "الأرقام من", "n": "العينة", "design": "التصميم"},
}


def draw_svg(title, cards, lang, subtitle="", source="", evidence_name="analysis/output.txt",
             accent="#1F5F8B", width=1200, height=675):
    """cards: list of dicts {caption, value_text, key, n}. Up to 4, laid out in one row."""
    rtl = lang == "ar"
    ui = UI["ar" if rtl else "en"]
    margin = 60
    font = "Segoe UI, Tahoma, Arial, Helvetica, Noto Naskh Arabic, sans-serif"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" xml:lang="{"ar" if rtl else "en"}"'
           + (' direction="rtl"' if rtl else "") + ">",
           f"<title>{escape(title)}</title>",
           f'<style>text{{font-family:{font}}}</style>',
           f'<rect width="{width}" height="{height}" fill="#FFFFFF"/>',
           f'<rect x="0" y="0" width="{width}" height="14" fill="{accent}"/>']
    x_text = width - margin if rtl else margin
    anchor = "end" if rtl else "start"
    y = 80
    for line in wrap(title, 44)[:2]:
        out.append(text_el(x_text, y, line, 40, "bold", "#1A1A1A", anchor, rtl))
        y += 50
    if subtitle:
        for line in wrap(subtitle, 80)[:2]:
            out.append(text_el(x_text, y, line, 22, "normal", "#5B6470", anchor, rtl))
            y += 30
    # Cards
    n = len(cards)
    gap = 24
    top = y + 20
    card_h = 300
    card_w = (width - 2 * margin - gap * (n - 1)) / n
    order = list(range(n))
    for i, c in zip(order, cards):
        cx = margin + i * (card_w + gap)
        if rtl:
            cx = width - margin - card_w - i * (card_w + gap)
        out.append(f'<rect x="{cx:.0f}" y="{top}" width="{card_w:.0f}" height="{card_h}" rx="16" fill="#F3F6F9"/>')
        out.append(f'<rect x="{cx:.0f}" y="{top}" width="8" height="{card_h}" rx="4" fill="{accent}"/>')
        mid = cx + card_w / 2
        big = 56 if n <= 2 else (48 if n == 3 else 40)
        # The statistic is always LTR, even on an Arabic card.
        out.append(text_el(f"{mid:.0f}", top + 110, c["value_text"], big, "bold", accent, "middle", False))
        cy = top + 165
        for line in wrap(c["caption"], 26 if n == 4 else 30)[:3]:
            out.append(text_el(f"{mid:.0f}", cy, line, 22, "normal", "#1A1A1A", "middle", rtl))
            cy += 28
        foot = top + card_h - 40
        if c.get("n") is not None:
            nn = int(c["n"]) if float(c["n"]).is_integer() else c["n"]
            out.append(text_el(f"{mid:.0f}", foot, f"{ui['n']} = {nn}", 18, "normal", "#5B6470", "middle", rtl))
            foot += 24
        out.append(text_el(f"{mid:.0f}", foot, c["key"], 14, "normal", "#8A94A0", "middle", False,
                           ' font-family="Consolas, Courier New, monospace"'))
    # Footer
    fy = height - 56
    out.append(f'<line x1="{margin}" y1="{fy - 30}" x2="{width - margin}" y2="{fy - 30}" stroke="#D9DEE3"/>')
    if source:
        for line in wrap(f"{ui['source']}: {source}", 110)[:2]:
            out.append(text_el(x_text, fy, line, 18, "normal", "#5B6470", anchor, rtl))
            fy += 24
    out.append(text_el(x_text, fy, f"{ui['evidence']}: {evidence_name} ({TODAY})", 16, "normal", "#8A94A0",
                       anchor, rtl))
    out.append("</svg>")
    return "\n".join(out)


def sibling_n(ev, key):
    """'corr.sleep~gpa.r' -> value of 'corr.sleep~gpa.n' if present (the card shows the sample size)."""
    base = key.rsplit(".", 1)[0]
    for cand in (base + ".n", base.rsplit(".", 1)[0] + ".n" if "." in base else None):
        if cand and cand in ev:
            return ev[cand]
    return None


def cmd_visual(a):
    if not os.path.exists(a.evidence):
        print(f"evidence file not found: {a.evidence}")
        return 1
    ev = load_evidence(a.evidence)
    if not ev:
        print(f"no 'key = value' lines in {a.evidence}: run analyze.py first (see module-contract.md)")
        return 1
    if len(a.labels) > 4:
        print(f"REFUSED: {len(a.labels)} labels given; a visual abstract carries at most 4 key statistics.")
        return 1
    cards, refused = [], []
    for spec in a.labels:
        key, _, caption = spec.partition(":")
        key, caption = key.strip(), caption.strip() or key.strip()
        if key not in ev:
            near = difflib.get_close_matches(key, list(ev), n=3, cutoff=0.5)
            refused.append((key, near))
            continue
        value_text, lab = fmt_value(key, ev[key], a.lang, a.decimals)
        cards.append({"caption": caption, "value_text": value_text, "key": key, "value": ev[key],
                      "n": sibling_n(ev, key) if a.show_n else None})
    if refused:
        for key, near in refused:
            hint = f" Did you mean: {', '.join(near)}?" if near else ""
            print(f"REFUSED: label '{key}' is not in {a.evidence}.{hint}")
        print("No file written. A visual abstract shows only numbers that exist in the analysis output.")
        print(f"RESULT: FAIL ({len(refused)} label(s) not in evidence)")
        return 1
    if not cards:
        print("RESULT: FAIL (no labels given; pass --labels KEY:Caption)")
        return 1
    # Every number typed into the title, subtitle, captions or source line must also be in the evidence.
    free_text = "\n".join([a.title, a.subtitle or "", a.source or ""] + [c["caption"] for c in cards])
    items = numbers_in_text(free_text)
    pool = evidence_numbers([a.evidence])
    bad = [i for i in items if number_supported(i, pool) in (None, "sign")]
    if bad:
        for i in bad:
            print(f"REFUSED: '{i['value']}{'%' if i['pct'] else ''}' in the title/caption/source text is not in "
                  f"{a.evidence}: \"{i['context']}\"")
        print("No file written. Rewrite the text with a number from the evidence, or remove it.")
        print(f"RESULT: FAIL ({len(bad)} number(s) in free text not in evidence)")
        return 1
    svg = draw_svg(a.title, cards, a.lang, a.subtitle or "", a.source or "",
                   os.path.basename(a.evidence), a.accent, a.width, a.height)
    if any(ch in svg for ch in EN_EM):
        svg = svg.replace(chr(0x2013), "-").replace(chr(0x2014), "-")
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    print(f"visual abstract: {os.path.abspath(a.out)} | {a.width}x{a.height} | lang {a.lang} | "
          f"{len(cards)} statistic(s) from {a.evidence}")
    print(table([[c["key"], str(c["value"]), c["value_text"], short(c["caption"], 40),
                  "" if c["n"] is None else str(int(c["n"]) if float(c["n"]).is_integer() else c["n"])]
                 for c in cards], ["evidence key", "raw value", "shown as", "caption", "n (sibling key)"]))
    print("Not checked: whether the caption describes the statistic truthfully (e.g. a correlation captioned as "
          "an effect). Read each card against the APA line in the evidence before sending.")
    print("RESULT: PASS")
    return 0


# ---------------------------------------------------------------- check

HYPE_EN = ["revolutionary", "game-changing", "game changing", "groundbreaking", "breakthrough", "unprecedented",
           "proves that", "proven", "definitively", "first ever", "first-ever", "paradigm shift", "world-first",
           "miracle", "guaranteed", "100% effective", "silver bullet"]
HYPE_AR = ["ثوري", "ثورية", "غير مسبوق", "غير مسبوقة", "يثبت", "تثبت", "أثبتت", "أثبت", "بشكل قاطع", "قطعياً",
           "لأول مرة في العالم", "الأولى من نوعها في العالم", "معجزة", "حل سحري", "مضمون"]
CAUSAL_EN = [r"\bcauses?\b", r"\bcaused\b", r"\bleads? to\b", r"\bled to\b", r"\bresults? in\b", r"\bimpacts?\b",
             r"\bboosts?\b", r"\bincreases\b(?= [a-z]+ by)", r"\bdrives\b"]
CAUSAL_AR = ["يؤدي إلى", "تؤدي إلى", "يسبب", "تسبب", "ينتج عنه", "يرفع", "ترفع", "يحسّن", "يحسن", "أثر "]
JARGON = ["regression", "coefficient", "standardi[sz]ed", r"\bbeta\b", "β", r"\bp\s*[<=]", "confidence interval",
          r"\bCI\b", r"\bSD\b", "variance", "significant", "mediat", "moderat", "cronbach", "likert", "r\\(\\d+\\)",
          "الانحدار", "معامل", "دلالة إحصائية", "الانحراف المعياري", "التباين", "وسيط", "معدّل", "فترة الثقة", "ليكرت"]

SECTIONS = {
    "abstract": [("background / purpose", r"background|purpose|objective|aim|introduction|الخلفية|الهدف|المقدمة"),
                 ("methods", r"method|design|approach|المنهج|الطريقة|الإجراءات"),
                 ("results", r"result|finding|النتائج"),
                 ("conclusions", r"conclusion|implication|originality|الخلاصة|الاستنتاج|الخاتمة|الدلالات")],
    "brief": [("executive summary (الخلاصة)", r"الخلاصة|الملخص التنفيذي|executive summary|key message"),
              ("the problem / context (المشكلة)", r"المشكلة|السياق|لماذا الآن|the problem|context|why now"),
              ("what the evidence says (ما تقوله الأدلة)", r"الأدلة|النتائج|ما وجدناه|evidence|findings"),
              ("options or recommendations (التوصيات)", r"التوصي|الخيارات|recommend|options"),
              ("limits of the evidence (حدود الدليل)", r"حدود|محددات|limit|caveat|what this study cannot"),
              ("source (المصدر)", r"المصدر|المرجع|الدراسة الكاملة|source|reference|doi")],
    "post": [], "lay": [], "any": [],
}
LIMITS = {   # kind: (min_words, max_words, max_chars)
    "abstract": (150, 250, None),
    "brief": (250, 550, None),
    "post": (40, 400, 3000),
    "lay": (300, 520, None),
    "any": (None, None, None),
}


AR_LABEL_MAP = {"ن": "n", "بيتا": "beta", "ألفا": "alpha", "الفا": "alpha", "كرونباخ": "alpha"}
AR_LABELS = re.compile(r"(?<![\w؀-ۿ])(?:" + "|".join(AR_LABEL_MAP) + r")(?![\w؀-ۿ])")


def word_count(text):
    body = re.sub(r"^#{1,6}\s.*$", "", text, flags=re.M)          # headings are not prose
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    return len(re.findall(r"[\w؀-ۿ][\w'’؀-ۿ\-\.]*", body))


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?؟])\s+|\n{2,}", text) if len(s.strip()) > 2]


def cmd_check(a):
    with open(a.text, encoding="utf-8") as f:
        raw = f.read()
    text = raw.translate(ARABIC_DIGITS)
    kind = a.kind
    fails, warns, rows = [], [], []
    for p in a.evidence:
        if not os.path.exists(p):
            print(f"evidence file not found: {p}")
            return 1
    # 1. Numbers (the same check as `scholar.py numbers`, same helpers). Arabic statistic
    #    labels are mapped to the Latin ones scholar knows, so 'ن = 199' is checked as n, not as a bare number.
    items = numbers_in_text(AR_LABELS.sub(lambda m: AR_LABEL_MAP[m.group(0)], raw))
    raw_lines = raw.splitlines()
    for i in items:                                   # show the author's own line, not the normalised one
        if 0 < i["line"] <= len(raw_lines):
            i["context"] = raw_lines[i["line"] - 1].strip()[:120]
    pool = evidence_numbers(a.evidence)
    res = [(i, number_supported(i, pool)) for i in items]
    missing = [i for i, r in res if r is None]
    sign = [i for i, r in res if r == "sign"]
    weak = [i for i, r in res if r == "weak"]
    rows.append(["numbers in evidence", "FAIL" if (missing or sign) else "PASS",
                 f"{len(items)} checked, {len(missing)} unsupported, {len(sign)} sign, {len(weak)} weak"])
    fails += [f"UNSUPPORTED number line {i['line']}: {i['label'] or '?'} {i['op']}{i['value']}"
              f"{'%' if i['pct'] else ''} | {i['context']}" for i in missing]
    fails += [f"SIGN DIFFERS line {i['line']}: {i['label'] or '?'} {i['value']} | {i['context']}" for i in sign]
    warns += [f"WEAK MATCH line {i['line']}: {i['label'] or '?'} {i['value']}{'%' if i['pct'] else ''} "
              f"matched an unlabelled evidence value | {i['context']}" for i in weak]
    # 2. Length.
    wc = word_count(text)
    lo, hi, max_chars = LIMITS[kind]
    if a.max_words:
        hi = a.max_words
    length_ok = True
    if hi and wc > hi:
        fails.append(f"LENGTH: {wc} words, limit for '{kind}' is {hi}")
        length_ok = False
    elif lo and wc < lo:
        warns.append(f"LENGTH: {wc} words, a '{kind}' is usually at least {lo}")
    if max_chars and len(raw) > max_chars:
        fails.append(f"LENGTH: {len(raw)} characters, platform hard limit {max_chars}")
        length_ok = False
    if kind == "post" and len(raw) > 1300:
        warns.append(f"LENGTH: {len(raw)} characters; LinkedIn truncates after about 210 characters with 'see more' "
                     "and posts over 1,300 lose readers: lead with the finding")
    rows.append(["length", "PASS" if length_ok else "FAIL", f"{wc} words, {len(raw)} chars"])
    # 3. Required sections.
    need = SECTIONS[kind]
    if need:
        # Headings, bold labels (**Results:** text) and 'Label:' at the start of a line.
        heads = (re.findall(r"^#{1,6}\s.*$", text, re.M) + re.findall(r"\*\*([^*\n]{2,60})\*\*", text)
                 + re.findall(r"^([^\n:]{2,40}):", text, re.M))
        scan = "\n".join(heads) if heads else text
        absent = [name for name, rx in need if not re.search(rx, scan, re.I)]
        if absent:
            fails.append(f"SECTIONS missing for '{kind}': " + "; ".join(absent))
        rows.append(["sections", "FAIL" if absent else "PASS", f"{len(need) - len(absent)}/{len(need)} found"])
    # 4. Source line (post and brief must say where the number comes from).
    if kind in ("post", "brief", "lay"):
        has_src = re.search(r"doi\.org|\bDOI\b|\bSource\b|المصدر|\(\d{4}\)|\d{4}\)|preprint|under review|قيد التحكيم|"
                            r"الدراسة الكاملة|Full study", text, re.I)
        rows.append(["source line", "PASS" if has_src else "FAIL", "found" if has_src else "none"])
        if not has_src:
            fails.append("SOURCE: no source line (authors, year, venue or DOI; 'preprint' / 'under review' if not yet "
                         "published). A number without its source is a rumour.")
    # 5. Hype and causal wording.
    low = text.lower()
    hype = [w for w in HYPE_EN if w in low] + [w for w in HYPE_AR if w in text]
    rows.append(["hype words", "FAIL" if hype else "PASS", ", ".join(hype) if hype else "none"])
    if hype:
        fails.append("HYPE: " + ", ".join(hype) + " (deliverables.md bans them; state the number and its limits)")
    causal = [m.group(0) for rx in CAUSAL_EN for m in re.finditer(rx, low)] + [w for w in CAUSAL_AR if w in text]
    if causal and not a.causal_design:
        warns.append("CAUSAL WORDING: " + ", ".join(sorted(set(causal))[:8]) +
                     " (fine only for an experimental or longitudinal design; pass --causal-design to silence)")
    rows.append(["causal wording", "WARN" if causal and not a.causal_design else "PASS",
                 ", ".join(sorted(set(causal))[:5]) if causal else "none"])
    # 6. Lay summary: jargon and sentence length.
    if kind == "lay":
        jarg = sorted({m.group(0) for rx in JARGON for m in re.finditer(rx, text, re.I)})
        if jarg:
            warns.append("JARGON in a lay summary: " + ", ".join(jarg) + " (say it in everyday words)")
        long_s = [s for s in sentences(text) if len(s.split()) > 25]
        if long_s:
            warns.append(f"{len(long_s)} sentence(s) over 25 words; the first: \"{short(long_s[0], 90)}\"")
        rows.append(["plain language", "WARN" if (jarg or long_s) else "PASS",
                     f"{len(jarg)} jargon term(s), {len(long_s)} long sentence(s)"])
    # 7. Hashtags (post).
    if kind == "post":
        tags = re.findall(r"(?<!\w)#[\w؀-ۿ]+", text)
        if len(tags) > 5:
            warns.append(f"{len(tags)} hashtags; 3 to 5 is the norm")
        rows.append(["hashtags", "WARN" if len(tags) > 5 else "PASS", str(len(tags))])
    # 8. Dashes.
    nd = sum(text.count(ch) for ch in EN_EM)
    rows.append(["em/en dashes", "FAIL" if nd else "PASS", str(nd)])
    if nd:
        fails.append(f"DASHES: {nd} em/en dash(es); use a hyphen, comma, colon or parentheses")
    # 9. Arabic text direction hint (cannot be checked in .md; reminder only).
    if is_arabic(text) and kind in ("brief", "post", "lay", "abstract"):
        rows.append(["arabic", "NOTE", "when exported, wrap in dir=\"rtl\" (build_docx.py does); digits stay Western"])

    print(f"text: {a.text} | kind: {kind} | evidence: {', '.join(a.evidence)} | {wc} words | {TODAY}")
    print(table(rows, ["check", "result", "detail"]))
    for x in fails:
        print("FAIL  " + x)
    for x in warns:
        print("WARN  " + x)
    print("Not checked: whether each sentence is true to the paper's discussion, and whether the venue's own "
          "word limit or structure differs (pass --max-words / --kind to match it).")
    print("RESULT: " + ("FAIL" if fails else "PASS") + f" ({len(fails)} fail, {len(warns)} warn)")
    return 1 if fails else 0


# ---------------------------------------------------------------- selftest

SELFTEST_EVIDENCE = """# corr sleep gpa | file data.csv | rows 200
corr.sleep~gpa.r = 0.311146
corr.sleep~gpa.df = 197
corr.sleep~gpa.p = 7.70809e-06
corr.sleep~gpa.n = 199
# APA: r(197) = .31, p < .001
freq.gender.female.pct = 55
freq.gender.female.n = 110
ttest.gpa.by_gender.d = -0.143692
ttest.gpa.by_gender.p = 0.314169
"""


def cmd_selftest(a):
    ok = True
    d = tempfile.mkdtemp(prefix="deliverables-selftest-")
    ev = os.path.join(d, "output.txt")
    with open(ev, "w", encoding="utf-8") as f:
        f.write(SELFTEST_EVIDENCE)

    def run(fn, ns, expect):
        nonlocal ok
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = fn(ns) or 0
        good = (code == 0) == expect
        ok &= good
        return good, code, buf.getvalue()

    base = dict(evidence=ev, lang="en", decimals=2, title="Sleep and grades among 199 students", subtitle="",
                source="", accent="#1F5F8B", width=1200, height=675, show_n=True)
    tests = []
    # 1. positive visual
    ns = argparse.Namespace(labels=["corr.sleep~gpa.r:Sleep and GPA", "freq.gender.female.pct:Women in the sample"],
                            out=os.path.join(d, "ok.svg"), **base)
    g, c, o = run(cmd_visual, ns, True)
    svg_ok = os.path.exists(ns.out) and "r = .31" in open(ns.out, encoding="utf-8").read() and "55%" in open(ns.out, encoding="utf-8").read()
    ok &= svg_ok
    tests.append(["visual: 2 real labels", "PASS" if g and svg_ok else "FAIL", f"exit {c}; svg written with 'r = .31' and '55%': {svg_ok}"])
    # 2. negative: label not in evidence
    ns = argparse.Namespace(labels=["corr.sleep~gpa.r:Sleep and GPA", "corr.stress~gpa.r:Stress and GPA"],
                            out=os.path.join(d, "bad.svg"), **base)
    g, c, o = run(cmd_visual, ns, False)
    not_written = not os.path.exists(ns.out)
    ok &= not_written
    tests.append(["visual: label not in evidence", "PASS" if g and not_written and "REFUSED" in o else "FAIL",
                  f"exit {c}; refused: {'REFUSED' in o}; no file: {not_written}"])
    # 3. negative: invented number in the title
    ns = argparse.Namespace(labels=["corr.sleep~gpa.r:Sleep and GPA"], out=os.path.join(d, "bad2.svg"),
                            **{**base, "title": "Sleep explains 42% of grades"})
    g, c, o = run(cmd_visual, ns, False)
    tests.append(["visual: invented number in title", "PASS" if g and "REFUSED" in o else "FAIL", f"exit {c}"])
    # 4. Arabic visual
    ns = argparse.Namespace(labels=["corr.sleep~gpa.r:النوم والمعدل التراكمي"], out=os.path.join(d, "ar.svg"),
                            **{**base, "lang": "ar", "title": "نوم أكثر، معدل أعلى"})
    g, c, o = run(cmd_visual, ns, True)
    ar_ok = os.path.exists(ns.out) and 'direction="rtl"' in open(ns.out, encoding="utf-8").read() and "r = 0.31" in open(ns.out, encoding="utf-8").read()
    ok &= ar_ok
    tests.append(["visual: Arabic, rtl, leading zero", "PASS" if g and ar_ok else "FAIL", f"exit {c}; rtl + '0.31': {ar_ok}"])
    # 5. check: honest post passes
    good_post = os.path.join(d, "post.md")
    with open(good_post, "w", encoding="utf-8") as f:
        f.write("Students who slept more had higher grades: r = .31, p < .001 (n = 199).\n"
                "Correlational, one university, self-reported sleep.\n"
                "Source: Author (2026), under review. #sleep #highered\n")
    g, c, o = run(cmd_check, argparse.Namespace(text=good_post, evidence=[ev], kind="post", max_words=None,
                                                causal_design=False), True)
    tests.append(["check: honest post", "PASS" if g else "FAIL", f"exit {c}"])
    # 6. check: invented number fails
    bad_post = os.path.join(d, "bad_post.md")
    with open(bad_post, "w", encoding="utf-8") as f:
        f.write("Students who slept more had higher grades: r = .31, p < .001 (n = 199). 42% of them slept under 6 hours.\n"
                "Source: Author (2026), under review.\n")
    g, c, o = run(cmd_check, argparse.Namespace(text=bad_post, evidence=[ev], kind="post", max_words=None,
                                                causal_design=False), False)
    tests.append(["check: invented 42% fails", "PASS" if g and "UNSUPPORTED" in o else "FAIL", f"exit {c}"])
    # 7. check: wrong sign fails
    sign_post = os.path.join(d, "sign.md")
    with open(sign_post, "w", encoding="utf-8") as f:
        f.write("Men scored higher, d = 0.14, p = .314 (n = 199). Source: Author (2026), under review.\n")
    g, c, o = run(cmd_check, argparse.Namespace(text=sign_post, evidence=[ev], kind="post", max_words=None,
                                                causal_design=False), False)
    tests.append(["check: sign flipped d fails", "PASS" if g and "SIGN DIFFERS" in o else "FAIL", f"exit {c}"])
    print(table(tests, ["selftest", "result", "detail"]))
    print(f"files: {d}")
    print("RESULT: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


# ---------------------------------------------------------------- cli

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("visual", help="SVG visual abstract from labelled evidence (max 4 statistics)",
                       description='Example: deliverables.py visual --evidence analysis/output.txt --labels '
                                   '"corr.sleep~gpa.r:Sleep and GPA" --title "More sleep, higher GPA" --out va.svg')
    v.add_argument("--evidence", default="analysis/output.txt", help="analysis output with 'key = value' lines")
    v.add_argument("--labels", nargs="+", required=True, help='"evidence.key:Caption" (1 to 4). The key must exist')
    v.add_argument("--title", required=True, help="the finding as one sentence (numbers in it are checked too)")
    v.add_argument("--subtitle", default="", help="design and sample in one line, e.g. 'Cross-sectional survey'")
    v.add_argument("--source", default="", help="citation line: Authors (year). Journal. DOI, or 'under review'")
    v.add_argument("--lang", choices=["en", "ar"], default="en", help="ar = right-to-left text, leading zeros kept")
    v.add_argument("--decimals", type=int, default=2)
    v.add_argument("--accent", default="#1F5F8B", help="one accent colour, hex")
    v.add_argument("--width", type=int, default=1200)
    v.add_argument("--height", type=int, default=675)
    v.add_argument("--no-n", dest="show_n", action="store_false", help="hide the sibling 'n' under each card")
    v.add_argument("--out", default="visual_abstract.svg")

    c = sub.add_parser("check", help="numbers, length, sections, hype and source line of a derived text",
                       description="Example: deliverables.py check brief.md --evidence analysis/output.txt --kind brief")
    c.add_argument("text", help="the abstract / brief / post / lay summary (.md or .txt)")
    c.add_argument("--evidence", nargs="+", default=["analysis/output.txt"])
    c.add_argument("--kind", choices=["any", "abstract", "brief", "post", "lay"], default="any",
                   help="adds the length, section and source rules of that deliverable")
    c.add_argument("--max-words", type=int, help="override the word limit (the venue's own limit wins)")
    c.add_argument("--causal-design", action="store_true", help="experimental/longitudinal: allow causal verbs")

    sub.add_parser("selftest", help="run the positive case and the negative controls on synthetic evidence")

    a = p.parse_args()
    sys.exit(globals()["cmd_" + a.cmd](a) or 0)


if __name__ == "__main__":
    main()
