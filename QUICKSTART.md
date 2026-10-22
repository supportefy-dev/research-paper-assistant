# Quickstart

The commands only. For what each step does and why, see [README.md](README.md).

```bash
git clone https://github.com/supportefy-dev/research-paper-assistant ~/.claude/skills/research-paper-assistant
cd ~/.claude/skills/research-paper-assistant
pip install -r requirements.txt
```

On Windows the skills folder is `%USERPROFILE%\.claude\skills\`.

Optional setup:

```bash
# OpenAlex key (free): request it, save the api_key from the reply as one line in
# ~/.config/research-paper-assistant/openalex.key, then click the activation email
mkdir -p ~/.config/research-paper-assistant
curl -X POST https://api.openalex.org/api-keys -H "Content-Type: application/json" -d '{"email":"you@example.com"}'
export RESEARCH_MAILTO="you@example.com"       # your own email: faster Crossref, Unpaywall full texts
export SJR_CSV="/path/to/scimagojr.csv"        # downloaded in a browser from https://www.scimagojr.com/journalrank.php
pip install semopy                              # CFA fit indices in analyze_sem.py cfa
```

Verify:

```text
python -X utf8 tests/run_tests.py
```

First prompts, in Claude Code:

```text
find me a gap on X
check my references
write my results from this CSV
which Q1 journal fits this abstract
جهزني للمناقشة
```

First script run, without Claude:

```text
python -X utf8 scripts/scholar.py verify 10.1016/j.chb.2010.03.024
```

That's it: `tests/run_tests.py` confirms the 13 module selftests and the planted-error regression pass offline (`RESULT: PASS (18/18 checks)`), the `verify` call checks a real DOI and its retraction status against Crossref. Everything else (the nine stages, the journal shortlist, the Word presets) is documented in [README.md](README.md); every command per stage is in [references/stages.md](references/stages.md).

Stuck? See [README.md#troubleshooting](README.md#troubleshooting) for the first-run issues that come up (`UnicodeEncodeError` on a Windows console, OpenAlex 429 from the shared keyless pool, Unpaywall skipped without `RESEARCH_MAILTO`).
