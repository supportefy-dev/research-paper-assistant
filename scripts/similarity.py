#!/usr/bin/env python3
"""similarity.py - paraphrase-risk check before Turnitin (research-paper-assistant).

Compares every manuscript sentence against the texts the project actually
holds: the abstracts in the source ledger and any full text in fulltext/<key>.txt.
It finds (1) exact shared word runs, (2) near-duplicate sentences, and
(3) quoted passages, and says whether each is cited. It is NOT Turnitin: it
can only see the sources in the ledger, never the whole web.

Commands
  check     manuscript vs ledger abstracts + fulltext/   (RESULT: PASS|FAIL)
  self      self-plagiarism: sentences reused between two chapters
  selftest  built-in positive and negative cases (no network)

Examples
  python -X utf8 similarity.py check paper.md --ledger sources.jsonl --fulltext fulltext/ --out similarity.md
  python -X utf8 similarity.py self --a chapter2.md --b chapter5.md
  python -X utf8 similarity.py selftest

Normalisation before comparing: case, hyphen/dash variants, straight and
curly quotes, Arabic diacritics and tatweel, alef variants (أ إ آ ٱ -> ا),
alef maqsura (ى -> ي), Persian yeh/kaf, Arabic-Indic digits. Punctuation is
ignored, so word order is what is compared.
"""

import argparse
import os
import re
import sys
import time
import unicodedata

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scholar import load_ledger, clean, short, table, strip_references  # noqa: E402

# ---------------------------------------------------------------- normalisation

QUOTE_MAP = dict.fromkeys([0x2018, 0x2019, 0x201A, 0x201B, 0x2032, 0x00B4, 0x0060], "'")
QUOTE_MAP.update(dict.fromkeys([0x201C, 0x201D, 0x201E, 0x201F, 0x2033, 0x00AB, 0x00BB, 0x300C, 0x300D], '"'))
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
AR_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ی": "ي", "ک": "ك"})
AR_DIAC = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ]")
# A token keeps Arabic diacritics attached so one word stays one token; they are dropped afterwards.
TOKEN_RE = re.compile(r"[\wؐ-ًؚ-ٰٟۖ-ۭـ]+")


def straighten(s):
    """Dashes to '-', curly quotes to straight, Arabic digits to ASCII, one space."""
    return clean(s).translate(QUOTE_MAP).translate(AR_DIGITS)


def norm_token(tok):
    t = unicodedata.normalize("NFKC", tok)
    t = AR_DIAC.sub("", t).translate(AR_LETTERS).replace("_", "")
    return t.casefold()


def tokens_of(text):
    """[(normalised token, start, end)] for a piece of (already straightened) text."""
    out = []
    for m in TOKEN_RE.finditer(text):
        n = norm_token(m.group(0))
        if n:
            out.append((n, m.start(), m.end()))
    return out


# ---------------------------------------------------------------- sentence splitting

ABBREV = re.compile(r"\b(et al|e\.g|i\.e|vs|cf|etc|viz|fig|figs|no|vol|pp|p|dr|prof|mr|mrs|ms|st|jr|inc|ltd|ed|eds|ch|sec|approx|ca)\."
                    r"|\b[A-Z]\.(?=\s)", re.I)
SENT_END = re.compile(r"(?<=[.!?؟])\s+(?=[\"'(\[A-Z0-9؀-ۿ])")
PAGE_MARK = re.compile(r"^\s*\[\[page\s+(\d+)\]\]\s*$", re.M)


