#!/usr/bin/env python3
"""evidence.py - full-text evidence for the research-paper-assistant skill.

Every citation in a manuscript should rest on a verbatim quote with a page
number. This tool fetches open-access full texts (never bypassing a paywall),
finds candidate passages, records quotes that are really in the text, and
audits a manuscript against those records.

Commands
  fetch     get the full text of every ledger source: papers/ (user PDFs),
            Unpaywall, OpenAlex OA locations, Europe PMC XML, arXiv
  quote     find the passages that best support a claim (a finder, not a judge)
  claim add record a claim + verbatim quote + page (refused if not in the text;
            a quote that crosses a page break is named and needs --across-pages)
  audit     every cited sentence whose source has a full text needs a verbatim
            claim; sources without a full text are counted as cited at
            abstract/title level (WARN; --strict makes them FAIL); causal verbs
            on a correlational source are flagged
  trail     evidence appendix (markdown + self-contained HTML with hover quotes)
  selftest  offline check with synthetic PDFs (positive + negative controls,
            including a corrupt PDF)

Optional environment variables
  RESEARCH_MAILTO   your email: enables Unpaywall (it rejects placeholder addresses)

Run with:  python -X utf8 evidence.py <command> --help
"""

import argparse
import contextlib
import html
import io
import json
import os
import re
import sys
import tempfile
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scholar import (http_get, as_json, openalex_by_doi, load_ledger, clean, norm_doi, title_sim, table,  # noqa: E402
                     short, apa, TODAY, ARABIC_RE, MAILTO, HTTPError, strip_references, extract_citations,
                     ledger_match, numbers_in_text, evidence_numbers, number_supported)

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

try:
    import fitz                      # PyMuPDF
except ImportError:                  # pragma: no cover
    fitz = None

PLACEHOLDER_MAIL = "research-skill@example.com"      # Unpaywall answers 422 to it (checked 2026-10-21)
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
PAGE_MARK = re.compile(r"^\[\[page ([^\]]+)\]\]\s*$")
MIN_QUOTE_WORDS = 5
ARXIV_DOI = re.compile(r"^10\.48550/arxiv\.(.+)$", re.I)

# ---------------------------------------------------------------- text normalisation

_DASH_CHARS = "-" + "".join(chr(c) for c in (0xAD, 0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015, 0x2043, 0x2212,
                                                0xFE58, 0xFE63, 0xFF0D))
_QUOTE_CHARS = "'\"‘’‚‛“”„‟′″«»‹›`´"
_DROP = {ord(c): None for c in _DASH_CHARS + _QUOTE_CHARS + "ـ​‌‍‎‏﻿"}
_AR_DIACRITICS = re.compile("[ً-ٰٟۖ-ۭ]")
_AR_ALEF = {ord(c): "ا" for c in "آأإٱ"}


def norm_q(s):
    """Comparison form for the verbatim check: NFKC (ligatures), no dashes,
    no quotes, no whitespace, no Arabic diacritics or tatweel, alef unified,
    case-folded. Punctuation and letters are kept, so the words must match."""
    s = unicodedata.normalize("NFKC", html.unescape(s or ""))
    s = _AR_DIACRITICS.sub("", s).translate(_AR_ALEF).translate(_DROP)
    return re.sub(r"\s+", "", s).casefold()


STOP_EN = set("""a an the and or but if then than that this these those of in on at to for from by with without
as is are was were be been being have has had do does did not no nor so such it its into onto about over under
between among through during before after above below up down out off again further once here there when where
why how all any both each few more most other some own same too very can will just should now also may might
must shall which who whom whose what while however although because therefore thus hence among via per et al
study studies research paper results found show shows showed reported report using used use based""".split())
STOP_AR = set("""في من على إلى عن أن إن كان كانت هذا هذه ذلك تلك التي الذي الذين ما لا لم لن قد و أو ثم بل حتى
كما مع بين عند لدى هو هي هم هن نحن أنا أنت كل بعض غير ذات ذو أي إذا لو ليس بعد قبل خلال حول حيث أيضا
دراسة الدراسة نتائج النتائج أظهرت وجد وجدت تشير أشارت""".split())


def content_words(s):
    """Lower-cased content tokens with a light stem (EN plurals/tenses, AR ال/و prefixes)."""
    s = _AR_DIACRITICS.sub("", unicodedata.normalize("NFKC", s or "")).translate(_AR_ALEF)
    words, nums = set(), set()
    for tok in re.findall(r"[A-Za-zÀ-ɏ؀-ۿ][\wÀ-ɏ؀-ۿ'\-]*|\d+(?:[.,]\d+)?%?", s):
        if re.match(r"\d", tok):
            v = tok.rstrip("%").replace(",", ".")
            try:
                nums.add(f"{float(v):g}")
            except ValueError:
                pass
            continue
        t = tok.lower().strip("'-")
        if ARABIC_RE.search(t):
            t = re.sub(r"^(و|ف|ب|ل|ك)?(ال)", "", t) if len(t) > 4 else t
            if len(t) < 2 or t in STOP_AR:
                continue
        else:
            if len(t) < 3 or t in STOP_EN:
                continue
            for suf in ("ingly", "ing", "edly", "ed", "ies", "es", "s", "ly"):
                if t.endswith(suf) and len(t) - len(suf) >= 4:
                    t = t[: -len(suf)]
                    break
        words.add(t)
    return words, nums


# ---------------------------------------------------------------- full-text files

def load_fulltext(path):
    """-> [(page_label, text)] from a fulltext/<key>.txt with [[page N]] markers."""
    pages, label, buf = [], None, []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = PAGE_MARK.match(line)
            if m:
                if label is not None or buf:
                    pages.append((label, "".join(buf)))
                label, buf = m.group(1).strip(), []
            else:
                buf.append(line)
    if label is not None or buf:
        pages.append((label, "".join(buf)))
    return [(lab if lab is not None else "1", txt) for lab, txt in pages]


def write_fulltext(path, pages):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for lab, txt in pages:
            f.write(f"[[page {lab}]]\n{txt.rstrip()}\n\n")


