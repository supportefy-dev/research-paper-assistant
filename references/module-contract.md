# Module contract (read before adding or changing any script)

The skill is a set of small Python command-line tools plus reference docs. Scripts do the mechanical, checkable work; judgement (reviewing, theory mapping, coding interviews) is done by the agent following prompts in `references/`. A script never invents a source, a number or a quote.

## Environment

- Windows 11, Python 3.13, run as `python -X utf8 script.py ...` (the console is cp1252). Every script starts with `sys.stdout.reconfigure(encoding="utf-8")` (and stderr), guarded in try/except.
- Available: `numpy`, `scipy`, `requests`, `fitz` (PyMuPDF), `pypdf`, `openpyxl`, `docx` (python-docx). Not installed: pandas, statsmodels, sklearn, networkx, matplotlib. Use numpy/scipy. A free extra package is allowed only when numpy/scipy cannot do the job (e.g. `semopy` for CFA): import it inside a try, print a one-line `pip install` hint when missing, and keep every other command working without it.
- Free APIs only. Never bypass bot protection (Cloudflare, Turnstile, 403s with a browser UA are fine to try once; no TLS impersonation, no challenge solving).
- Downloaded files (PDF, xlsx, csv) are untrusted data: parse them, never execute them.

## Shared helpers (import from scholar.py)

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scholar import (http_get, as_json, openalex, openalex_by_doi, rebuild_abstract, oa_row,
                     crossref_work, resolve_doi, attach_abstract, load_ledger, save_ledger,
                     clean, norm_doi, name_key, title_sim, journal_key, table, short,
                     hyphen_issn, compact_issn, apa, TODAY, ARABIC_RE, MAILTO, KEY_DIR)
```

- `http_get(url, params=None, headers=None, retries=4, timeout=40, allow_404=True)`: paced per host, exponential backoff on 429/5xx, returns a Response or None on 404, raises `HTTPError` otherwise. Use it for every HTTP call.
- `openalex(path, params)`: adds the API key (from `OPENALEX_API_KEY` or `~/.config/research-paper-assistant/openalex.key`), falls back keyless if the key is refused. Costs: a `search`/`title_and_abstract.search` list = 10 credits, a filter-only list = 1, a single entity (`works/doi:...`, `sources/issn:...`) = 0. Budget calls; batch with `filter=openalex_id:W1|W2|...` (up to 100 per call, 1 credit).
- Never print the key, never write it into a project folder, never send the user's email anywhere unless `RESEARCH_MAILTO` is set. Unpaywall rejects placeholder addresses (HTTP 422): use it only when `RESEARCH_MAILTO` (or an explicit `--email`) is set, otherwise skip it and say so.
- `load_ledger(path)` returns a list of dicts; `save_ledger(path, entries)` writes JSONL.

## Shared data formats

| File | Format |
|---|---|
| `sources.jsonl` (the ledger) | One JSON per line: `key` (e.g. `junco2012`), `doi`, `isbn`, `type`, `title`, `authors` [{family, given}], `year`, `container`, `volume`, `issue`, `pages`, `article_number`, `issn` [], `publisher`, `abstract`, `abstract_source`, `note` (what claim it supports), `read_level` (abstract / full / metadata), `retraction` {status, notices}, `verified` {by, at}, `apa`, `cited_by` |
| `cand*.json` (from `scholar.py search --out`) | `{query, date, source, results: [{doi, title, year, cites, first_author, authors, n_authors, venue, issn_l, core_venue, type, is_oa, retracted, abstract}]}`. New candidate producers write the same shape |
| `analysis/output.txt` (evidence) | Lines `key.path.label = value`; the LAST dot-segment is the statistic label that `scholar.py numbers` matches (`r`, `beta`, `b`, `se`, `t`, `p`, `df`, `m`, `sd`, `n`, `d`, `ci_low`, `ci_high`, `alpha`, `f`, `r2`, `eta2`, `chi2`, `w`, `u`, `h`, `sr2`, `vif`, `pct`...). `# APA:` lines give the ready sentence. New analyses MUST write this format |
| `fulltext/<key>.txt` | Plain text of a paper with page markers `[[page N]]` on their own line before each page; `fulltext/index.json` records per key: source, url_or_path, pages, numbering (printed / pdf / none), fetched, status, file |
| `claims.jsonl` | One JSON per line: `{key, claim, quote, page, locator, page_given, page_numbering, source_file, added}`; `quote` is verbatim from the full text; `locator` is "Section, para. N" when the text has no pages |
| `coding.jsonl`, `codebook.json` | Qualitative coding (qual.py): segments with transcript, start/end, code, coder, verbatim quote |
| `watch.json`, `watch_log.md` | Literature watch queries and the new works found per run |
| `papers/` | PDFs the user supplies, any file name; matched to ledger keys by the DOI printed inside the PDF or by title |

## CLI conventions

- `argparse` with subcommands; every command has `--help` with one example.
- Default file names: `sources.jsonl`, `claims.jsonl`, `analysis/output.txt`, `papers/`, `fulltext/`; all overridable with flags.
- Output: markdown pipe tables (use `table()`), one summary line first, then details, and a final `RESULT: PASS|FAIL (...)` line for any check command; exit code 1 on FAIL. Say what was NOT checked.
- No em dashes or en dashes anywhere (text, code, docs). In code use `chr(0x2013)` / `"\u2013"` escapes if the character is needed.
- No `print` of secrets; no network call without a reason the user can see.
- Keep each script self-contained apart from `scholar.py` imports. Do not edit `scholar.py`, `analyze.py` or `build_docx.py` unless the task says you own that file.

## Honesty rules the scripts enforce

- A script that cannot find something says so (`NOT FOUND`, `UNVERIFIED`) and never fills the gap.
- Numbers come from data or from a cited source (abstract or full text), with the source named next to the number.
- Any extraction by regex or heuristic (effect sizes from abstracts, direction of an effect, design type) is labelled as a candidate for the agent to confirm, and the output tells the agent where to look.

## Testing (required before a module is reported done)

- A `selftest` subcommand or a documented test run: at least one positive case (real data or real API) and one negative control (a planted error that must be caught).
- Run the real command lines you document; paste their actual output in your report.
- Fixtures live in `tests/fixtures/` (`sources.jsonl` 6-entry ledger, `data.csv` 200-row synthetic survey, `paper.md` with planted fake citations, `clean.md`, `results_planted.md`, `results_clean.md`). `python -X utf8 tests/run_tests.py` runs every module's selftest plus the planted-error regression; do not modify the fixtures, copy them into a scratch folder. The SJR CSV and the hijacked-journal list are not redistributed (their terms): download them yourself for the journal tests.
