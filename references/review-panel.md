# Review panel: six reviewers, run in parallel (لجنة التحكيم الداخلية)

A manuscript that passes this panel has already met the objections a real journal or thesis committee will raise. The panel is six self-contained prompt files in [reviewers/](reviewers/). Each takes the manuscript path and the project folder and returns a structured verdict: scores, must-fix and should-fix lists tied to exact sentences, and one of `accept / minor / major / reject`.

| # | Reviewer | File | Decides on |
|---|---|---|---|
| 1 | Methods (المنهجية) | [reviewers/methods.md](reviewers/methods.md) | design fit, sampling, instruments, bias control, ethics, reporting guideline |
| 2 | Statistics (الإحصاء) | [reviewers/statistics.md](reviewers/statistics.md) | every number (`numbers` check), tests, effect sizes, interpretation |
| 3 | Field expert (التخصص) | [reviewers/field-expert.md](reviewers/field-expert.md) | gap, coverage, synthesis, fidelity to sources, discussion honesty |
| 4 | Editor (المحرّر) | [reviewers/editor.md](reviewers/editor.md) | scope, structure, abstract, declarations, `audit`, venue guidelines |
| 5 | Arabic language (اللغة العربية) | [reviewers/arabic-language.md](reviewers/arabic-language.md) | fusha, terminology, orthography, RTL rendering, bilingual parity |
| 6 | Theory (الإطار النظري) | [reviewers/theory.md](reviewers/theory.md) | constructs, mechanism, derivation of hypotheses, theoretical payoff |

Run it at stage 8 (before `build_docx.py`), on a single chapter during writing (one or two reviewers only), and again after any major revision.

## 1. Prepare the inputs

```
<project>/
  paper.md                 the manuscript (or chapters/*.md; pass one file per run)
  sources.jsonl            the ledger (reviewers 1, 3, 4, 6 read it)
  analysis/output.txt      evidence lines (reviewers 1, 2)
  design.md                red-team design file if one exists (reviewers 1, 6)
  glossary.md              Arabic/English construct terms if kept (reviewer 5)
  paper.pdf                built and converted, for RTL checks (reviewer 5)
  shortlist.md             stage 7 journal shortlist (reviewer 4)
  review/
    author-guide.md        the venue's author guidelines (fetched, see section 2)
    journal-guide.md       the venue's reviewer guidelines or checklist (fetched)
    round-1/               one verdict file per reviewer, then merged.md
    round-2/ ...
```

Line numbers are the panel's coordinate system. Do not edit `paper.md` between launching the reviewers and merging their verdicts, or the line references drift.

## 2. The target journal's own reviewer guidelines

When the user names a target journal (stage 7 output), the venue's own criteria outrank this panel's defaults.

1. Fetch two pages from the journal's site: "Guide for authors" (author-guide.md) and "Reviewer guidelines" / "Information for reviewers" / the review form, if public (journal-guide.md). Use the web fetch tool on the journal's own domain only; save the text, with the URL and the date, in `review/`. The sites that block fetching (Cloudflare, login walls): ask the user to paste the pages. **Never reconstruct a journal's guidelines from memory**; a reviewer that cannot see them writes "not checked: author guide not fetched".
2. Many venues point to a reporting guideline instead of writing their own: STROBE for observational studies, CONSORT for trials, COREQ or SRQR for qualitative work (DOIs in [reviewers/methods.md](reviewers/methods.md)). Download the checklist from the EQUATOR Network page the journal links and save it as `review/journal-guide.md`.
3. Each reviewer prompt already says what it does with `journal-guide.md`: the editor turns every author-guide item into a checklist row; methods and statistics add the guideline items; the field expert adds the "contribution / relevance to readers" criterion; the language reviewer adds the Arabic-abstract and digit rules.
4. Thesis instead of journal: the university's دليل كتابة الرسائل الجامعية plays the same role. Save it as `review/author-guide.md`. The committee's evaluation form (نموذج تقييم الرسالة), if the department publishes it, is `review/journal-guide.md`.

