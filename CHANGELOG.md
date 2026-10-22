# Changelog

All notable changes to Research Paper Assistant are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added

- **README media.** Light and dark hero and how-it-works images, feature cards, a quick-start card, a social preview image and line icons in `assets/readme/`, with their SVG sources in `assets/readme/source/` and the text and palette they are built from in `tools/readme-media/media.json`. The README now shows the stages and the three checks before the reader scrolls.
- **Doc set.** `QUICKSTART.md` (commands only), `SYSTEM.md` (the 18 scripts by stage, the shared data formats, the data flow, the API limits, how to add a module), `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, this changelog, issue and pull request templates, release notes (`.github/RELEASE_TEMPLATE.md`) and a record of the GitHub description, topics and release (`.github/REPOSITORY_METADATA.md`). Before this, contributors had only the README and `references/module-contract.md`.
- **`.repo-polish-ignore`.** Lists `tests/fixtures/*` for the repo-polish dash scan, because `tests/fixtures/paper.md` plants an em dash on purpose (`scholar.py audit` must warn about it).

### Changed

- **README rewritten from the repo's own facts.** Hero, feature grid, how-it-works diagram, Works with row, What it is, Who this is for, Compatibility, Safety model and Troubleshooting sections, badges (version, licence, script count, Python, languages), and links to the new doc set. The install commands, the stage table, the check examples and the honest limits carry over from 1.0.0.

## [1.0.0] - 2026-10-22

First public release.

- A Claude Code skill (`SKILL.md`) for research papers, theses and proposals in Arabic and English, IMRaD or the five-chapter Arab-university thesis, in nine stages from topic and gap to after submission. An authorship check (modes A to D) declines work that someone else will submit as their own and offers coaching instead.
- `scripts/scholar.py`: search (OpenAlex, Semantic Scholar, Crossref for Arabic journals); a source ledger (`sources.jsonl`) whose `add` refuses fake DOIs, retraction notices and retracted papers; `verify` for one DOI, one citation or a whole list (verdicts `REAL`, `REAL, ERRORS`, `RETRACTED`, `FABRICATED?`, `WRONG DOI` or `UNVERIFIED`, with corrected APA); `fix`, `book`, `abstract`, `cite`, `refs` (APA, or `--format ris/bibtex/csl`), `list`, `audit`, `numbers`, `journal` and `journals`.
- Topic and gap: `gapmap.py` (where studies disagree, empty population and country cells, draft gap sentences) and `comap.py` (co-citation map: schools of thought, seminal papers, frontier, bridge papers).
- Literature: `snowball.py` (backward and forward citation chasing with PRISMA counts) and `evidence.py` (open-access full texts with page markers, verbatim quotes with page numbers in `claims.jsonl`, claim audit, evidence trail).
- Design: `instruments.py` (validated scales, pilot item analysis, back-translation protocol), `effects.py` (effect sizes from abstracts as candidates, power including mediation, a sourced sample-size paragraph in English and Arabic), a registry of 30 theories with verified sources (`references/theories.md`) and a red-team protocol for the design (`references/red-team.md`).
- Analysis on the user's own CSV, written as `label = value` evidence lines: `autopsy.py` (careless responders, GRIM, Harman, statcheck), `analyze.py` (descriptives, frequencies, correlation, regression with diagnostics, Welch t-test, one-way ANOVA, Cronbach's alpha), `analyze_sem.py` (mediation and moderation in the PROCESS models 4 and 1, CFA with CR, AVE and HTMT, basic PLS-SEM) and `qual.py` (local whisper.cpp transcription, codebook, coding, Cohen's kappa, themes with timestamped quotes).
- Journal choice: SJR shortlist by category quartile from a CSV the user downloads, DOAJ and hijacked-journal checks, and `journalfit.py` (house profile, TF-IDF fit score, desk-reject risk).
- Pre-submission: `similarity.py` (exact and near copies against the ledger abstracts and full texts), `reviews.py` (public peer reviews from OpenReview, eLife and F1000Research), six reviewer prompts in `references/reviewers/`, AI-use disclosure templates in `references/integrity.md`, and `build_docx.py` (Word output with right-to-left Arabic paragraphs, APA tables and 10 formatting presets; `--list-presets` shows the 7 verified against a published guide).
- After submission: `package.py` (reproducibility zip with a data dictionary, SHA-256 checksums and a CITATION.cff skeleton; key files are refused), `watch.py` (new OpenAlex works per saved query), `deliverables.py` (visual abstract drawn only from evidence lines, derived texts checked against them) and a defense guide (`references/defense.md`).
- Tests: `python -X utf8 tests/run_tests.py` runs 13 module selftests and 5 planted-error regression checks on the fixtures, offline (18 checks); `--live` adds a real and a fake DOI checked against Crossref.
- License: MIT, licensed by Supportefy.

[Unreleased]: https://github.com/supportefy-dev/research-paper-assistant/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/supportefy-dev/research-paper-assistant/releases/tag/v1.0.0
