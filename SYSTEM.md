# Research Paper Assistant - System Architecture

This document describes how Research Paper Assistant's parts fit together: the agent instructions (`SKILL.md` and `references/`), the 18 scripts in `scripts/`, the files they share in a research project folder, and the free APIs behind them.

---

## Overview

Research Paper Assistant is three layers connected only through files in the user's research project folder. There is no server, no database and no long-running process.

```text
 +------------------------------+        reads        +-------------------------------+
 | Claude Code + SKILL.md       |-------------------->| references/*.md               |
 | authorship mode, stage,      |                     | stages, integrity, theories,  |
 | judgement, writing           |                     | reviewer prompts, presets     |
 +--------------+---------------+                     +-------------------------------+
                |
                | runs: python -X utf8 scripts/<tool>.py <command>
                v
 +------------------------------+   HTTPS via scholar.http_get()   +---------------------+
 | scripts/*.py (18 CLIs)       |--------------------------------->| free public APIs    |
 | scholar.py = shared helpers  |                                  | OpenAlex, Crossref, |
 +--------------+---------------+                                  | Europe PMC, ...     |
                |                                                  +---------------------+
                | read and write
                v
 +---------------------------------------------------------------------------------------+
 | project folder: cand*.json, sources.jsonl, claims.jsonl, fulltext/, papers/,          |
 | analysis/output.txt, matrix.md, shortlist.md, the manuscript .md                      |
 +---------------------------------------------------------------------------------------+
```

**Agent layer: `SKILL.md`** - tells Claude Code who may get which help (Step 0, authorship modes A to D), which stage a request belongs to, which script to run, and the hard rules: sources from the ledger only, a specific finding only with a quote, numbers only from analysis output, AI use disclosed. It reads the `references/` file for the stage at hand and does the judgement work (reviewing, theory mapping, coding interviews). It never types a reference, a quote or a statistic from memory.

**Scripts: `scripts/*.py`** - 18 self-contained `argparse` command-line tools that do the mechanical, checkable work. `scholar.py` also holds the shared helpers the others import. A script never invents a source, a number or a quote: what it cannot find it reports as `NOT FOUND` or `UNVERIFIED`, and a regex extraction is labelled as a candidate.

**Project folder** - the single source of truth, one folder per paper. Every script reads and writes it through default file names that flags can override. Nothing about a project is stored in the skill's own folder: `.gitignore` keeps root-level `sources.jsonl`, `claims.jsonl`, `fulltext/`, `papers/` and `analysis/` out of the repo.

---

## Component Detail

### `scripts/` - the 18 tools, by stage

Run from the project folder, with `python -X utf8` (Windows consoles are cp1252):

```bash
cd "<project>" && python -X utf8 ~/.claude/skills/research-paper-assistant/scripts/scholar.py --help
```

Every script has `--help` with examples; 13 have a `selftest` command that `tests/run_tests.py` runs. Each script is listed once, at the stage where it is first used.

| Stage | Script | Commands | Network |
|---|---|---|---|
| 1. Topic and gap | `scholar.py` | `search`, `verify`, `add`, `fix`, `book`, `abstract`, `cite`, `refs`, `list`, `audit`, `numbers`, `journal`, `journals` | OpenAlex, Crossref, doi.org, Semantic Scholar, Europe PMC, Open Library, DOAJ; `list`, `refs`, `audit`, `numbers` and `journals` are offline |
| 1 | `gapmap.py` | `run`, `selftest` | OpenAlex, 2 list calls at most; none with `--in` |
| 1 | `comap.py` | `build`, `selftest` | OpenAlex filter lists, about 4 credits per 100 input papers |
| 2. Literature | `snowball.py` | `run`, `selftest` | OpenAlex, 1 credit per backward batch or forward page |
| 2 | `evidence.py` | `fetch`, `quote`, `claim add` / `claim list`, `audit`, `trail`, `selftest` | `fetch` only: Unpaywall (with `RESEARCH_MAILTO`), OpenAlex OA locations, Europe PMC, arXiv, open-access PDF hosts |
| 4. Design | `instruments.py` | `find`, `pilot`, `protocol`, `selftest` | `find`: OpenAlex, 2 searches; `protocol`: Crossref |
| 4 | `effects.py` | `harvest`, `power`, `justify`, `selftest` | none |
| 5. Analysis | `autopsy.py` | `careless`, `grim`, `harman`, `statcheck`, `selftest` | none |
| 5 | `analyze.py` | `describe`, `freq`, `corr`, `regress`, `ttest`, `anova`, `alpha` | none |
| 5 | `analyze_sem.py` | `mediate`, `moderate`, `cfa`, `pls`, `selftest` | none |
| 5 | `qual.py` | `transcribe`, `codebook`, `code`, `agreement`, `themes`, `quote`, `selftest` | none (whisper.cpp and ffmpeg run locally) |
| 7. Journal | `journalfit.py` | `profile`, `fit`, `compare`, `selftest` | `profile`, `fit`: OpenAlex; `fit --cached-only` makes no call |
| 8. Pre-submission | `similarity.py` | `check`, `self`, `selftest` | none |
| 8 | `reviews.py` | `pull`, `classify`, `selftest` | `pull`: OpenReview, eLife, F1000Research, PeerJ (tried once, reported as blocked) |
| 8 | `build_docx.py` | one command, Markdown to `.docx`; `--preset`, `--list-presets` | none |
| 9. After submission | `package.py` | `build`, `dictionary`, `verify` | none |
| 9 | `watch.py` | `add`, `run`, `list`, `remove`, `schedule` | `run`: OpenAlex, 10 credits per watch |
| 9 | `deliverables.py` | `visual`, `check`, `selftest` | none |

