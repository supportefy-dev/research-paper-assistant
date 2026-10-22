# Contributing

Thank you for improving Research Paper Assistant.

Research Paper Assistant is a Claude Code skill for academic papers, theses and proposals in Arabic and English, whose integrity rules are enforced by 18 Python scripts rather than by promises. Contributions should preserve the core philosophy (from [references/module-contract.md](references/module-contract.md)):

```text
A script never invents a source, a number or a quote.
Scripts do the mechanical, checkable work; judgement stays with the agent and the researcher.
Free APIs only, and no paywall or bot-protection bypass.
```

## Contribution Types

Good contributions include:

- New or improved scripts (`scripts/`), written to [references/module-contract.md](references/module-contract.md)
- Fixes after a free API changes its behaviour (`scripts/scholar.py`, with [references/api-notes.md](references/api-notes.md) updated)
- Reference docs and reviewer prompts (`references/`, `references/reviewers/`)
- University formatting presets (`references/university-presets.json`), verified against the university's published guide where possible
- Test coverage: a `selftest` in each script and checks in `tests/run_tests.py`
- Documentation improvements

## Before You Open a Pull Request

1. Run the test suite (offline; add `--live` when you changed code that calls an API):

```bash
python -X utf8 tests/run_tests.py
python -X utf8 tests/run_tests.py --live
```

2. Confirm every script still starts cleanly:

```bash
for f in scripts/*.py; do python -X utf8 "$f" --help > /dev/null || echo "FAIL $f"; done
```

3. If you added or removed a script, update the count (18 today) in the README badge, the `chips` in `tools/readme-media/media.json` and `.github/REPOSITORY_METADATA.md`.

4. Update these files when structure changes:

```text
README.md
CHANGELOG.md
SKILL.md                         (if a stage, a command or a hard rule changed)
SYSTEM.md                        (if a script, a data format or an API changed)
references/stages.md             (if a documented command changed)
references/module-contract.md    (if a shared data format or helper changed)
references/api-notes.md          (if an API's limits or behaviour changed)
```

## Script Rules

New scripts should:

```text
follow references/module-contract.md (environment, helpers, formats, CLI conventions)
use argparse subcommands, each with --help and one example
start with sys.stdout.reconfigure(encoding="utf-8") (and stderr), guarded in try/except
make every HTTP call through http_get() from scholar.py, to free APIs only
read and write the shared formats (sources.jsonl, cand*.json, label = value evidence lines)
print a summary line, a table, then RESULT: PASS|FAIL for a check command, and exit 1 on FAIL
say NOT FOUND or UNVERIFIED instead of filling a gap, and label regex extractions as candidates
ship a selftest with one positive case and one planted-error negative control
not expose secrets or personal data in output
```

Do not edit `scholar.py`, `analyze.py` or `build_docx.py` as a side effect of another change: import their helpers instead. The fixtures in `tests/fixtures/` are read-only; a test copies them into a scratch folder (as `tests/run_tests.py` does with `tests/_out/`).

## Ledger Integrity

`sources.jsonl` is the source of truth for what a manuscript may cite. Any code that writes to it must:

```text
go through load_ledger() and save_ledger() in scholar.py
never truncate an existing ledger without reading it first
write only entries resolved against a registry (add --manual entries stay marked unverified)
change an entry's spelling and form, never its identity (the rule scholar.py fix enforces)
```

## Style Rules

- **No em dash or en dash anywhere**: docs, code, comments, output. Use a hyphen, colon, comma or parentheses; in code write `chr(0x2013)` or `"\u2013"` when a script must match the character. This prints nothing when the repo is clean (`tests/fixtures/paper.md` plants an em dash on purpose, so fixtures are skipped):

```bash
python -X utf8 -c "import pathlib; [print(p) for p in pathlib.Path('.').rglob('*') if p.suffix in ('.md', '.py', '.json') and not {'.git', 'fixtures', '_out'} & set(p.parts) and any(c in p.read_text(encoding='utf-8', errors='replace') for c in (chr(0x2013), chr(0x2014)))]"
```

- **No machine paths or personal data**: no absolute paths to a home folder or a drive letter (use `~/.claude/skills/research-paper-assistant` or a relative path), no real email addresses (use `you@example.com`), no real participant data. The fixtures are synthetic and must stay synthetic.
- **No secrets**: no API keys, `.env` files or key files; `.gitignore` already excludes `*.key`, `.env` and `.env.*`.
- **No debug prints** left in a script.

## Pull Request Flow

1. Fork the repository and branch from `master`.
2. Make the change, with its selftest or test check.
3. Run the checks in [Before You Open a Pull Request](#before-you-open-a-pull-request).
4. Add a line under `[Unreleased]` in `CHANGELOG.md`.
5. Open a pull request against `master` and fill in the template (summary, type, validation output).

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md). Security issues go by email, not as a pull request: see [SECURITY.md](SECURITY.md).

## Pull Request Checklist

- [ ] `python -X utf8 tests/run_tests.py` ends with `RESULT: PASS`.
- [ ] Every script's `--help` runs.
- [ ] A new script has a `selftest` (positive case + planted-error negative control) listed in `tests/run_tests.py`.
- [ ] Docs updated if behavior changed.
- [ ] `CHANGELOG.md` updated with a concise entry.
- [ ] No em or en dashes.
- [ ] No hardcoded paths, tokens, or personal data.
- [ ] No debug print statements left in production paths.

## Contributor terms

By submitting a contribution you agree it is licensed under the project's MIT license (see [LICENSE](LICENSE)).