def load_index(fulltext_dir):
    p = os.path.join(fulltext_dir, "index.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_index(fulltext_dir, idx):
    with open(os.path.join(fulltext_dir, "index.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)


class PDFUnreadable(Exception):
    """PyMuPDF cannot open the file or cannot load one of its pages (broken page tree,
    truncated download, encrypted file). The message is the MuPDF error."""


def read_pdf_pages(path_or_bytes):
    """-> (texts, labels, error). Reads page by page by index (a plain `for page in doc`
    swallows an IndexError and hides a broken page tree). Never raises: on a broken file
    or page the pages read so far come back with the error text."""
    if fitz is None:
        sys.exit("PyMuPDF is missing: pip install pymupdf")
    texts, labels, n = [], [], 0
    try:
        doc = fitz.open(stream=path_or_bytes, filetype="pdf") if isinstance(path_or_bytes, bytes) else fitz.open(path_or_bytes)
    except Exception as e:
        return texts, labels, f"{type(e).__name__}: {e}"
    try:
        n = doc.page_count
        for k in range(n):
            page = doc[k]
            texts.append(page.get_text("text"))
            try:
                labels.append(page.get_label() or "")
            except Exception:           # older PyMuPDF
                labels.append("")
    except Exception as e:
        return texts, labels, f"{type(e).__name__}: {e} (page {len(texts) + 1} of {n})"
    finally:
        doc.close()
    return texts, labels, ""


def pdf_page_texts(path_or_bytes):
    """-> (texts, labels); raises PDFUnreadable (callers record it as a status, never a crash)."""
    texts, labels, err = read_pdf_pages(path_or_bytes)
    if err:
        raise PDFUnreadable(err)
    return texts, labels


def page_labels(n, entry, pdf_labels):
    """Printed page numbers when they can be known, else physical PDF pages.

    1. PDF page labels (set by the publisher) when every page has a numeric one.
    2. The ledger page range when its length equals the PDF page count.
    3. Physical index 1..n (quote these as PDF pages, not printed pages)."""
    if pdf_labels and all(re.fullmatch(r"\d+", x or "") for x in pdf_labels) and len(set(pdf_labels)) == n:
        return list(pdf_labels), "printed (PDF page labels)"
    m = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", str(entry.get("pages") or ""))
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if b - a + 1 == n:
            return [str(a + i) for i in range(n)], "printed (ledger page range matches the PDF page count)"
    return [str(i + 1) for i in range(n)], "pdf (physical page index; printed page numbers unknown)"


def pages_from_pdf(data, entry):
    texts, labels = pdf_page_texts(data)
    labs, numbering = page_labels(len(texts), entry, labels)
    return list(zip(labs, texts)), numbering


# ---------------------------------------------------------------- fetch sources

def download_pdf(url):
    """-> (bytes, '') or (None, reason). One retry with a browser UA on 403,
    nothing more: a site that still refuses is left alone."""
    for headers in ({}, {"User-Agent": BROWSER_UA, "Accept": "application/pdf,*/*;q=0.8"}):
        try:
            r = http_get(url, headers=headers, retries=1, timeout=90)
        except HTTPError as e:
            if e.status == 403 and not headers:
                continue
            return None, f"HTTP {e.status}"
        if r is None:
            return None, "HTTP 404"
        body = r.content
        if body[:1024].lstrip().startswith(b"%PDF"):
            return body, ""
        ct = (r.headers.get("content-type") or "").split(";")[0]
        return None, f"not a PDF ({ct or 'unknown type'})"
    return None, "HTTP 403 (the site blocks scripts)"


def match_local_pdf(entry, pdf_info):
    """pdf_info: {path: {'doi_text': ..., 'first': ...}}. Returns (path, how) or (None, None).
    Matched by the DOI printed in the PDF, then by the ledger key in the file name (the only
    way to attribute a PDF that cannot be read at all), then by the title on page 1."""
    doi = (entry.get("doi") or "").lower()
    title = clean(entry.get("title") or "")
    key = (entry.get("key") or "").lower()
    best = (0.0, None)
    for path, info in pdf_info.items():
        if doi and norm_q(doi) in info["doi_text"]:
            return path, "DOI printed in the PDF"
    for path in pdf_info:
        if key and key in os.path.basename(path).lower():
            return path, "ledger key in the file name"
    for path, info in pdf_info.items():
        if title:
            sim = title_on_page(info["first"], title)
            if sim > best[0]:
                best = (sim, path)
    if best[0] > 0.85:
        return best[1], f"title on page 1 (similarity {best[0]:.2f})"
    return None, None


def title_on_page(page_text, title):
    """Best similarity between the title and any same-length run of words on the page."""
    if norm_q(title) and norm_q(title) in norm_q(page_text):
        return 1.0
    words = clean(page_text).split()[:600]
    tw = len(title.split())
    best = 0.0
    for n in (tw, tw + 1, tw + 2, max(1, tw - 1)):
        for i in range(0, max(1, len(words) - n + 1)):
            best = max(best, title_sim(" ".join(words[i: i + n]), title))
            if best > 0.97:
                return best
    return best


def scan_papers(papers_dir):
    info = {}
    if not papers_dir or not os.path.isdir(papers_dir):
        return info
    for name in sorted(os.listdir(papers_dir)):
        if not name.lower().endswith(".pdf"):
            continue
        path = os.path.join(papers_dir, name)
        texts, _, err = read_pdf_pages(path)      # a broken or encrypted file is data, not a crash
        if err:
            print(f"[papers] cannot read {name}: {err}", file=sys.stderr)
        probe = "".join(texts[:2] + texts[-1:])
        info[path] = {"doi_text": norm_q(probe), "first": texts[0] if texts else "", "error": err}
    return info


def unpaywall_pdf_urls(doi, email):
    """-> (is_oa or None, [pdf urls]). None = no record."""
    r = http_get("https://api.unpaywall.org/v2/" + urllib.parse.quote(doi, safe="/()"), params={"email": email})
    if r is None:
        return None, []
    d = as_json(r)
    urls = []
    for loc in [d.get("best_oa_location") or {}] + (d.get("oa_locations") or []):
        u = loc.get("url_for_pdf")
        if u and u not in urls:
            urls.append(u)
    return d.get("is_oa"), urls


def openalex_pdf_urls(doi):
    w = openalex_by_doi(doi)
    if not w:
        return None, [], {}
    urls = []
    for loc in [w.get("best_oa_location") or {}] + (w.get("locations") or []):
        u = loc.get("pdf_url")
        if u and u not in urls:
            urls.append(u)
    oa = w.get("open_access") or {}
    if oa.get("oa_url") and oa["oa_url"] not in urls:
        urls.append(oa["oa_url"])
    return oa.get("is_oa"), urls, w.get("ids") or {}


def europepmc_pmcid(doi):
    r = http_get("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                 params={"query": f'DOI:"{doi}"', "format": "json", "resultType": "lite"}, retries=2)
    hits = (as_json(r).get("resultList") or {}).get("result", []) if r is not None else []
    for h in hits:
        if h.get("pmcid"):
            return h["pmcid"]
    return None


def europepmc_xml_text(pmcid):
    """Full text from Europe PMC JATS XML: one unpaginated 'page', headings as '## ' lines,
    paragraphs separated by blank lines (APA locators: section + paragraph)."""
    r = http_get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML", retries=2)
    if r is None:
        return ""
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        return ""
    body = root.find(".//body")
    if body is None:
        return ""
    out = []

    def text_of(el):
        return clean("".join(el.itertext()))

    def walk(el, depth):
        for child in el:
            tag = child.tag.split("}")[-1]
            if tag == "sec":
                t = child.find("title")
                if t is not None and text_of(t):
                    out.append("#" * min(depth + 2, 6) + " " + text_of(t))
                walk(child, depth + 1)
            elif tag == "title":
                continue
            elif tag in ("p", "list-item", "disp-quote"):
                t = text_of(child)
                if t:
                    out.append(t)
            elif tag in ("table-wrap", "fig"):
                cap = child.find(".//caption")
                lab = child.find("label")
                t = " ".join(x for x in (text_of(lab) if lab is not None else "", text_of(cap) if cap is not None else "") if x)
                if t:
                    out.append(t)
            else:
                walk(child, depth)
    walk(body, 0)
    return "\n\n".join(out)


def arxiv_id(entry):
    doi = entry.get("doi") or ""
    m = ARXIV_DOI.match(doi)
    if m:
        return m.group(1)
    ext = entry.get("externalIds") or entry.get("external_ids") or {}
    for k in ("ArXiv", "arxiv", "arXiv"):
        if ext.get(k):
            return ext[k]
    return entry.get("arxiv") or None


def fetch_one(entry, a, pdf_info, email):
    """-> dict for index.json: source, url_or_path, pages, numbering, status, pdf?, text pages."""
    key = entry["key"]
    res = {"source": None, "url_or_path": None, "pages": 0, "numbering": None, "fetched": TODAY, "status": ""}
    # 1. the user's own PDF
    path, how = match_local_pdf(entry, pdf_info)
    if path:
        with open(path, "rb") as f:
            data = f.read()
        try:
            pages, numbering = pages_from_pdf(data, entry)
        except PDFUnreadable as e:
            res.update(source="papers/", url_or_path=path,
                       status=f"PDF unreadable: {e}; replace {os.path.basename(path)} in papers/ with a good copy")
            return res
        res.update(source="papers/", url_or_path=path, pages=len(pages), numbering=numbering,
                   status=f"ok ({how})", _pages=pages)
        return res
    doi = norm_doi(entry.get("doi") or "")
    if not doi:
        res["status"] = "no DOI: put the PDF or scan in papers/ (matched by title or by the key in the file name)"
        return res
    is_oa, tried, blocked, unreadable = None, [], [], []

    def try_urls(urls, source):
        for u in urls:
            if u in tried:
                continue
            tried.append(u)
            data, why = download_pdf(u)
            if data:
                try:
                    pages, numbering = pages_from_pdf(data, entry)
                except PDFUnreadable as e:        # a broken download: note it, try the next copy
                    unreadable.append(f"PDF unreadable: {e} ({u})")
                    continue
                res.update(source=source, url_or_path=u, pages=len(pages), numbering=numbering, status="ok",
                           _pages=pages, _pdf=data)
                return True
            blocked.append(f"{why}: {u}")
        return False

    # 2. Unpaywall (needs a real email: it refuses placeholders)
    if email:
        try:
            oa, urls = unpaywall_pdf_urls(doi, email)
            is_oa = oa if oa is not None else is_oa
            if try_urls(urls, "unpaywall"):
                return res
        except HTTPError as e:
            print(f"[unpaywall] {key}: {e}", file=sys.stderr)
    # 3. OpenAlex OA locations (single-entity lookup, 0 credits)
    try:
        oa, urls, ids = openalex_pdf_urls(doi)
        is_oa = oa if is_oa is None else (is_oa or bool(oa))
        if try_urls(urls, "openalex-oa"):
            return res
    except HTTPError as e:
        print(f"[openalex] {key}: {e}", file=sys.stderr)
    # 4. Europe PMC full-text XML (biomedical; no page numbers)
    try:
        pmcid = europepmc_pmcid(doi)
        if pmcid:
            txt = europepmc_xml_text(pmcid)
            if txt:
                res.update(source="europepmc-xml", url_or_path=f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML",
                           pages=1, numbering="none (XML: cite section + paragraph, not a page)",
                           status="ok (unpaginated XML)", _pages=[("1", txt)])
                return res
    except HTTPError as e:
        print(f"[europepmc] {key}: {e}", file=sys.stderr)
    # 5. arXiv
    ax = arxiv_id(entry)
    if ax and try_urls([f"https://arxiv.org/pdf/{ax}"], "arxiv"):
        return res
    if unreadable:
        res["status"] = short(unreadable[0], 160) + ": save a good copy in your browser into papers/"
    elif blocked:
        res["status"] = ("OA copy not downloadable (" + "; ".join(short(b, 90) for b in blocked[:2]) +
                         "): save it in your browser into papers/")
    elif is_oa is False:
        res["status"] = "paywalled: ask the user for the PDF (put it in papers/)"
    else:
        res["status"] = "no OA copy found: ask the user for the PDF (put it in papers/)"
    return res


def cmd_fetch(a):
    ledger = load_ledger(a.ledger)
    if a.key:
        ledger = [e for e in ledger if e["key"] in a.key]
        missing = set(a.key) - {e["key"] for e in ledger}
        if missing:
            print(f"not in ledger: {', '.join(sorted(missing))}")
    os.makedirs(a.out, exist_ok=True)
    idx = load_index(a.out)
    email = a.email or MAILTO
    if not email:
        print("Unpaywall skipped: it rejects placeholder emails (HTTP 422). Set RESEARCH_MAILTO or pass --email "
              "to use it. OpenAlex OA locations, Europe PMC and arXiv are still tried.")
    pdf_info = scan_papers(a.papers)
    rows, ok = [], 0
    print(f"ledger: {a.ledger} ({len(ledger)} sources) | papers/: {len(pdf_info)} PDF(s) | out: {a.out} | {TODAY}")
    for e in ledger:
        key = e["key"]
        txt_path = os.path.join(a.out, key + ".txt")
        if os.path.exists(txt_path) and key in idx and not a.force:
            r = idx[key]
            rows.append([key, r.get("source") or "", str(r.get("pages") or ""), "kept (already fetched; --force to redo)"])
            ok += 1
            continue
        try:
            r = fetch_one(e, a, pdf_info, email)
        except HTTPError as err:
            r = {"source": None, "url_or_path": None, "pages": 0, "numbering": None, "fetched": TODAY,
                 "status": f"network error: {err}"}
        pages = r.pop("_pages", None)
        pdf = r.pop("_pdf", None)
        if pages:
            write_fulltext(txt_path, pages)
            if pdf:
                with open(os.path.join(a.out, key + ".pdf"), "wb") as f:
                    f.write(pdf)
                r["pdf"] = os.path.join(a.out, key + ".pdf")
            r["file"] = txt_path
            idx[key] = r
            ok += 1
        elif not os.path.exists(txt_path):
            idx[key] = r                    # the failure (e.g. 'PDF unreadable: ...') is on record; an older good text is kept
        rows.append([key, r.get("source") or "", str(r.get("pages") or ""), r["status"]])
    save_index(a.out, idx)
    print(table(rows, ["key", "source", "pages", "status"]))
    print(f"{ok}/{len(ledger)} full texts available in {a.out} | index: {os.path.join(a.out, 'index.json')}")
    for e in ledger:
        r = idx.get(e["key"]) or {}
        numbering = str(r.get("numbering") or "")
        if numbering.startswith("pdf "):
            print(f"  {e['key']}: page markers are PDF page indexes (printed numbers unknown): cite as PDF pages or "
                  "check the printed number on the page.")
        elif numbering.startswith("none"):
            print(f"  {e['key']}: no page numbers (XML). APA 7 for unpaginated sources: cite the section heading and "
                  "paragraph number; `claim add` records them.")
    print("Paywalls are never bypassed: for a 'paywalled' or 'blocked' source, the user saves the PDF into papers/ "
          "and runs fetch again.")
    return 0


# ---------------------------------------------------------------- sentences

ABBR = r"(?:et al|e\.g|i\.e|cf|vs|etc|pp?|Fig|Figs|No|Nos|Vol|Eq|Eqs|approx|ca|Dr|Prof|St|Mr|Ms|Mrs|Jr|Sr|Inc|Ltd|Co)"


def split_sentences(text):
    t = re.sub(r"\b(" + ABBR + r")\.", lambda m: m.group(1) + "\x00", text)
    t = re.sub(r"\b([A-Z])\.(?=\s*[A-Z]|\s*$)", lambda m: m.group(1) + "\x00", t)     # initials: P. A. Kirschner
    t = re.sub(r"(\d)\.(\d)", lambda m: m.group(1) + "\x00" + m.group(2), t)          # decimals
    t = re.sub(r"\.(?=\d)", "\x00", t)                                   # .31
    parts = re.split(r"(?<=[.!?؟])\s+(?=[\"'(\[“‘A-Z0-9؀-ۿ])", t)
    return [p.replace("\x00", ".").strip() for p in parts if p.strip()]


def page_sentences(pages):
    """-> [(page_label, sentence)] from fulltext pages; line breaks joined, end-of-line
    hyphenation kept (the verbatim check ignores dashes)."""
    out = []
    for lab, txt in pages:
        flat = re.sub(r"-\n(?=[a-z؀-ۿ])", "-", txt)
        for para in re.split(r"\n\s*\n", flat):
            para = re.sub(r"\s+", " ", para).strip()
            if para.startswith("#"):
                continue
            for s in split_sentences(para):
                if len(s) >= 25:
                    out.append((lab, s))
    return out


def score_passage(claim_words, claim_nums, sentence):
    sw, sn = content_words(sentence)
    shared_w, shared_n = claim_words & sw, claim_nums & sn
    denom = len(claim_words) + 2 * len(claim_nums)
    if not denom:
        return 0.0, shared_w, shared_n
    return (len(shared_w) + 2 * len(shared_n)) / denom, shared_w, shared_n


def cmd_quote(a):
    path = os.path.join(a.fulltext, a.key + ".txt")
    if not os.path.exists(path):
        print(f"no full text for {a.key}: run `evidence.py fetch` (or put the PDF in papers/) first")
        return 1
    pages = load_fulltext(path)
    cw, cn = content_words(a.claim)
    if not cw and not cn:
        print("the claim has no content words to search for")
        return 1
    scored = []
    for lab, s in page_sentences(pages):
        sc, w, n = score_passage(cw, cn, s)
        if sc > 0:
            scored.append((sc, len(s), lab, s, w, n))
    scored.sort(key=lambda x: (-x[0], x[1]))
    unpag = str(load_index(a.fulltext).get(a.key, {}).get("numbering", "")).startswith("none") or \
        (len(pages) == 1 and pages[0][0] == "1" and "\n## " in pages[0][1])
    print(f"key: {a.key} | claim: {short(a.claim, 90)} | sentences searched: {len(scored)} with any overlap | "
          f"claim terms: {len(cw)} words, {len(cn)} numbers")
    for sc, _, lab, s, w, n in scored[: a.top]:
        where = "unpaginated" if unpag else f"p. {lab}"
        # show the sentence's own words, not the stems they were matched on
        shown = {tok for tok in re.findall(r"[\w؀-ۿ'-]+", s)
                 if any(re.sub(r"^(و|ف|ب|ل|ك)?(ال)", "", tok.lower()).startswith(st) for st in w)}
        terms = ", ".join(sorted(shown, key=str.lower) + sorted(n))
        print(f"\n[{where}] score {sc:.2f} | shared: {terms}\n  \"{s}\"")
    if not scored:
        print("NOT FOUND: no sentence shares a content word with the claim. The source may not support it.")
    print("\nThis is a finder, not a judge: read the passage in the PDF, then record it with "
          f"`claim add --key {a.key} --page N --quote \"...\" --claim \"...\"`.")
    return 0


# ---------------------------------------------------------------- claims

def locate_quote(pages, quote):
    """-> [page_label] where the quote occurs verbatim (normalised) within one page."""
    q = norm_q(quote)
    return [lab for lab, txt in pages if q and q in norm_q(txt)]


def locate_quote_across(pages, quote):
    """-> [(label_a, label_b)] consecutive page pairs whose joined text holds the quote
    while neither page holds it alone: the quote crosses that page break."""
    q = norm_q(quote)
    if not q or len(pages) < 2:
        return []
    norms = [norm_q(txt) for _, txt in pages]
    return [(pages[i][0], pages[i + 1][0]) for i in range(len(pages) - 1)
            if q not in norms[i] and q not in norms[i + 1] and q in norms[i] + norms[i + 1]]


def section_locator(text, quote):
    """For unpaginated text: 'Heading, para. N' of the paragraph holding the quote."""
    q = norm_q(quote)
    heading, n = "", 0
    for para in text.split("\n\n"):
        p = para.strip()
        if not p:
            continue
        if re.match(r"#{1,6}\s", p):
            heading, n = re.sub(r"^#+\s*", "", p), 0
            continue
        n += 1
        if q in norm_q(p):
            return f"{heading or 'body'}, para. {n}"
    return ""


def load_claims(path):
    return load_ledger(path) if os.path.exists(path) else []


def cmd_claim(a):
    if a.action == "list":
        claims = load_claims(a.claims)
        print(table([[c["key"], str(c.get("page") or c.get("locator") or ""), short(c["claim"], 50), short(c["quote"], 60),
                      c.get("added", "")] for c in claims if not a.key or c["key"] == a.key],
                    ["key", "page", "claim", "quote", "added"]))
        return 0
    path = os.path.join(a.fulltext, a.key + ".txt")
    if not os.path.exists(path):
        print(f"REFUSED: no full text for {a.key} ({path}). Fetch it first; a claim without the text is not evidence.")
        return 1
    quote = clean(a.quote)
    if len(quote.split()) < MIN_QUOTE_WORDS:
        print(f"REFUSED: the quote has fewer than {MIN_QUOTE_WORDS} words; quote a full clause so it can be found again.")
        return 1
    if re.search(r"\.\.\.|…|\[\.\.\.\]", a.quote):
        print("REFUSED: the quote contains an ellipsis. Record each verbatim part as its own claim.")
        return 1
    pages = load_fulltext(path)
    idx = load_index(a.fulltext).get(a.key, {})
    unpag = str(idx.get("numbering", "")).startswith("none")
    hits = locate_quote(pages, quote)
    across = locate_quote_across(pages, quote) if not hits else []
    if not hits and not across:
        print(f"REFUSED: the quote is not in {path} (whitespace, dashes and quote marks are ignored; words must match).")
        cw, cn = content_words(quote)
        best = max(((score_passage(cw, cn, s)[0], lab, s) for lab, s in page_sentences(pages)), default=None)
        if best and best[0] > 0:
            where = "unpaginated" if unpag else f"p. {best[1]}"
            print(f"  closest sentence [{where}, overlap {best[0]:.2f}]: \"{best[2]}\"")
        return 1
    if not hits and not getattr(a, "across_pages", False):
        pa, pb = across[0]
        print(f"REFUSED: the quote crosses a page break between pages {pa} and {pb}: add it as two claims "
              f"(the words on page {pa}, then the words on page {pb}), or pass --across-pages to accept it "
              f"(recorded as pages {pa}-{pb}).")
        return 1
    rec = {"key": a.key, "claim": clean(a.claim), "quote": quote, "page": None, "source_file": path, "added": TODAY}
    if not hits:                                    # --across-pages: the quote spans two consecutive pages
        pa, pb = across[0]
        span = f"{pa}-{pb}"
        given = str(a.page or "").strip().lstrip("pP. ")
        rec["page"], rec["page_numbering"] = span, idx.get("numbering")
        if given and given not in (pa, pb, span):
            rec["page_given"] = given
            print(f"WARNING: page corrected: the quote runs across pages {pa} and {pb} (you gave {given}); recorded pages {span}.")
        else:
            print(f"OK: quote found verbatim across the page break between pages {pa} and {pb} of {a.key}; "
                  f"recorded pages {span} (cite as pp. {span}).")
        if str(idx.get("numbering", "")).startswith("pdf"):
            print("  page numbers are PDF page indexes, not printed numbers: check the printed number before citing pp. N.")
    elif unpag:
        rec["locator"] = section_locator(pages[0][1], quote)
        rec["page_numbering"] = idx.get("numbering")
        print(f"OK: quote found in {a.key} (unpaginated XML). Locator for APA: {rec['locator'] or 'body'}.")
        if a.page:
            print("  --page ignored: this full text has no page numbers.")
    else:
        if not a.page:
            print(f"REFUSED: give --page (the quote is on page {', '.join(hits)} of {a.key}).")
            return 1
        given = str(a.page).strip().lstrip("pP. ")
        if given in hits:
            rec["page"] = given
            print(f"OK: quote found verbatim on page {given} of {a.key}.")
        else:
            rec["page"], rec["page_given"] = hits[0], given
            print(f"WARNING: page corrected: the quote is on page {hits[0]} (you gave {given}); recorded page {hits[0]}.")
        rec["page_numbering"] = idx.get("numbering")
        if str(idx.get("numbering", "")).startswith("pdf"):
            print("  page numbers are PDF page indexes, not printed numbers: check the printed number before citing p. N.")
        if len(hits) > 1:
            print(f"  note: the same words also occur on page(s) {', '.join(h for h in hits if h != rec['page'])}.")
    with open(a.claims, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"appended to {a.claims}: {a.key} | \"{short(quote, 70)}\" | claim: {short(rec['claim'], 70)}")
    return 0


# ---------------------------------------------------------------- audit

DESIGNS = [
    ("meta-analysis", r"meta-?analy\w*|systematic review|تحليل بعدي|مراجعة منهجية"),
    ("experimental", r"randomi[sz]ed|randomly assigned|random assignment|\bexperimental\b|\bexperiments?\b|manipulat\w*|"
                     r"control group|quasi-?experiment\w*|\bRCT\b|intervention group|pre-?test|post-?test|"
                     r"تجريبي\w*|شبه التجريبي\w*|عشوائي\w*"),
    ("qualitative", r"\bqualitative\b|\binterviews?\b|focus groups?|thematic analysis|grounded theory|phenomenolog\w*|ethnograph\w*|"
                    r"نوعي\w*|مقابلات|المقابلة"),
    ("correlational", r"cross-?sectional|correlational|\bsurvey\w*|questionnaires?|self-?report\w*|descriptive study|"
                      r"structural equation|\bregression\b|مسحي\w*|ارتباطي\w*|"
                      r"استبانة|استبيان|وصفي\w*"),
]
CAUSAL = re.compile(r"\b(causes?|caused|causing|leads? to|led to|increases?|increased|improves?|improved|results? in|resulted in|"
                    r"reduces?|reduced|decreases?|decreased|enhances?|enhanced|boosts?|lowers?|lowered)\b|"
                    r"يؤدي إلى|تؤدي إلى|يسبب|تسبب|"
                    r"يحسن|تحسن|يزيد|تزيد|يقلل|تقلل|"
                    r"يرفع|ترفع|يخفض|تخفض", re.I)


def detect_design(entry, fulltext_pages):
    """Heuristic design label from the abstract (weight 3) and the full text (weight 1).
    -> (design, signals) ; design 'unknown' when nothing matches."""
    abstract = clean(entry.get("abstract") or "")
    full = " ".join(t for _, t in fulltext_pages) if fulltext_pages else ""
    scores, signals = {}, {}
    for name, pat in DESIGNS:
        ha = [m.group(0).lower() for m in re.finditer(pat, abstract, re.I)]
        hf = [m.group(0).lower() for m in re.finditer(pat, full, re.I)] if full else []
        scores[name] = 3 * len(ha) + len(hf)
        if ha or hf:
            parts = [", ".join(sorted(set(ha))[:3]) + " (abstract)"] if ha else []
            parts += [f"{len(hf)} hit(s) in the full text" + ("" if ha else ": " + ", ".join(sorted(set(hf))[:3]))] if hf else []
            signals[name] = "; ".join(parts)
    if not any(scores.values()):
        return "unknown", "no design words in the abstract or full text"
    best = max(DESIGNS, key=lambda d: scores[d[0]])[0]
    # Experimental words beat survey words when both appear with real weight (a survey of an experiment's sample).
    if best == "correlational" and scores["experimental"] >= max(3, scores["correlational"] * 0.6) and \
            re.search(r"randomi[sz]|random assignment|control group|manipulat", abstract + full, re.I):
        best = "experimental"
    return best, signals.get(best, "")


def cited_sentences(manuscript, ledger):
    """-> [(line_no, sentence, [(snippet, [keys], who, year)])] for sentences with citations.

    `who` is whatever scholar.extract_citations returns as the author chunk ('Kirschner &
    Karpinski', 'Rosen et al.', 'الأنصاري وآخرون' or a bare surname): it is passed to
    scholar.ledger_match unchanged and printed as is, never split or parsed here."""
    with open(manuscript, encoding="utf-8") as f:
        text = f.read()
    body, _ = strip_references(text)
    out = []
    for ln, line in enumerate(body.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#") or re.fullmatch(r"\|?[\s:|\-]+\|?", s):
            continue
        for sent in split_sentences(s):
            cites = extract_citations(sent)
            if not cites:
                continue
            found = []
            for who, yr, snip in cites:
                keys = [h["key"] for h in ledger_match(who, yr, ledger)]
                found.append((snip, keys, who, yr))
            out.append((ln, sent, found))
    return out


def claim_state(key, claims, fulltext_dir, cache):
    """-> (live_claims, stale_claims, has_text). live = quote still verbatim in the text."""
    if key not in cache:
        path = os.path.join(fulltext_dir, key + ".txt")
        cache[key] = load_fulltext(path) if os.path.exists(path) else None
    pages = cache[key]
    mine = [c for c in claims if c.get("key") == key]
    if pages is None:
        return [], mine, False
    live = [c for c in mine if locate_quote(pages, c.get("quote", "")) or locate_quote_across(pages, c.get("quote", ""))]
    return live, [c for c in mine if c not in live], True


def best_claim(sentence, live):
    cw, cn = content_words(sentence)
    return max(live, key=lambda c: score_passage(cw, cn, c.get("claim", "") + " " + c.get("quote", ""))[0], default=None)


def cmd_audit(a):
    ledger = load_ledger(a.ledger)
    claims = load_claims(a.claims)
    by_key = {e["key"]: e for e in ledger}
    cache, fails, warns, infos = {}, [], [], []
    strict = getattr(a, "strict", False)
    sents = cited_sentences(a.manuscript, ledger)
    design_cache = {}
    n_cites = 0
    no_text = {}                                  # key -> [line numbers] cited without a full text (default mode)
    for ln, sent, found in sents:
        causal = CAUSAL.search(sent)
        for snip, keys, who, yr in found:
            n_cites += 1
            if not keys:
                fails.append(f"NOT IN LEDGER: {who} ({yr}) at line {ln}: \"{short(sent, 110)}\"")
                continue
            for key in keys:
                live, stale, has_text = claim_state(key, claims, a.fulltext, cache)
                if not has_text:
                    if strict:
                        fails.append(f"NO FULL TEXT: {key} cited at line {ln} has no {a.fulltext}/{key}.txt (fetch it or add the "
                                     f"PDF to papers/): \"{short(sent, 100)}\"")
                    else:
                        no_text.setdefault(key, []).append(ln)
                elif not live and stale:
                    fails.append(f"STALE QUOTE: every claim for {key} has a quote no longer verbatim in the full text "
                                 f"(line {ln}): \"{short(sent, 100)}\"")
                elif not live:
                    fails.append(f"NO EVIDENCE: {key} cited at line {ln} has no claim entry (quote + page) in {a.claims}: "
                                 f"\"{short(sent, 100)}\"")
                if key not in design_cache:
                    design_cache[key] = detect_design(by_key[key], cache.get(key))
                design, signal = design_cache[key]
                if causal and design == "correlational":
                    warns.append(f"CAUSAL LANGUAGE: \"{causal.group(0)}\" at line {ln} cites {key}, whose design looks "
                                 f"correlational ({signal}). A correlational source supports association, not causation: "
                                 f"reword (is associated with / predicts) or cite an experimental study. "
                                 f"Confirm the design in its Methods. \"{short(sent, 90)}\"")
    for e in ledger:
        if e.get("read_level") in ("full", "full_text") and not os.path.exists(os.path.join(a.fulltext, e["key"] + ".txt")):
            warns.append(f"READ IN FULL, NO TEXT: {e['key']} is marked read_level=full but has no {a.fulltext}/{e['key']}.txt; "
                         f"its quotes cannot be checked (books/scans: put the PDF in papers/ and fetch)")
    n_no_text = sum(len(v) for v in no_text.values())
    if no_text:
        where = ", ".join(f"{k} (line{'s' if len(v) > 1 else ''} {', '.join(str(x) for x in v)})" for k, v in sorted(no_text.items()))
        warns.append(f"NO FULL TEXT (cited at abstract/title level): {n_no_text} citation(s) of {len(no_text)} source(s) rest on "
                     f"the abstract or title, not on a verbatim quote: {where}. To check them against the text, put a PDF "
                     f"for each of these keys in papers/ and run fetch: {', '.join(sorted(no_text))}. "
                     f"--strict makes them FAIL.")
    for key, (design, signal) in sorted(design_cache.items()):
        infos.append(f"design (heuristic): {key} = {design}" + (f" [{signal}]" if signal else ""))
    print(f"manuscript: {a.manuscript} | cited sentences: {len(sents)} | citations: {n_cites} | claims: {len(claims)} | "
          f"ledger: {len(ledger)} | full texts in {a.fulltext}: {sum(1 for v in cache.values() if v)} | "
          f"mode: {'strict (no full text = FAIL)' if strict else 'default (no full text = WARN)'}")
    if not sents:
        print("NOTE  no sentence with an in-text citation was found: nothing to audit.")
    for x in fails:
        print("FAIL  " + x)
    for x in dict.fromkeys(warns):
        print("WARN  " + x)
    for x in infos:
        print("INFO  " + x)
    print("NOT CHECKED: whether each quote really supports the sentence it is attached to (read the quote next to the "
          "sentence in the trail), and whether the design label is right (regex on abstract/full text; confirm in Methods)"
          + ("" if strict else "; citations without a full text are counted, not verified (see the NO FULL TEXT warning)") + ".")
    print("RESULT: " + ("FAIL" if fails else "PASS") + f" ({len(fails)} fail, {len(set(warns))} warn, "
          f"{n_no_text} citation(s) without full text)")
    return 1 if fails else 0


# ---------------------------------------------------------------- trail

def evidence_lines(path):
    """-> [(line_text, [(label, value)])] for every line of analysis output that carries numbers."""
    out = []
    if not path or not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            pairs = evidence_numbers(texts=[line])
            if pairs:
                out.append((line, pairs))
    return out


def stat_matches(sentence, ev_lines):
    """-> [(item, kind, line or None)] for every statistic in the sentence."""
    res = []
    for item in numbers_in_text(sentence):
        hit, kind = None, None
        for line, pairs in ev_lines:
            k = number_supported(item, pairs)
            if k == "strict":
                hit, kind = line, k
                break
            if k and hit is None:
                hit, kind = line, k
        res.append((item, kind, hit))
    return res


def quote_label(c):
    if c.get("page"):
        pp = "pp." if "-" in str(c["page"]) else "p."         # 'N-N+1' = a quote that crosses a page break
        return f"{pp} {c['page']}" + (" (PDF page index)" if str(c.get("page_numbering", "")).startswith("pdf") else "")
    return c.get("locator") or "unpaginated"


def cmd_trail(a):
    ledger = load_ledger(a.ledger)
    claims = load_claims(a.claims)
    by_key = {e["key"]: e for e in ledger}
    cache = {}
    ev = evidence_lines(a.evidence)
    sents = cited_sentences(a.manuscript, ledger)
    md = ["# Evidence trail", "",
          f"Manuscript: {a.manuscript} | ledger: {a.ledger} | claims: {a.claims} | analysis output: "
          f"{a.evidence if ev else '(none given)'} | generated {TODAY}", "",
          "Every citation is listed with the verbatim quote and page recorded for it; every statistic with the "
          "analysis-output line that produced it. 'NO EVIDENCE' items must be fixed before submission.", ""]
    html_items = []
    n_ok = n_missing = n_stat_ok = n_stat_missing = 0
    for i, (ln, sent, found) in enumerate(sents, 1):
        md.append(f"## {i}. (line {ln})")
        md.append("")
        md.append(f"> {sent}")
        md.append("")
        spans = []                               # (snippet, [(key, apa, quote, label)])
        for snip, keys, who, yr in found:
            group = []
            if not keys:
                md.append(f"- **{who} ({yr})**: NOT IN LEDGER")
                n_missing += 1
                group.append((None, f"{who} ({yr})", "NOT IN LEDGER", ""))
            for key in keys:
                e = by_key[key]
                ref = e.get("apa") or apa(e)
                live, stale, has_text = claim_state(key, claims, a.fulltext, cache)
                c = best_claim(sent, live)
                md.append(f"- **{key}**: {ref}")
                if c:
                    md.append(f"  - \"{c['quote']}\" ({quote_label(c)}) | claim: {c['claim']} | recorded {c.get('added', '')}")
                    n_ok += 1
                    group.append((key, ref, c["quote"], quote_label(c)))
                else:
                    why = "no full text fetched" if not has_text else ("quote no longer verbatim" if stale else "no claim recorded")
                    md.append(f"  - NO EVIDENCE ({why})")
                    n_missing += 1
                    group.append((key, ref, f"NO EVIDENCE ({why})", ""))
            spans.append((snip, group))
        stats = stat_matches(sent, ev) if ev else []
        if stats:
            md.append("- statistics:")
            for item, kind, line in stats:
                shown = f"{item['op']}{item['value']}{'%' if item['pct'] else ''}"
                if line:
                    md.append(f"  - {item['label'] or '?'} {shown} -> `{line.strip()}`" + (" (weak: unlabelled match)" if kind == "weak" else "" if kind == "strict" else f" ({kind})"))
                    n_stat_ok += 1
                else:
                    md.append(f"  - {item['label'] or '?'} {shown} -> NOT FOUND in the analysis output")
                    n_stat_missing += 1
        md.append("")
        html_items.append((ln, sent, spans, stats))
    md.append(f"Summary: {n_ok} citation(s) with a verbatim quote, {n_missing} without; "
              f"{n_stat_ok} statistic(s) traced to the analysis output, {n_stat_missing} not found"
              + ("" if ev else " (no analysis output given)") + ".")
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md) + "\n")
    print(f"trail: {os.path.abspath(a.out)} | cited sentences: {len(sents)} | quotes: {n_ok} ok, {n_missing} missing | "
          f"statistics: {n_stat_ok} traced, {n_stat_missing} not found")
    if a.html:
        write_html(a.html, html_items, a.manuscript, n_ok, n_missing, n_stat_ok, n_stat_missing)
        print(f"html:  {os.path.abspath(a.html)} (hover a citation to see its quote)")
    return 0


HTML_HEAD = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Evidence trail</title>
<style>
body{font-family:Georgia,"Times New Roman",serif;max-width:60em;margin:2em auto;padding:0 1em;line-height:1.5;color:#222;background:#fff}
h1{font-size:1.6em} .meta{color:#666;font-size:.9em}
.sent{margin:.4em 0 .6em;padding:.6em .9em;background:#f7f7f2;border-left:4px solid #8a8}
.sent.missing{border-left-color:#c44}
.cite{position:relative;border-bottom:2px dotted #27a;cursor:help;background:#eef6fb}
.cite.missing{border-bottom-color:#c44;background:#fbeeee}
.cite:hover::after{content:attr(data-quote);position:absolute;left:0;top:1.6em;z-index:9;width:32em;max-width:80vw;
 background:#fffbe6;border:1px solid #b9a;box-shadow:0 2px 8px rgba(0,0,0,.2);padding:.6em .8em;font-size:.9em;
 white-space:pre-wrap;color:#222;direction:ltr;text-align:left}
.cite:hover::after{direction:inherit;text-align:inherit}
ul{margin:.2em 0 .8em} li{margin:.15em 0} .q{color:#363} .no{color:#a22;font-weight:bold} .stat{font-family:Consolas,monospace;font-size:.9em}
[dir=rtl]{text-align:right}
</style></head><body>
"""


def write_html(path, items, manuscript, n_ok, n_missing, n_stat_ok, n_stat_missing):
    esc = lambda s: html.escape(str(s), quote=True)
    out = [HTML_HEAD, f"<h1>Evidence trail</h1><p class='meta'>Manuscript: {esc(manuscript)} | generated {TODAY} | "
           f"{n_ok} quotes recorded, <b>{n_missing} missing</b> | {n_stat_ok} statistics traced, {n_stat_missing} not found. "
           "Hover a highlighted citation to read its verbatim quote and page.</p>"]
    for ln, sent, spans, stats in items:
        rtl = bool(ARABIC_RE.search(sent))
        shown = esc(sent)
        missing_any = False
        for snip, group in spans:
            qtext = "\n\n".join(f"{(k + ': ') if k else ''}{q}" + (f" ({lab})" if lab else "") for k, _, q, lab in group)
            miss = any(q.startswith("NO EVIDENCE") or q == "NOT IN LEDGER" for _, _, q, _ in group)
            missing_any = missing_any or miss
            span = f"<span class='cite{' missing' if miss else ''}' data-quote=\"{esc(qtext)}\" title=\"{esc(qtext)}\">{esc(snip)}</span>"
            shown = shown.replace(esc(snip), span, 1)
        out.append(f"<div class='sent{' missing' if missing_any else ''}'{' dir=\"rtl\"' if rtl else ''}>"
                   f"<span class='meta'>line {ln}</span><br>{shown}</div><ul>")
        for snip, group in spans:
            for k, ref, q, lab in group:
                if q.startswith("NO EVIDENCE") or q == "NOT IN LEDGER":
                    out.append(f"<li>{esc(ref)}: <span class='no'>{esc(q)}</span></li>")
                else:
                    out.append(f"<li>{esc(ref)}<br><span class='q'{' dir=\"rtl\"' if ARABIC_RE.search(q) else ''}>"
                               f"&ldquo;{esc(q)}&rdquo; ({esc(lab)})</span></li>")
        for item, kind, line in stats:
            v = f"{item['op']}{item['value']}{'%' if item['pct'] else ''}"
            if line:
                out.append(f"<li class='stat'>{esc(item['label'] or '?')} {esc(v)} &rarr; {esc(line.strip())}"
                           + (" (weak)" if kind == "weak" else "") + "</li>")
            else:
                out.append(f"<li class='stat'>{esc(item['label'] or '?')} {esc(v)} &rarr; <span class='no'>NOT FOUND in analysis output</span></li>")
        out.append("</ul>")
    out.append("</body></html>\n")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(out))


# ---------------------------------------------------------------- selftest

def make_pdf(path, pages_text):
    doc = fitz.open()
    for txt in pages_text:
        page = doc.new_page()
        y = 72
        for line in txt.split("\n"):
            page.insert_text((72, y), line, fontsize=10)
            y += 14
    doc.save(path)
    doc.close()


def corrupt_pdf(src, dst):
    """Write a broken copy of a real PDF for the negative control. First choice: truncate
    the file (what a cut-off download looks like), at the first cut point MuPDF cannot
    repair; if this MuPDF repairs every truncation, inflate /Count in the page tree so a
    page the tree promises does not exist (the 'cannot find page N in page tree' family).
    -> description of the corruption used."""
    with open(src, "rb") as f:
        data = f.read()
    for pct in range(90, 9, -5):
        cut = data[: len(data) * pct // 100]
        if read_pdf_pages(cut)[2]:
            with open(dst, "wb") as f:
                f.write(cut)
            return f"truncated to {pct}% ({len(cut)} of {len(data)} bytes)"
    m = re.search(rb"/Type\s*/Pages[^>]*?/Count\s+(\d+)", data)
    if not m:                                   # page tree inside an object stream: fall back to a hard cut
        with open(dst, "wb") as f:
            f.write(data[: len(data) // 2])
        return "truncated to 50% (page tree not in plain text; MuPDF repaired every stepped truncation)"
    n = int(m.group(1))
    broken = data[: m.start(1)] + str(n + 2).encode() + data[m.end(1):]
    with open(dst, "wb") as f:
        f.write(broken)
    return f"page tree /Count raised from {n} to {n + 2} (MuPDF repaired every truncation)"


def run(fn, ns):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fn(ns)
    return code or 0, buf.getvalue()


def cmd_selftest(a):
    if fitz is None:
        print("PyMuPDF is missing: pip install pymupdf")
        return 1
    root = tempfile.mkdtemp(prefix="evidence-selftest-")
    papers, full = os.path.join(root, "papers"), os.path.join(root, "fulltext")
    os.makedirs(papers)
    ledger = os.path.join(root, "sources.jsonl")
    claims = os.path.join(root, "claims.jsonl")
    manuscript = os.path.join(root, "paper.md")
    evid = os.path.join(root, "output.txt")
    title_a = "Sleep duration and grade point average among undergraduates"
    make_pdf(os.path.join(papers, "random-name-A.pdf"), [
        f"{title_a}\nAmal Selftest and Omar Control\nJournal of Synthetic Studies, 12(1), 101-103\nhttps://doi.org/10.9999/selftest.2020.1",
        "Methods\nA cross-sectional survey of 300 undergraduates completed a questionnaire on sleep.\n"
        "Results\nStudents who slept longer reported higher grade point averages (r = .31, p < .001).\n"
        "Sleep duration was positively associated with GPA in this sample.\n"
        "The sample was drawn from a single university, which limits",
        "the generalisation of these findings to other settings.\n"
        "Discussion\nThe association does not establish causation because the design was correlational.\nReferences"])
    make_pdf(os.path.join(papers, "random-name-B.pdf"), [
        "A randomized experiment on study breaks\nNoor Experiment\n",
        "Participants were randomly assigned to a break condition or a control group.\n"
        "The break condition improved recall scores by twelve percent."])
    # a real 4-page PDF, then a broken copy of it in papers/ (named after its key so it can be attributed)
    good_c = os.path.join(root, "corrupt-source-good.pdf")
    make_pdf(good_c, ["A paper whose PDF arrived broken\nSami Corrupt\nhttps://doi.org/10.9999/corrupt.2022.1\n"]
             + [f"Page {i} of the broken paper with some running text." for i in (2, 3, 4)])
    corruption = corrupt_pdf(good_c, os.path.join(papers, "corrupt2022-download.pdf"))
    entries = [
        {"key": "corrupt2022", "doi": "10.9999/corrupt.2022.1", "type": "journal-article",
         "title": "A paper whose PDF arrived broken", "authors": [{"family": "Corrupt", "given": "Sami"}], "year": 2022,
         "container": "Journal of Synthetic Studies", "pages": "1-4", "abstract": "A broken download.",
         "read_level": "abstract", "retraction": {"status": "ok", "notices": []}},
        {"key": "selftest2020", "doi": "10.9999/selftest.2020.1", "type": "journal-article", "title": title_a,
         "authors": [{"family": "Selftest", "given": "Amal"}, {"family": "Control", "given": "Omar"}], "year": 2020,
         "container": "Journal of Synthetic Studies", "volume": "12", "issue": "1", "pages": "101-103",
         "abstract": "A cross-sectional survey of 300 undergraduates using a questionnaire found sleep was associated with GPA.",
         "read_level": "full", "retraction": {"status": "ok", "notices": []}},
        {"key": "experiment2021", "doi": None, "type": "journal-article", "title": "A randomized experiment on study breaks",
         "authors": [{"family": "Experiment", "given": "Noor"}], "year": 2021, "container": "Journal of Synthetic Studies",
         "pages": "1-2", "abstract": "Participants were randomly assigned to a break condition or a control group.",
         "read_level": "full", "retraction": {"status": "ok", "notices": []}},
        {"key": "book1990", "doi": None, "isbn": "9780000000000", "type": "book", "title": "A book nobody scanned",
         "authors": [{"family": "Book", "given": "Hana"}], "year": 1990, "publisher": "Nowhere Press", "abstract": "",
         "read_level": "full", "retraction": {"status": "n/a", "notices": []}},
    ]
    with open(ledger, "w", encoding="utf-8") as f:
        for e in entries:
            e["apa"] = apa(e)
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    with open(manuscript, "w", encoding="utf-8") as f:
        f.write("# Test\n\n## Literature\n\nLonger sleep increases GPA (Selftest & Control, 2020). "
                "Study breaks improved recall (Experiment, 2021). Theory comes from Book (1990). "
                "Sleep correlated with GPA, r(197) = .31, p < .001 (Selftest & Control, 2020).\n\n"
                "أشارت دراسة Selftest (2020) إلى أن النوم "
                "يؤدي إلى رفع المعدل.\n")
    with open(evid, "w", encoding="utf-8") as f:
        f.write("corr.sleep~gpa.r = 0.311146\ncorr.sleep~gpa.df = 197\ncorr.sleep~gpa.p = 7.70809e-06\n")
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, bool(cond), detail))
        print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))

    def claim_ns(**kw):
        ns = dict(action="add", key="selftest2020", page=None, quote="", claim="", across_pages=False, claims=claims, fulltext=full)
        ns.update(kw)
        return argparse.Namespace(**ns)

    def audit_ns(**kw):
        ns = dict(manuscript=manuscript, ledger=ledger, claims=claims, fulltext=full, strict=False)
        ns.update(kw)
        return argparse.Namespace(**ns)

    # fetch: local PDFs only (DOI match for A, title match for B, no network for the book); the corrupt PDF is first
    # in the ledger, so the batch must survive it and go on to A and B
    err_buf = io.StringIO()
    with contextlib.redirect_stderr(err_buf):
        code, out = run(cmd_fetch, argparse.Namespace(ledger=ledger, papers=papers, out=full, key=None, email=None, force=False))
    idx = load_index(full)
    check(f"fetch survives a corrupt PDF ({corruption}) and records 'PDF unreadable' for its key",
          "| PDF unreadable: " in out and str(idx.get("corrupt2022", {}).get("status", "")).startswith("PDF unreadable: ")
          and not os.path.exists(os.path.join(full, "corrupt2022.txt")), out + err_buf.getvalue())
    check("fetch matches PDF A by printed DOI", "DOI printed in the PDF" in out and os.path.exists(os.path.join(full, "selftest2020.txt")), out)
    check("fetch matches PDF B by title", "title on page 1" in out and os.path.exists(os.path.join(full, "experiment2021.txt")), out)
    check("fetch leaves the book alone (no DOI, no PDF)", "no DOI" in out and not os.path.exists(os.path.join(full, "book1990.txt")), out)
    check("printed page numbers from the ledger range (101-103)", idx["selftest2020"]["numbering"].startswith("printed")
          and load_fulltext(os.path.join(full, "selftest2020.txt"))[1][0] == "102", json.dumps(idx.get("selftest2020")))
    # quote finder
    code, out = run(cmd_quote, argparse.Namespace(key="selftest2020", claim="sleep is associated with higher GPA", top=2, fulltext=full))
    first_hit = out.split("\n\n")[1]
    check("quote finder ranks the GPA sentence first with its page", "[p. 102]" in first_hit and "associated with GPA" in first_hit, out)
    # claim add: positive
    good = "Sleep duration was positively associated with GPA in this sample"
    code, out = run(cmd_claim, claim_ns(page="102", quote=good, claim="sleep associated with GPA"))
    check("claim add accepts a verbatim quote on the right page", code == 0 and "OK: quote found verbatim on page 102" in out, out)
    # claim add: wrong page -> warning + correction
    code, out = run(cmd_claim, claim_ns(page="101", quote="Sleep duration was positively  associated with GPA in this sample",
                                        claim="dup with wrong page"))
    check("claim add corrects a wrong page with a warning", code == 0 and "WARNING: page corrected" in out and "page 102" in out, out)
    # negative control: quote not in the text
    code, out = run(cmd_claim, claim_ns(page="102", quote="Sleep duration caused a large rise in GPA for everyone", claim="fabricated"))
    check("claim add REFUSES a quote that is not in the text", code == 1 and "REFUSED" in out, out)
    # negative control: ellipsis
    code, out = run(cmd_claim, claim_ns(page="102", quote="Sleep duration was ... associated with GPA in this sample", claim="elided"))
    check("claim add REFUSES an elided quote", code == 1 and "ellipsis" in out, out)
    check("claims.jsonl holds exactly the 2 accepted claims", len(load_claims(claims)) == 2)
    # a quote that crosses the page break between 102 and 103: named, then accepted with --across-pages
    span_q = "a single university, which limits the generalisation of these findings"
    code, out = run(cmd_claim, claim_ns(page="102", quote=span_q, claim="single-site sample limits generalisation"))
    check("claim add names the page break a quote crosses (102 to 103) and asks for --across-pages",
          code == 1 and "crosses a page break between pages 102 and 103" in out and "--across-pages" in out, out)
    code, out = run(cmd_claim, claim_ns(page="102", quote=span_q, claim="single-site sample limits generalisation", across_pages=True))
    span_rec = [c for c in load_claims(claims) if c["quote"] == span_q]
    check("claim add --across-pages accepts it and records pages 102-103",
          code == 0 and "across the page break between pages 102 and 103" in out and span_rec and span_rec[0]["page"] == "102-103", out)
    live, stale, _ = claim_state("selftest2020", load_claims(claims), full, {})
    check("a cross-page claim counts as live for the audit (not STALE)", any(c["quote"] == span_q for c in live) and not stale)
    code, out = run(cmd_claim, claim_ns(page="102", quote="the generalisation of these findings, which limits a single university",
                                        claim="reordered words: on no page and on no page pair", across_pages=True))
    check("claim add still REFUSES words found on no page and on no page pair", code == 1 and "is not in" in out, out)
    # audit, default mode: experiment2021 (full text, no claim) -> FAIL; book1990 (no full text) -> WARN with a count;
    # causal verb on correlational -> WARN; book read_level full no text -> WARN
    code, out = run(cmd_audit, audit_ns())
    check("audit FAILS a cited key with no claim", code == 1 and "NO EVIDENCE: experiment2021" in out, out)
    check("audit WARNS on causal 'increases' for the cross-sectional survey", "CAUSAL LANGUAGE: \"increases\"" in out and "selftest2020" in out, out)
    check("audit WARNS on Arabic causal يؤدي إلى", "يؤدي إلى" in out and "CAUSAL" in out, out)
    check("audit does not flag 'improved' for the experimental source", "CAUSAL LANGUAGE: \"improved\"" not in out, out)
    check("audit WARNS read_level=full without full text (book)", "READ IN FULL, NO TEXT: book1990" in out, out)
    check("audit (default) WARNS, not FAILS, a citation with no full text and counts it",
          "WARN  NO FULL TEXT (cited at abstract/title level): 1 citation(s) of 1 source(s)" in out and "FAIL  NO FULL TEXT" not in out
          and "1 citation(s) without full text" in out, out)
    check("audit (default) names the key that needs a PDF", "run fetch: book1990" in out, out)
    code, out = run(cmd_audit, audit_ns(strict=True))
    check("audit --strict FAILS the book citation (no full text)", code == 1 and "FAIL  NO FULL TEXT: book1990" in out
          and "NO FULL TEXT (cited at abstract/title level)" not in out, out)
    # the manuscript can be given as --manuscript FILE (through the real parser)
    ns = parse_cli(["audit", "--manuscript", manuscript, "--ledger", ledger, "--claims", claims, "--fulltext", full])
    code, out = run(cmd_audit, ns)
    check("audit accepts --manuscript FILE as well as the positional form", ns.manuscript == manuscript and "cited sentences: " in out, out)
    # add the missing claim, re-audit the experiment part: it should no longer fail
    code, out = run(cmd_claim, claim_ns(key="experiment2021", page="2", quote="The break condition improved recall scores by twelve percent",
                                        claim="breaks improved recall"))
    code, out = run(cmd_audit, audit_ns())
    check("after adding its claim, experiment2021 no longer fails", "NO EVIDENCE: experiment2021" not in out, out)
    # stale quote: edit the full text so the quote disappears
    p = os.path.join(full, "experiment2021.txt")
    with open(p, encoding="utf-8") as f:
        t = f.read()
    with open(p, "w", encoding="utf-8") as f:
        f.write(t.replace("twelve percent", "ten percent"))
    code, out = run(cmd_audit, audit_ns())
    check("audit FAILS when a recorded quote is no longer verbatim (STALE QUOTE)", "STALE QUOTE" in out and "experiment2021" in out, out)
    # trail
    trail_md, trail_html = os.path.join(root, "trail.md"), os.path.join(root, "trail.html")
    code, out = run(cmd_trail, argparse.Namespace(manuscript=manuscript, ledger=ledger, claims=claims, fulltext=full,
                                                  evidence=evid, out=trail_md, html=trail_html))
    with open(trail_md, encoding="utf-8") as f:
        tmd = f.read()
    with open(trail_html, encoding="utf-8") as f:
        thtml = f.read()
    check("trail lists the quote with its page", good in tmd and "(p. 102)" in tmd, tmd[:800])
    check("trail traces r = .31 to the analysis line", "corr.sleep~gpa.r = 0.311146" in tmd, tmd)
    check("trail marks the missing book evidence", "NO EVIDENCE" in tmd and "book1990" in tmd, tmd)
    check("html trail is self-contained with hover quotes", "data-quote=" in thtml and good in thtml and "http" not in thtml.split("<body>")[0].replace("http-equiv", ""), thtml[:500])
    bad = [c for c in checks if not c[1]]
    print(f"selftest folder: {root}")
    print("RESULT: " + ("FAIL" if bad else "PASS") + f" ({len(checks) - len(bad)}/{len(checks)} checks)")
    return 1 if bad else 0


# ---------------------------------------------------------------- cli

def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="full texts for the ledger: papers/, Unpaywall, OpenAlex OA, Europe PMC, arXiv",
                       epilog="example: evidence.py fetch --ledger sources.jsonl --papers papers --out fulltext")
    f.add_argument("--ledger", default="sources.jsonl")
    f.add_argument("--papers", default="papers", help="folder of PDFs the user supplied (matched by DOI or title)")
    f.add_argument("--out", default="fulltext")
    f.add_argument("--key", nargs="*", help="only these ledger keys")
    f.add_argument("--email", help="your email for Unpaywall (or set RESEARCH_MAILTO); placeholders are rejected")
    f.add_argument("--force", action="store_true", help="re-fetch keys that already have a text file")

    q = sub.add_parser("quote", help="find the passages that best support a claim (verbatim, with page)",
                       epilog='example: evidence.py quote --key kolhar2021 --claim "social media delays bedtime" --top 3')
    q.add_argument("--key", required=True)
    q.add_argument("--claim", required=True)
    q.add_argument("--top", type=int, default=3)
    q.add_argument("--fulltext", default="fulltext")

    c = sub.add_parser("claim", help="record a claim backed by a verbatim quote (add) or list claims (list)",
                       epilog='example: evidence.py claim add --key kolhar2021 --page 2218 --quote "..." --claim "..."')
    c.add_argument("action", choices=["add", "list"])
    c.add_argument("--key")
    c.add_argument("--page", help="printed page (or PDF page index when the index says so); not needed for XML texts")
    c.add_argument("--quote", help="verbatim words from the full text, no ellipsis")
    c.add_argument("--claim", help="what the sentence in the manuscript says, in your words")
    c.add_argument("--across-pages", action="store_true",
                   help="accept a quote that runs across a page break (recorded as pages N-N+1); default: refused with the two pages named")
    c.add_argument("--claims", default="claims.jsonl")
    c.add_argument("--fulltext", default="fulltext")

    au = sub.add_parser("audit", help="every cited sentence with a full text needs a live verbatim claim; no full text = WARN "
                                      "(--strict: FAIL); causal verbs on correlational sources warn",
                        epilog="example: evidence.py audit paper.md --ledger sources.jsonl --claims claims.jsonl --fulltext fulltext")
    au.add_argument("manuscript", nargs="?", help="the manuscript (.md or .txt); or give it as --manuscript FILE")
    au.add_argument("--manuscript", dest="manuscript_opt", metavar="FILE", help="same as the positional manuscript")
    au.add_argument("--ledger", default="sources.jsonl")
    au.add_argument("--claims", default="claims.jsonl")
    au.add_argument("--fulltext", default="fulltext")
    au.add_argument("--strict", action="store_true",
                    help="a citation whose source has no full text FAILS (default: WARN, counted as cited at abstract/title level)")

    t = sub.add_parser("trail", help="evidence appendix: citation -> quote + page; statistic -> analysis line",
                       epilog="example: evidence.py trail paper.md --out evidence-trail.md --html evidence-trail.html")
    t.add_argument("manuscript", nargs="?", help="the manuscript (.md or .txt); or give it as --manuscript FILE")
    t.add_argument("--manuscript", dest="manuscript_opt", metavar="FILE", help="same as the positional manuscript")
    t.add_argument("--out", default="evidence-trail.md")
    t.add_argument("--html", help="also write a self-contained HTML version (quote on hover)")
    t.add_argument("--ledger", default="sources.jsonl")
    t.add_argument("--claims", default="claims.jsonl")
    t.add_argument("--fulltext", default="fulltext")
    t.add_argument("--evidence", default=os.path.join("analysis", "output.txt"), help="analysis output ('label = value' lines)")

    sub.add_parser("selftest", help="offline check with synthetic PDFs: positive cases and negative controls")
    return p


def parse_cli(argv=None):
    """Parsed, validated arguments (the selftest feeds real command lines through this too)."""
    p = build_parser()
    a = p.parse_args(argv)
    if a.cmd == "claim" and a.action == "add" and not (a.key and a.quote and a.claim):
        p.error("claim add needs --key, --quote and --claim (and --page for paginated texts)")
    if a.cmd in ("audit", "trail"):
        a.manuscript = a.manuscript or a.manuscript_opt
        if not a.manuscript:
            p.error(f"{a.cmd} needs the manuscript: `{a.cmd} paper.md` or `{a.cmd} --manuscript paper.md`")
        if a.manuscript and a.manuscript_opt and a.manuscript != a.manuscript_opt:
            p.error("the manuscript was given twice with different files (positional and --manuscript)")
    return a


def main():
    a = parse_cli()
    fn = globals()["cmd_" + a.cmd]
    try:
        sys.exit(fn(a) or 0)
    except HTTPError as e:
        sys.exit(f"API error: {e} {e.body[:200] if isinstance(e.body, str) else ''}")


if __name__ == "__main__":
    main()