## 3. Run all six in parallel

Each reviewer is one Agent call (or one Workflow step). The prompt is the reviewer file's full content followed by an Inputs block:

```
<full content of references/reviewers/<name>.md>

## Inputs for this run
{MANUSCRIPT} = /path/to/project/paper.md
{PROJECT}    = /path/to/project
{S}          = ~/.claude/skills/research-paper-assistant/scripts
{ROUND}      = 1
{LANG}       = ar | en | mixed
{VENUE}      = <journal name + ISSN, or 'thesis: <university>', or 'unknown'>
{DIGITS}     = arabic | arabic-indic
{SEARCH_BUDGET} = 2
Write your verdict block to /path/to/project/review/round-1/<name>.md and return it.
```

Launch the six agents in one message so they run concurrently; none depends on another. Budget: the field expert may spend up to `{SEARCH_BUDGET}` OpenAlex searches (10 credits each); the others make no list searches (`numbers` and `audit` are local; `verify` is Crossref). A full round therefore costs at most 20 OpenAlex credits.

A reviewer that cannot read a file says so under NOT CHECKED and still returns a verdict on what it could read. A reviewer that returns an objection without a quoted sentence has broken its own rule: drop that objection at merge and note it.

Smaller runs: one chapter while writing -> the two reviewers that own it (Methods chapter: methods + statistics; Literature chapter: field expert + theory; Arabic abstract: arabic-language + editor). Keep `{ROUND}` numbering per manuscript, not per chapter.

**Literature chapter scope** (a chapter or proposal with no results yet, full panel requested): each reviewer judges what exists and writes `literature chapter: no results` under NOT CHECKED for the rest. Methods: causal verbs in the hypotheses as phrased, construct definitions, a ledger source for every named instrument. Statistics: `numbers <chapter> --ledger sources.jsonl` (figures quoted from abstracts), no `--evidence`, and the "no output = reject" rule does not apply. Field expert: gap, coverage, currency, synthesis, fidelity. Theory: derivation of the hypotheses. Editor and Arabic language: as usual. Scores a reviewer cannot give are written `n/a`.

**Sequential fallback**: when parallel agents are unavailable (one agent at a time, a Workflow without parallel steps), run the six one after another with the same prompts and the same frozen `paper.md`, and write `Mode: sequential` in `merged.md`. The verdicts do not change, only the wall time.

## 4. Merge

Scores written `n/a` (literature-chapter runs, or a criterion a reviewer could not judge) are left out of every average and verdict count; only the 1-5 scores and the must-fix lists decide the verdict.

Write `review/round-<k>/merged.md` with the template in section 7. Rules:

| Step | Rule |
|---|---|
| Collect | Every M and S item from the six verdicts, keeping its reviewer tag (`methods M2`) |
| Validate | Drop any item without a line number and verbatim quote (or `ABSENT: <heading>`); list the dropped ones at the end so the author knows the reviewer slipped |
| De-duplicate | Same line and same problem from two reviewers = one item carrying both tags; it keeps the higher severity |
| Conflicts | Two reviewers disagree on the same sentence: the owner decides. Numbers: statistics. Design and causal wording: methods. Gap and sources: field expert. Venue format: editor. Terminology and Arabic form: arabic-language. Mechanism and hypotheses: theory. Record the overruled view in one line |
| Severity | The panel verdict is the worst single verdict: any `reject` = reject; else any `major` = major; else any `minor` = minor; else accept |
| Order | Must-fix items sorted by line number, then should-fix by line number, so the author works top to bottom once |
| Integrity items first | An unsupported number, a citation not in the ledger, a source cited for what it does not say, or AR/EN abstracts with different numbers go to the top of the must-fix list regardless of line, tagged INTEGRITY |

## 5. Fix, then re-run until clean

```
round 1: run 6 reviewers -> merge -> author/agent fixes every must-fix (and the should-fix items it agrees with)
round 2: run again (all 6, same prompts, ROUND = 2) -> merge -> fix
round 3: run again -> merge
stop when: no must-fix remains  (panel verdict accept or minor)
       or: round 3 is merged     (report the remaining must-fix items to the user as decisions)
```