Stage 3 (verify sources) is `scholar.py verify`. Stage 6 (writing) has no script: the agent writes from `references/writing-style.md` and the ledger. Stage 8 reuses `scholar.py refs`, `audit` and `numbers`, `evidence.py audit` and `trail`, and `autopsy.py statcheck`.

Shared helpers in `scholar.py`, imported by the other scripts:

| Helper | Role |
|---|---|
| `http_get()` | Every HTTP call in the repo: per-host pacing, exponential backoff on 429 and 5xx, `None` on a 404 |
| `openalex()` | OpenAlex calls with the API key when present; a refused key prints one warning and the call is retried keyless |
| `crossref_work()`, `resolve_doi()`, `openalex_by_doi()`, `attach_abstract()` | Registry lookups and the abstract fallback chain |
| `load_ledger()`, `save_ledger()` | Read and write `sources.jsonl` |
| `table()`, `clean()`, `apa()`, `norm_doi()`, `title_sim()` | Markdown tables, text normalisation (dashes to hyphens), APA strings, DOI and title comparison |

### `references/` - what the agent reads

| File | Read at |
|---|---|
| `stages.md` | Every stage: the commands and checks per stage |
| `integrity.md` | Step 0: authorship modes, refusal wording, laws, AI-use disclosure templates |
| `theories.md` | Stage 4: 30 theories with verified original sources, and the theory-fit procedure |
| `red-team.md` | Stage 4: attack the design before data collection |
| `instruments.md` | Stage 4: validated scales, adaptation, licence table |
| `writing-style.md` | Stage 6: IMRaD and the five-chapter thesis |
| `journal-vetting.md` | Stage 7: quartiles, predatory and hijacked journals |
| `review-panel.md`, `reviewers/*.md`, `reviewer-complaints.md` | Stage 8: six reviewer prompts (methods, statistics, field expert, editor, Arabic language, theory), the merge template, and what real reviewers object to |
| `university-presets.json`, `university-presets.md` | Stage 8: `build_docx.py --preset` (10 presets) |
| `defense.md`, `deliverables.md` | Stage 9: viva preparation; abstract, policy brief, post, lay summary, visual abstract |
| `module-contract.md`, `api-notes.md` | Maintainers: the rules every script follows and how each API behaves |

### Project folder - the shared state

```text
<project>/
  cand*.json                  search and snowball candidates (not sources until added)
  sources.jsonl               the source ledger: one verified source per line
  matrix.md                   themes x sources, filled from the ledger
  papers/                     PDFs the user supplies, matched to ledger keys by DOI or title
  fulltext/<key>.txt          full text with [[page N]] markers; fulltext/index.json
  claims.jsonl                claim + verbatim quote + page for each cited finding
  analysis/                   the user's data, analysis scripts, output.txt (evidence lines)
  coding.jsonl, codebook.json qualitative coding (qual.py)
  watch.json, watch_log.md    literature watch (watch.py)
  shortlist.md                3 to 5 vetted journals
  <manuscript>.md             the paper, checked by audit, numbers and similarity
```

`add` writes only entries resolved against a registry, except `add --manual`, which records a report or manual with no DOI or ISBN marked unverified. `fix` changes spelling and form, never identity, and changes nothing when any part is refused. `claim add` refuses a quote that is not verbatim in the full text. Evidence lines end with the statistic label, because `scholar.py numbers` reads the last dot-segment of a key. `package.py` never packages key files, `papers/` or `fulltext/`.

### Shared data formats