def markdown_to_text(md):
    """Drop what is not prose: code, comments, headings markers, link targets, table pipes."""
    md = re.sub(r"<!--.*?-->", " ", md, flags=re.S)
    md = re.sub(r"```.*?```", " ", md, flags=re.S)
    md = re.sub(r"`[^`\n]*`", " ", md)
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md)
    md = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", md)
    md = re.sub(r"^\s{0,3}#{1,6}\s*", "", md, flags=re.M)
    md = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", md, flags=re.M)
    md = re.sub(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$", "", md, flags=re.M)
    md = re.sub(r"(?<![\w*])[*_]{1,3}(?=\S)|(?<=\S)[*_]{1,3}(?![\w*])", "", md)
    return md.replace("|", " ")


def split_sentences(text, keep_pages=False):
    """[(sentence text, line number, page)] from plain or markdown text.

    Lines are never joined: a paragraph break always ends a sentence.
    Page markers [[page N]] (fulltext files) set the page of what follows.
    """
    out, page = [], None
    for ln, line in enumerate(text.splitlines(), 1):
        pm = PAGE_MARK.match(line)
        if pm:
            page = int(pm.group(1))
            continue
        line = straighten(line)
        if not line:
            continue
        guarded = ABBREV.sub(lambda m: m.group(0).replace(".", "\u0001"), line)
        for chunk in SENT_END.split(guarded):
            s = chunk.replace("\u0001", ".").strip()
            if s:
                out.append((s, ln, page if keep_pages else None))
    return out


# ---------------------------------------------------------------- citations and quotes

CITE_RE = re.compile(r"\([^()]*?(?:(?:19|20)\d{2}[a-z]?|n\.d\.|in press|د\.ت)[^()]*\)"      # (Author, 2010) / Author (2010)
                     r"|\[\s*\d{1,3}(?:\s*[,\-]\s*\d{1,3})*\s*\]"                           # [12], [3-5]
                     r"|\[\^[^\]]+\]"                                                       # [^note]
                     r"|\(\s*(?:p|pp|ص)\.?\s*\d+", re.I)
QUOTED_RE = re.compile(r"\"([^\"]{3,})\"|'([^']{20,})'|«([^»]{3,})»")


def is_cited(sentence):
    return bool(CITE_RE.search(sentence))


def quoted_spans(sentence):
    """Character spans that sit inside quotation marks."""
    return [(m.start(), m.end()) for m in QUOTED_RE.finditer(sentence)]


def inside_quotes(spans, start, end):
    return any(qs <= start and end <= qe for qs, qe in spans)


# ---------------------------------------------------------------- sources

class Source:
    def __init__(self, key, kind, label=""):
        self.key, self.kind, self.label = key, kind, label
        self.tokens = []        # normalised tokens, whole text in order
        self.pages = []         # page per token (fulltext) or None
        self.sentences = []     # (set of 3-shingles, token count, original sentence, page)

    def add_text(self, text, keep_pages):
        for s, _ln, page in split_sentences(text, keep_pages=keep_pages):
            toks = [t for t, _, _ in tokens_of(s)]
            if not toks:
                continue
            self.tokens.extend(toks)
            self.pages.extend([page] * len(toks))
            self.sentences.append((shingles(toks, 3), len(toks), s, page))


def shingles(toks, k):
    return {tuple(toks[i:i + k]) for i in range(len(toks) - k + 1)}


def load_sources(ledger_path, fulltext_dir):
    """Ledger abstracts + fulltext/<key>.txt. Returns (sources, unchecked keys, notes)."""
    sources, unchecked, notes = [], [], []
    ledger = load_ledger(ledger_path) if ledger_path else []
    keys = set()
    for e in ledger:
        key = e.get("key") or e.get("doi") or "?"
        keys.add(key)
        ab = clean(e.get("abstract") or "")
        if ab:
            src = Source(key, "abstract", f"{key} (abstract)")
            src.add_text(ab, keep_pages=False)
            sources.append(src)
        else:
            unchecked.append(key)
    if fulltext_dir and os.path.isdir(fulltext_dir):
        for fn in sorted(os.listdir(fulltext_dir)):
            if not fn.lower().endswith(".txt"):
                continue
            key = fn[:-4]
            with open(os.path.join(fulltext_dir, fn), encoding="utf-8", errors="replace") as f:
                src = Source(key, "fulltext", f"{key} (fulltext)")
                src.add_text(f.read(), keep_pages=True)
            if src.tokens:
                sources.append(src)
                if key in unchecked:
                    unchecked.remove(key)
                if keys and key not in keys:
                    notes.append(f"fulltext/{fn} has no ledger key '{key}': compared anyway")
    elif fulltext_dir and fulltext_dir != "fulltext":
        notes.append(f"fulltext folder not found: {fulltext_dir}")
    return sources, unchecked, notes


# ---------------------------------------------------------------- matching

class Index:
    def __init__(self, sources, k, near_k=3):
        self.k, self.near_k = k, near_k
        self.sources = sources
        self.exact = {}         # k-shingle -> [(src_i, pos)]
        self.near = {}          # 3-shingle -> [(src_i, sent_i)]
        for si, src in enumerate(sources):
            t = src.tokens
            for pos in range(len(t) - k + 1):
                self.exact.setdefault(tuple(t[pos:pos + k]), []).append((si, pos))
            for sj, (sh, _n, _s, _p) in enumerate(src.sentences):
                for g in sh:
                    self.near.setdefault(g, []).append((si, sj))

    def exact_runs(self, toks):
        """Maximal shared runs of >= k tokens: [(src_i, start, end, src_pos)] (end exclusive)."""
        runs, k = [], self.k
        for i in range(len(toks) - k + 1):
            hits = self.exact.get(tuple(toks[i:i + k]))
            if not hits:
                continue
            for si, pos in hits[:50]:
                st = self.sources[si].tokens
                j = k
                while i + j < len(toks) and pos + j < len(st) and toks[i + j] == st[pos + j]:
                    j += 1
                runs.append((si, i, i + j, pos))
        # Drop runs contained in another run of the same source.
        runs.sort(key=lambda r: (r[0], r[1], -r[2]))
        kept = []
        for r in runs:
            if kept and kept[-1][0] == r[0] and kept[-1][1] <= r[1] and r[2] <= kept[-1][2]:
                continue
            kept.append(r)
        return kept

    def near_matches(self, toks, threshold, min_tokens):
        """[(src_i, sent_i, jaccard)] of source sentences with Jaccard >= threshold on 3-shingles."""
        if len(toks) < min_tokens:
            return []
        sh = shingles(toks, self.near_k)
        if not sh:
            return []
        counts = {}
        for g in sh:
            for hit in self.near.get(g, ()):
                counts[hit] = counts.get(hit, 0) + 1
        out, need = [], threshold * len(sh)
        for (si, sj), c in counts.items():
            if c < need:
                continue
            other, n, _s, _p = self.sources[si].sentences[sj]
            if n < min_tokens:
                continue
            jac = c / len(sh | other)
            if jac >= threshold:
                out.append((si, sj, round(jac, 2)))
        out.sort(key=lambda x: -x[2])
        return out


# ---------------------------------------------------------------- check

def check_manuscript(text, sources, min_words, jaccard, near_min):
    """Return (rows, stats). rows: dicts for the report, in manuscript order."""
    body, _refs = strip_references(text)
    sentences = split_sentences(markdown_to_text(body))
    index = Index(sources, min_words)
    rows, total, covered, uncited_words = [], 0, 0, 0
    for sent, ln, _page in sentences:
        tk = tokens_of(sent)
        toks = [t for t, _, _ in tk]
        total += len(toks)
        if not toks:
            continue
        cited = is_cited(sent)
        qspans = quoted_spans(sent)
        hit_sources, span_mask = set(), [False] * len(toks)
        for si, a, b, pos in index.exact_runs(toks):
            src = sources[si]
            hit_sources.add(si)
            for x in range(a, b):
                span_mask[x] = True
            cs, ce = tk[a][1], tk[b - 1][2]
            quoted = inside_quotes(qspans, cs, ce)
            whole = (b - a) == len(toks)
            if quoted and cited:
                kind, advice, level = "quoted, cited", "fine", "ok"
            elif quoted:
                kind, advice, level = "quoted, UNCITED", "add the citation in this sentence", "fail"
            elif cited:
                kind, advice, level = ("exact, cited (no quotation marks)",
                                       "quote and cite (put it in quotation marks) or paraphrase", "warn")
            else:
                kind, advice, level = "exact, UNCITED", "paraphrase, or quote and cite", "fail"
            if level == "fail":
                uncited_words += b - a
            where = src.key + (f" p.{src.pages[pos]}" if src.pages and src.pages[pos] else "")
            rows.append({"line": ln, "sentence": sent, "source": where, "type": kind + (" (whole sentence)" if whole else ""),
                         "shared": sent[cs:ce], "words": b - a, "advice": advice, "level": level})
        # Citations are not prose: "(Kirschner & Karpinski, 2010)" would only lower the Jaccard.
        prose = [t for t, _, _ in tokens_of(CITE_RE.sub(" ", sent))]
        for si, sj, jac in index.near_matches(prose, jaccard, near_min):
            if si in hit_sources:
                continue
            src = sources[si]
            _sh, _n, s_text, page = src.sentences[sj]
            hit_sources.add(si)
            span_mask = [True] * len(toks)
            where = src.key + (f" p.{page}" if page else "")
            advice = "paraphrase further" + ("" if cited else " and cite")
            rows.append({"line": ln, "sentence": sent, "source": where, "type": f"near-duplicate (Jaccard {jac})",
                         "shared": s_text, "words": len(toks), "advice": advice, "level": "near"})
        covered += sum(span_mask)
    stats = {"sentences": len(sentences), "words": total, "covered": covered, "uncited_words": uncited_words,
             "fails": sum(r["level"] == "fail" for r in rows), "warns": sum(r["level"] == "warn" for r in rows),
             "near": sum(r["level"] == "near" for r in rows), "fine": sum(r["level"] == "ok" for r in rows)}
    return rows, stats


def report_lines(a, rows, stats, sources, unchecked, notes, elapsed):
    n_ab = sum(s.kind == "abstract" for s in sources)
    n_ft = sum(s.kind == "fulltext" for s in sources)
    score = (100.0 * stats["covered"] / stats["words"]) if stats["words"] else 0.0
    out = [f"manuscript: {a.manuscript} | sentences: {stats['sentences']} | words: {stats['words']} | "
           f"sources: {len(sources)} ({n_ab} abstracts, {n_ft} fulltext) | min-words: {a.min_words} | "
           f"jaccard: {a.jaccard} | {elapsed:.2f}s"]
    out.append(f"overlap score: {score:.1f}% of manuscript words inside flagged overlaps "
               f"({stats['covered']}/{stats['words']}; uncited exact: {stats['uncited_words']} words)")
    out.append("")
    if rows:
        out.append(table([[f"L{r['line']}: {short(r['sentence'], 70)}", r["source"], r["type"],
                           short(r["shared"], 90), r["advice"]] for r in rows],
                         ["sentence", "source key", "overlap type", "shared text", "advice"]))
    else:
        out.append("no overlap found with the sources checked")
    out.append("")
    for n in notes:
        out.append("NOTE  " + n)
    if unchecked:
        out.append("NOT CHECKED: " + ", ".join(unchecked) + " (no abstract in the ledger and no fulltext/<key>.txt)")
    out.append("NOT CHECKED: anything outside the ledger and fulltext/ (the web, other theses). "
               "This is a pre-check, not a Turnitin report.")
    if stats["fails"]:
        verdict = f"FAIL ({stats['fails']} uncited exact overlap(s) >= {a.min_words} words"
    else:
        verdict = f"PASS ({stats['near']} near-duplicate(s)"
    verdict += f", {stats['warns']} cited-but-unquoted, {stats['fine']} quoted and cited)"
    out.append("RESULT: " + verdict)
    return out


def cmd_check(a):
    t0 = time.time()
    with open(a.manuscript, encoding="utf-8") as f:
        text = f.read()
    sources, unchecked, notes = load_sources(a.ledger, a.fulltext)
    if not sources:
        print(f"manuscript: {a.manuscript} | no source text to compare against "
              f"(ledger {a.ledger}: no abstracts; fulltext {a.fulltext}: no .txt files)")
        print("RESULT: FAIL (nothing checked)")
        return 1
    rows, stats = check_manuscript(text, sources, a.min_words, a.jaccard, a.near_min_words)
    lines = report_lines(a, rows, stats, sources, unchecked, notes, time.time() - t0)
    print("\n".join(lines))
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write("# Similarity pre-check\n\n" + "\n".join(lines) + "\n")
        print(f"written: {os.path.abspath(a.out)}")
    return 1 if stats["fails"] else 0


# ---------------------------------------------------------------- self-plagiarism

def cmd_self(a):
    t0 = time.time()
    texts = {}
    for label, path in (("a", a.a), ("b", a.b)):
        with open(path, encoding="utf-8") as f:
            body, _ = strip_references(f.read())
        texts[label] = split_sentences(markdown_to_text(body))
    b_src = Source(os.path.basename(a.b), "chapter")
    for s, _ln, _p in texts["b"]:
        toks = [t for t, _, _ in tokens_of(s)]
        if toks:
            b_src.tokens.extend(toks)
            b_src.pages.extend([None] * len(toks))
            b_src.sentences.append((shingles(toks, 3), len(toks), s, None))
    b_lines = {}
    for s, ln, _p in texts["b"]:
        b_lines.setdefault(tuple(t for t, _, _ in tokens_of(s)), ln)
    index = Index([b_src], a.min_words)
    rows, same, near, total, covered = [], 0, 0, 0, 0
    for s, ln, _p in texts["a"]:
        tk = tokens_of(s)
        toks = tuple(t for t, _, _ in tk)
        total += len(toks)
        if len(toks) < a.near_min_words:
            continue
        if toks in b_lines:
            same += 1
            covered += len(toks)
            rows.append([f"L{ln}: {short(s, 70)}", f"{os.path.basename(a.b)} L{b_lines[toks]}", "identical sentence",
                         short(s, 90), "rewrite one of them, or cite the earlier chapter"])
            continue
        mask = [False] * len(toks)
        for _si, x, y, _pos in index.exact_runs(list(toks)):
            for i in range(x, y):
                mask[i] = True
            rows.append([f"L{ln}: {short(s, 70)}", os.path.basename(a.b), f"exact run ({y - x} words)",
                         short(s[tk[x][1]:tk[y - 1][2]], 90), "rewrite the shared run"])
        if any(mask):
            covered += sum(mask)
            continue
        prose = [t for t, _, _ in tokens_of(CITE_RE.sub(" ", s))]
        for _si, sj, jac in index.near_matches(prose, a.jaccard, a.near_min_words):
            near += 1
            covered += len(toks)
            rows.append([f"L{ln}: {short(s, 70)}", os.path.basename(a.b), f"near-duplicate (Jaccard {jac})",
                         short(b_src.sentences[sj][2], 90), "paraphrase further"])
            break
    runs = sum(1 for r in rows if r[2].startswith("exact run"))
    print(f"a: {a.a} ({len(texts['a'])} sentences) | b: {a.b} ({len(texts['b'])} sentences) | "
          f"min-words: {a.min_words} | {time.time() - t0:.2f}s")
    pct = (100.0 * covered / total) if total else 0.0
    print(f"reuse score: {pct:.1f}% of the words in a also appear in b inside flagged overlaps ({covered}/{total})")
    print()
    print(table(rows, ["sentence (a)", "found in (b)", "overlap type", "shared text", "advice"]) if rows
          else "no sentence of a is reused in b")
    print()
    print(f"NOT CHECKED: sentences shorter than {a.near_min_words} words (headings, labels), and any third file.")
    if same or runs:
        print(f"RESULT: FAIL ({same} identical sentence(s), {runs} exact run(s) >= {a.min_words} words, {near} near-duplicate(s))")
        return 1
    print(f"RESULT: PASS ({near} near-duplicate(s))")
    return 0


# ---------------------------------------------------------------- selftest

SELFTEST_ABSTRACT = ("This article presents the preliminary results of a descriptive and exploratory survey study "
                     "involving Facebook use, often carried out simultaneously with other study activities, and its "
                     "relation to academic performance as measured by self-reported Grade Point Average (GPA) and hours "
                     "spent studying per week. Results show that Facebook users reported having lower GPAs and spend "
                     "fewer hours per week studying than nonusers.")
SELFTEST_AR = ("هدفت الدراسة إلى معرفة القيادة التحويلية ودورها في تحسين الأداء الوظيفي لدى العاملين في بلدية البيرة. "
               "واستخدمت الدراسة المنهج الوصفي التحليلي وتكونت عينة الدراسة من العاملين في البلدية.")


def cmd_selftest(a):
    import json
    import tempfile
    d = tempfile.mkdtemp(prefix="similarity-selftest-")
    ledger = os.path.join(d, "sources.jsonl")
    with open(ledger, "w", encoding="utf-8") as f:
        f.write(json.dumps({"key": "kirschner2010", "abstract": SELFTEST_ABSTRACT,
                            "authors": [{"family": "Kirschner", "given": "P."}], "year": 2010}, ensure_ascii=False) + "\n")
        f.write(json.dumps({"key": "badr2024", "abstract": SELFTEST_AR,
                            "authors": [{"family": "بدر", "given": ""}], "year": 2024}, ensure_ascii=False) + "\n")
        f.write(json.dumps({"key": "noabstract2019", "abstract": "", "authors": [{"family": "X", "given": ""}],
                            "year": 2019}, ensure_ascii=False) + "\n")
    cases = [
        ("copy_uncited", "Results show that Facebook users reported having lower GPAs and spend fewer hours per week "
                         "studying than nonusers.", "fail"),
        ("copy_quoted_cited", "As the authors put it, “Facebook users reported having lower GPAs and spend fewer "
                              "hours per week studying than nonusers” (Kirschner & Karpinski, 2010).", "ok"),
        ("copy_quoted_uncited", "One study concluded that \"Facebook users reported having lower GPAs and spend fewer "
                                "hours per week studying than nonusers\".", "fail"),
        ("copy_cited_unquoted", "Facebook users reported having lower GPAs and spend fewer hours per week studying "
                                "than nonusers (Kirschner & Karpinski, 2010).", "warn"),
        ("paraphrase_j0.30", "Findings show that Facebook users reported having weaker GPAs and spend fewer hours "
                             "each week studying than peers (Kirschner & Karpinski, 2010).", "near"),
        ("arabic_diacritics", "هَدَفَتِ الدِّرَاسَةُ الى مَعْرِفَةِ القِيَادَةِ التَّحْوِيلِيَّةِ وَدَوْرِهَا فِى تَحْسِينِ الأَدَاءِ الوَظِيفِيِّ لَدَى العَامِلِينَ فِي بَلَدِيَّةِ البِيرَةِ.", "fail"),
        ("original", "Our own survey of 212 undergraduates in Amman measured weekly study hours with a diary method.",
         None),
    ]
    text = "\n\n".join(s for _, s, _ in cases)
    ms = os.path.join(d, "paper.md")
    with open(ms, "w", encoding="utf-8") as f:
        f.write("# Selftest\n\n" + text + "\n")
    sources, unchecked, _notes = load_sources(ledger, None)
    rows, stats = check_manuscript(text, sources, 8, 0.5, 6)
    by_sentence = {}
    for r in rows:
        by_sentence.setdefault(r["sentence"], []).append(r["level"])
    # A paraphrase with a word changed every 5-6 words never reaches Jaccard 0.5 on
    # 3-word shingles (each change removes 3 shingles: 3 changes in 18 words = 8/24 = 0.33),
    # so that case runs at 0.30.
    rows_near, _ = check_manuscript(text, sources, 8, 0.30, 6)
    for r in rows_near:
        if r["level"] == "near":
            by_sentence.setdefault(r["sentence"], []).append("near")
    results, ok = [], True
    for name, sent, want in cases:
        got = sorted(set(by_sentence.get(straighten(sent), [])))
        passed = (want is None and not got) or (want is not None and want in got)
        ok &= passed
        results.append([name, want or "no flag", ", ".join(got) or "no flag", "ok" if passed else "MISMATCH"])
    print(table(results, ["case", "expected", "found", "check"]))
    print(f"unchecked keys reported: {unchecked} (expected ['noabstract2019'])")
    ok &= unchecked == ["noabstract2019"]
    print(f"fixtures: {d}")
    print("RESULT: " + ("PASS" if ok else "FAIL") + " (selftest, no network)")
    return 0 if ok else 1


# ---------------------------------------------------------------- cli

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="compare a manuscript with the ledger abstracts and fulltext/",
                       description="Example: similarity.py check paper.md --ledger sources.jsonl --fulltext fulltext/ --out similarity.md")
    p.add_argument("manuscript")
    p.add_argument("--ledger", default="sources.jsonl")
    p.add_argument("--fulltext", default="fulltext", help="folder of <key>.txt files with [[page N]] markers")
    p.add_argument("--min-words", type=int, default=8, help="shortest exact shared run to flag (default 8)")
    p.add_argument("--jaccard", type=float, default=0.5, help="near-duplicate threshold on 3-word shingles (default 0.5)")
    p.add_argument("--near-min-words", type=int, default=6, help="ignore sentences shorter than this for near-duplicates")
    p.add_argument("--out", help="write the same report as markdown")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("self", help="sentences reused between two chapters of the same thesis",
                       description="Example: similarity.py self --a chapter2.md --b chapter5.md")
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--min-words", type=int, default=8)
    p.add_argument("--jaccard", type=float, default=0.5)
    p.add_argument("--near-min-words", type=int, default=6)
    p.set_defaults(func=cmd_self)

    p = sub.add_parser("selftest", help="built-in positive and negative cases, no network",
                       description="Example: similarity.py selftest")
    p.set_defaults(func=cmd_selftest)

    a = ap.parse_args()
    sys.exit(a.func(a))


if __name__ == "__main__":
    main()