- Fixing means editing `paper.md` (and re-running the analysis or `refs` when the fix needs it), then re-running `audit` and `numbers` yourself before launching round 2. Do not launch a round you know will fail on the same mechanical lines.
- Keep a change log in `review/changelog.md`: item id, what changed, line. A reviewer in round 2 does not see round 1; the log is for the user and for the response-to-reviewers letter later.
- An item the author rejects with a reason (e.g. the venue does not allow that section) is recorded as `WONTFIX: <reason>` in the changelog and is not counted as open; if the same reviewer raises it again in the next round, it stays WONTFIX and the user is told once.
- After round 3, remaining must-fix items are by definition things prompts and edits could not settle: usually new data, a changed design, or a missing source the user must supply. Present them as a decision list, each with the reviewer's quoted sentence, and stop.

Expected pattern: round 1 finds the structural problems (major), round 2 verifies the fixes and finds what the fixes exposed (minor or a few must-fix), round 3 confirms. A manuscript still at `major` after round 3 should go back to stage 4 or 5, not to a fourth round.

## 6. What the panel cannot do

- It reads what is on disk. A design that is wrong cannot be fixed by wording: send it to [red-team.md](red-team.md) before data collection.
- It does not run new analyses or fetch new sources on its own (the field expert's two searches are the exception, and only produce suggestions).
- Verdict thresholds are this skill's defaults; a venue's own form outranks them whenever it exists.
- The scores are a reading aid, not a prediction of acceptance.
- A similarity (Turnitin) percentage is never estimated; the user runs it through the institution.

## 7. Merge template (`review/round-<k>/merged.md`)

```
# Panel verdict, round <k>
Manuscript: <path> (<N> lines, read at <date>)
Venue: <name + ISSN | thesis: <university> | unknown>
Guides used: author-guide.md (yes/no), journal-guide.md (yes/no)
Mode: parallel | sequential      Scope: full manuscript | literature chapter | <chapter name>

| Reviewer | design/gap/... scores | Verdict | Must | Should |
|---|---|---|---|---|
| methods | design_fit=2 sampling=1 instruments=3 bias_control=2 procedure_ethics=1 reporting=2 | major | 4 | 3 |
| statistics | ... | ... | ... | ... |
| field-expert | ... | ... | ... | ... |
| editor | ... | ... | ... | ... |
| arabic-language | ... | ... | ... | ... |
| theory | ... | ... | ... | ... |

PANEL VERDICT: reject | major | minor | accept   (worst single verdict)
Open must-fix: <n>   Open should-fix: <n>   Dropped (no quoted sentence): <n>

## Must fix (integrity first, then by line)
| id | tags | line | sentence | problem | fix | source |
|---|---|---|---|---|---|---|
| 1 | INTEGRITY statistics M1 | 3 | "After screening, N = 196 responses were analysed..." | n not in analysis output | ... | numbers |
| 2 | methods M1, theory M2 | 5 | "..." | ... | ... | ... |

## Should fix (by line)
| id | tags | line | sentence | problem | fix | source |
|---|---|---|---|---|---|---|

## Conflicts resolved
- line 12: field-expert wanted X, theory wanted Y; theory owns hypotheses -> Y. 

## Not checked (union of the six lists)
- ...

## Dropped objections (no quoted sentence)
- methods S3: "the sample is small" (no line, no quote)

## Next step
round <k+1> after fixing items 1..n  |  stop: no must-fix  |  stop: round 3, decisions for the user: items ...
```

## Verified sources

This document cites no methodological claim of its own. The claims inside each reviewer prompt are sourced there, with DOIs resolved by `python -X utf8 scholar.py verify <doi>`; the full list (35 DOIs) is at the end of [reviewers/methods.md](reviewers/methods.md) and [reviewers/statistics.md](reviewers/statistics.md).