From [references/module-contract.md](references/module-contract.md); a new script that produces one of these files writes the same shape.

| File | Format |
|---|---|
| `sources.jsonl` (the ledger) | One JSON object per line: `key` (e.g. `junco2012`), `doi`, `isbn`, `type`, `title`, `authors` [{family, given}], `year`, `container`, `volume`, `issue`, `pages`, `article_number`, `issn` [], `publisher`, `abstract`, `abstract_source`, `note` (the claim it supports), `read_level` (abstract / full / metadata), `retraction` {status, notices}, `verified` {by, at}, `apa`, `cited_by` |
| `cand*.json` | `{query, date, source, results: [{doi, title, year, cites, first_author, authors, n_authors, venue, issn_l, core_venue, type, is_oa, retracted, abstract}]}` |
| `analysis/output.txt` (evidence) | Lines `key.path.label = value`; the last dot-segment is the statistic label `scholar.py numbers` matches (`r`, `beta`, `b`, `se`, `t`, `p`, `df`, `m`, `sd`, `n`, `d`, `ci_low`, `ci_high`, `alpha`, `f`, `r2`, `eta2`, `chi2`, `w`, `u`, `h`, `sr2`, `vif`, `pct`...); `# APA:` lines give the ready sentence |
| `fulltext/<key>.txt` | Plain text with `[[page N]]` on its own line before each page; `fulltext/index.json` records per key: source, url_or_path, pages, numbering (printed / pdf / none), fetched, status, file |
| `claims.jsonl` | One JSON object per line: `{key, claim, quote, page, locator, page_given, page_numbering, source_file, added}`; `quote` is verbatim; `locator` is "Section, para. N" when the text has no pages |
| `coding.jsonl`, `codebook.json` | Qualitative coding: segments with transcript, start / end, code, coder, verbatim quote |
| `watch.json`, `watch_log.md` | Literature watch queries and the new works found per run |

Output convention for every check command: one summary line, a markdown pipe table, then `RESULT: PASS|FAIL (...)`, with exit code 1 on FAIL and a note of what was not checked.

---

## Data Flow: A Typical Paper

1. **Search.** The agent runs `scholar.py search '"a" AND "b"' --since 2018 --core --out cand.json` (OpenAlex; `--source crossref --expand` for Arabic) or `snowball.py run --seeds <DOI> <DOI>`. Candidates land in `cand*.json`. `gapmap.py` and `comap.py` read those files to show where studies disagree and how the field clusters. Nothing in a candidate file is a source yet.
2. **Ledger.** `scholar.py abstract <doi>` shows the real abstract (OpenAlex, Crossref, Semantic Scholar, Europe PMC in turn). `scholar.py add <doi> --note "..."` resolves the DOI at Crossref (doi.org handles for DataCite DOIs), reads retractions from Crossref's `updated-by`, refuses fake DOIs, notices and retracted papers, and appends the entry to `sources.jsonl`. A list the user brings goes through `verify --citations-file refs.txt --add-to sources.jsonl`.
3. **Claims.** `evidence.py fetch` writes `fulltext/<key>.txt` from the user's `papers/` or an open-access copy. `evidence.py quote` finds candidate passages; `evidence.py claim add --key ... --page ... --quote ... --claim ...` stores the verbatim quote in `claims.jsonl`, or refuses it.
4. **Evidence.** `autopsy.py careless` flags careless or invalid survey rows and writes a cleaned CSV. `analyze.py` and `analyze_sem.py` (also `instruments.py pilot`, `effects.py justify --evidence`, `qual.py agreement --evidence`) append `label = value` lines to `analysis/output.txt`.
5. **Audit.** `scholar.py refs` builds the reference list from the ledger, only what the text cites. `scholar.py audit` checks every in-text citation against the ledger, `evidence.py audit` checks every cited finding has a live verbatim claim, `scholar.py numbers` checks every statistic against `analysis/output.txt`, `autopsy.py statcheck` recomputes every reported p, and `similarity.py check` looks for uncited overlap with the ledger abstracts and full texts. Each ends with `RESULT: PASS|FAIL`.
6. **Output.** `build_docx.py paper.md -o paper.docx --preset <name>` writes the Word file, `evidence.py trail` the evidence appendix, `package.py build` the reproducibility zip.

---

## Data Flow: From Search to Audit Detail

