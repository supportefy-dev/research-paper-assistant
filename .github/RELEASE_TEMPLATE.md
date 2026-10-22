# Research Paper Assistant 1.0.0: first public release with script-enforced sources, quotes and numbers

Research Paper Assistant 1.0.0 is the first public release of the Claude Code skill for research papers, theses and proposals in Arabic and English. What a user notices first: a source ledger that refuses fake DOIs, retraction notices and retracted papers (`scholar.py add`, and `scholar.py verify --citations-file` for a whole reference list); findings cited only with a verbatim quote and its page (`evidence.py claim add`, checked by `evidence.py audit`); and every statistic in a Results section matched to the analysis output it came from (`scholar.py numbers`). It is 1.0.0 because it is the first tagged release.

## Highlights

- **Reference list check in one command.** `python -X utf8 scripts/scholar.py verify --citations-file refs.txt` gives one verdict per reference (`REAL`, `REAL, ERRORS`, `RETRACTED`, `FABRICATED?`, `WRONG DOI`, `UNVERIFIED`) and a corrected APA version built from the registry; `--add-to sources.jsonl` puts the confirmed ones in the ledger. A fabricated reference that borrows a real journal, volume and page is caught by looking up what really sits at that locator.
- **Quotes with pages.** `evidence.py fetch` collects open-access full texts, or the user's PDFs in `papers/`, with page markers; `evidence.py claim add` refuses a quote that is not verbatim in the text; `evidence.py audit` fails a cited finding without one.
- **Audited numbers.** `autopsy.py careless` cleans survey data first; `analyze.py` and `analyze_sem.py` write `label = value` evidence lines; `scholar.py numbers results.md --evidence analysis/output.txt` fails an unsupported value or a flipped sign.
- **Journal, review and Word output.** SJR shortlist by category quartile from a CSV you download, DOAJ and hijacked-journal checks, `journalfit.py` fit score, a six-reviewer panel, and `build_docx.py --preset` with 10 formatting presets and right-to-left Arabic paragraphs.
- **License:** MIT License (MIT), licensed by Supportefy.
- 18 scripts in `scripts/`, 13 with a `selftest`; `python -X utf8 tests/run_tests.py` runs 18 offline checks.

See [CHANGELOG.md](https://github.com/supportefy-dev/research-paper-assistant/blob/master/CHANGELOG.md) for the complete list.