```text
Agent (SKILL.md)        scripts/                          APIs                     project folder
     |                     |                                 |                           |
     | scholar.py search   |                                 |                           |
     |-------------------->| title_and_abstract.search       |                           |
     |                     |-------------------------------->| OpenAlex                  |
     |                     |<--------------------------------|                           |
     |                     | candidates ------------------------------------------------>| cand.json
     | scholar.py add DOI  |                                 |                           |
     |-------------------->| works/DOI, updated-by           |                           |
     |                     |-------------------------------->| Crossref, doi.org         |
     |                     |<--------------------------------|                           |
     |                     | refuse fake / notice / retracted, else append ------------->| sources.jsonl
     | evidence.py fetch   |                                 |                           |
     |-------------------->| papers/ first, then an OA copy  |                           |
     |                     |-------------------------------->| Unpaywall*, OpenAlex OA,  |
     |                     |<--------------------------------| Europe PMC, arXiv         |
     |                     | text with [[page N]] -------------------------------------->| fulltext/KEY.txt
     | evidence.py         |                                 |                           |
     |   claim add         |                                 |                           |
     |-------------------->| quote verbatim in the text? then append ------------------->| claims.jsonl
     | analyze.py ... >>   | label = value lines, no network ---------------------------->| analysis/output.txt
     | audit, numbers      |                                 |                           |
     |-------------------->| read manuscript, ledger, claims, output.txt <---------------|
     |<--------------------| RESULT: PASS | FAIL (exit 1)    |                           |

* Unpaywall only when RESEARCH_MAILTO (or --email) is set.
```

---

## External APIs and Limits

From [references/api-notes.md](references/api-notes.md) (verified live on 2026-10-20) and `reviews.py --help` (2026-10-21). On top of the limits below, `http_get()` paces itself per host: OpenAlex 0.12 s, Crossref 1.05 s (0.35 s with `RESEARCH_MAILTO`), Semantic Scholar 1.1 s, DOAJ 0.55 s, Open Library 0.4 s, doi.org 0.35 s, 0.2 s for any other host.

| API | Used by | Auth and limits | Notes |
|---|---|---|---|
| OpenAlex | scholar, gapmap, comap, snowball, evidence, instruments, journalfit, watch | No key: 1,000 credits a day shared per IP. Free key: 10,000. A search costs 10, a filter list 1, a single lookup (`works/doi:`, `sources/issn:`) 0 | Search with `title_and_abstract.search`; `per_page` max 200; cursor paging past page 1 needs a key; many abstracts are missing; no quartile field |
| Crossref | scholar, instruments | No key. Single record 5/s (10/s polite); lists and search 1/s (3/s polite, with `mailto`) | A 404 is not proof of fabrication (DataCite DOIs live elsewhere); `query.bibliographic` always returns hits, so title, first author and year are compared; retractions come from `updated-by` (includes Retraction Watch data), which `select=` silently drops |
| doi.org | scholar | Crossref limits | Handles API (`responseCode 1` = registered) for non-Crossref DOIs; content negotiation output is decoded as UTF-8 and its dashes normalised |
| Semantic Scholar | scholar | Keyless shared pool, 429s even on the first call; free key (`S2_API_KEY`) starts at 1 request/s | `limit` max 100; `/paper/search/match` always returns something, so it is never used alone |
| Europe PMC | scholar, evidence | No key | Abstract fallback for biomedical and life-science papers; full-text XML has no page numbers |
| Unpaywall | evidence | A real email (`RESEARCH_MAILTO` or `--email`); placeholder addresses get HTTP 422 | Skipped, with a message, when no email is set |
| arXiv | evidence | No key | PDF by arXiv ID, last in the fetch order |
| DOAJ | scholar | No key, 2 requests/s, excess queued | ISSN must be hyphenated; absence is normal for subscription journals |
| Open Library | scholar | No key | Returns every edition: cite the edition used |
| OpenReview, eLife, F1000Research | reviews | Free, no login | Open reviews exist for ML/CS, life science and F1000 only |
| PeerJ | reviews | Blocked for scripts (Cloudflare challenge) | Tried once with a browser user agent, then reported as blocked with 0 reviews |
| SJR (SCImago) | scholar `journal`, `journals` | No API; Cloudflare and robots.txt block scripts | The user downloads the CSV (`--sjr` or `SJR_CSV`): `;` delimiter, comma decimals, per-category quartiles in `Categories`; not redistributed |

---

## Security Model

1. **Sources only from a registry.** `scholar.py` `add` and `verify` resolve every DOI at Crossref (doi.org handles for DataCite) and every ISBN at Open Library; unresolvable DOIs, retraction notices and retracted papers are refused. `add --manual` is the one exception and marks the entry unverified.
2. **Quotes only from the text.** `evidence.py claim add` refuses a quote that is not verbatim in `fulltext/<key>.txt`; `evidence.py audit` fails a cited finding without one (a source with no full text is a WARN, a FAIL with `--strict`).
3. **Numbers only from analysis output.** `scholar.py numbers` fails a value with no matching label in `analysis/output.txt` and a value whose sign differs; in template mode (no evidence file) it fails any number at all.
4. **Keys stay out of projects and output.** `scholar.py` reads the OpenAlex key from `OPENALEX_API_KEY` or `~/.config/research-paper-assistant/openalex.key` and sends it only to `api.openalex.org`; error messages carry the URL without its query string. `package.py` refuses key files, `.env` files and any text file with an API-key-looking line.
5. **No bypass.** `evidence.py` retries an HTTP 403 once with a browser user agent and then leaves the site alone; paywalled papers come only from the user's `papers/`; `reviews.py` reports PeerJ's block; no script fetches the SJR file.
6. **Downloads are data.** Fetched PDFs, `.xlsx` and CSV files are parsed (PyMuPDF, pypdf, openpyxl), never executed.
7. **Local transcription.** `qual.py transcribe` runs whisper.cpp (and ffmpeg) on the machine; no audio leaves it.

See [SECURITY.md](SECURITY.md) for every host the scripts call and what is sent.

---

## How to extend

### Add a new script

Drop the file in `scripts/`. There is no registry: it runs at once, and the agent uses it once `SKILL.md` and `references/stages.md` name it.

```text
scripts/
  newtool.py      <-- new script, immediately runnable as: python -X utf8 scripts/newtool.py --help
```

The file shape that [references/module-contract.md](references/module-contract.md) requires:

```python
#!/usr/bin/env python3
"""newtool.py - one line on what it checks.

Commands
  check     ... (prints a table, then RESULT: PASS|FAIL)
  selftest  one positive case and one planted-error negative control

Usage
  python -X utf8 newtool.py check paper.md
"""
import argparse
import os
import sys

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scholar import http_get, load_ledger, table, TODAY  # noqa: E402

# argparse with subcommands; each check command ends with
# print(f"RESULT: {'FAIL' if bad else 'PASS'} (...)") and sys.exit(1 if bad else 0)
```

### Add a new module

1. Read [references/module-contract.md](references/module-contract.md): environment, shared helpers, data formats, CLI conventions, honesty rules.
2. Write `scripts/<module>.py`, importing helpers from `scholar.py` instead of copying them. Do not edit `scholar.py`, `analyze.py` or `build_docx.py` unless the change is about that file.
3. Give it a `selftest` with at least one positive case and one planted-error negative control, and add the module name to the selftest loop in `tests/run_tests.py`. Fixtures in `tests/fixtures/` are read-only: copy them into a scratch folder.
4. Name the script in the stage table of `SKILL.md`, in `references/stages.md` and in the README stage table, and update the script count (README badge, `tools/readme-media/media.json`, `.github/REPOSITORY_METADATA.md`). No other registration.
5. `python -X utf8 tests/run_tests.py` must end with `RESULT: PASS`.

### Add a university preset

Add an entry to `references/university-presets.json` with the keys its `_schema` entry describes (including `source_url`, `verified` and `verified_date`) and a row in `references/university-presets.md`. `build_docx.py --list-presets` shows it with its verification status.

### Add a reviewer or a reference doc

Reviewer prompts are self-contained files in `references/reviewers/`, merged with the template in `references/review-panel.md`. Other docs go in `references/` and are linked from the stage table in `SKILL.md` or from `references/stages.md`.

---

## Environment Variable Reference

| Variable | Default | Read by |
|---|---|---|
| `OPENALEX_API_KEY` | *(unset)*: then `~/.config/research-paper-assistant/openalex.key`, then keyless | `scholar.py` (every OpenAlex call goes through its `openalex()`) |
| `RESEARCH_MAILTO` | *(unset)* | `scholar.py` (Crossref `mailto`, User-Agent), `evidence.py` (Unpaywall) |
| `S2_API_KEY` | *(unset)* | `scholar.py` (Semantic Scholar) |
| `SJR_CSV` | *(unset)*: `--sjr <file>` instead | `scholar.py journal`, `journals` |
| `WHISPER_CLI` | *(unset)*: then `whisper-cli` on `PATH` | `qual.py transcribe` |
| `WHISPER_MODEL_DIR` | `~/.cache/whisper` | `qual.py transcribe` |

The OpenAlex key file sits outside every repo and project on purpose: it is never copied into a project folder or a reproducibility package.

---

*See [README.md](README.md) for feature descriptions. See [references/module-contract.md](references/module-contract.md) for the rules every script follows.*
