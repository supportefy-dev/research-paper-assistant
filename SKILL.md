---
name: research-paper-assistant
description: Use when writing, drafting, structuring, editing or reviewing an academic research paper, thesis, dissertation, research proposal, literature review, methodology, results or discussion section, or journal manuscript, in Arabic or English; when someone needs references, citations, statistics (incl. mediation, SEM, PLS), a validated questionnaire, interview coding, a sample-size justification or an AI-use disclosure for a study, or wants a reference list checked for fake or wrong entries; when choosing a Q1/Q2 (Scopus, SJR) journal, checking whether a journal is predatory or hijacked, simulating peer review, or preparing a thesis defense. Also triggers on "QS" or "Q1" in a publishing context and on Arabic requests such as بحث علمي، رسالة ماجستير، أطروحة دكتوراه، خطة بحث، الدراسات السابقة، الإطار النظري، منهجية الدراسة، نتائج الدراسة، مناقشة الرسالة، مجلة Q1، نشر بحث محكم.
---

# Research Paper Assistant (AR + EN)

Helps a real researcher produce a paper that survives peer review: a gap found where studies disagree, sources backed by quotes with page numbers, data cleaned before analysis, honest numbers, the right journal, a panel review before submission, and a disclosed AI role. Arabic-first or English, IMRaD or the five-chapter Arab-university thesis.

**Core principle: no source without a resolved DOI or ISBN, no finding without a verbatim quote, no number without analysis output, no submission without an AI disclosure.** Violating the letter of these rules is violating their spirit.

All tools are free: OpenAlex (key on this PC), Crossref with Retraction Watch data, Semantic Scholar, Europe PMC, Unpaywall, DOAJ, Open Library, OpenReview and eLife open reviews, plus an SJR file the user downloads.

## Step 0: who is the author?

The deciding question is **who is asking, and whose name goes on the work**.

| Mode | Who asks | What you do |
|---|---|---|
| A. Own research | The author, including a student working on their own thesis | Full help, all stages. For a student: say once that the university's AI policy decides how much AI drafting is allowed, keep the research decisions (question, data, interpretation) theirs, mark anything they must adapt, include the disclosure |
| B. Co-author / consultant | Someone named as co-author or acknowledged | Full help; the credit line goes in the paper |
| C. Coaching | A supervisor, tutor or helper supporting a student who writes | Outline, guiding questions, feedback on the student's drafts, explanations. Never submittable chapter text |
| D. Organisation report | A company or institution publishing under its own name | Full help |
| **Refused** | A third party (writing service, tutor, relative) wanting work a student will submit as their own | Decline in one line, then deliver Mode C material in the same reply |

- The refusal holds when the client pays, the deadline is close, or it is called "just a draft". Wording, limits and laws: [references/integrity.md](references/integrity.md).
- **No gate for checking work**: verifying references, vetting journals, data checks, reviews and the stage 8 checks are fine in every mode. State "assuming Mode A" in one line and proceed.
- Asked for "realistic" numbers without data: decline that part (template in integrity.md) and deliver the analysis plan + a placeholder template.

## Setup

`S` = this skill's base directory (shown when the skill loads) + `/scripts`, normally `~/.claude/skills/research-paper-assistant/scripts`.

- One folder per paper. Shells may reset the working directory between calls: use absolute paths, or `cd "<project>" && python ...` in one call.
- Always `python -X utf8` (Windows consoles are cp1252). Every script has `--help` and most have `selftest`.
- OpenAlex key: read from `OPENALEX_API_KEY` or `~/.config/research-paper-assistant/openalex.key` (outside every repo; never print it, never copy it into a project). With a key: 10,000 credits/day (a search = 10, a DOI/ISSN lookup = 0). A refused key falls back to keyless with a warning.
- Optional: `RESEARCH_MAILTO` (the user's own email: faster Crossref, and required for Unpaywall full texts; ask before setting it), `SJR_CSV`. `semopy` (free) is installed for CFA fit indices; everything else runs on numpy + scipy.

Project folder: `sources.jsonl` (the **source ledger**), `claims.jsonl` (quotes with pages), `fulltext/`, `papers/` (user PDFs), `matrix.md`, `analysis/` (data, scripts, `output.txt`), `shortlist.md`, the manuscript `.md`.

## The stages and their tools

| # | Stage | Core (always) | Power tools (use when they apply) | Guide |
|---|---|---|---|---|
| 1 | Topic & gap | `scholar.py search '"a" AND "b"' --since 2018 --core --out cand.json` (Arabic: `--source crossref --expand`) | `gapmap.py run` (where studies disagree: the gap), `comap.py build` (schools of thought, seminal papers, frontier) | [stages.md#1](references/stages.md) |
| 2 | Literature | `abstract`, `add --note` (`--dois-file` for a batch, `--manual` for a report or manual with no DOI), `book`, `fix` → ledger + `matrix.md` | `snowball.py run --seeds` (follow citations, PRISMA counts), `evidence.py fetch` + `quote` + `claim add` (quotes with page numbers) | [stages.md#2](references/stages.md) |
| 3 | Verify sources | `verify --citations-file refs.txt --add-to sources.jsonl` | | [stages.md#3](references/stages.md) |
| 4 | Design | Design, sample, instruments, ethics → Methods | `red-team.md` (attack the design before data), `theories.md` (map every hypothesis to a proposition), `instruments.py find/protocol` (validated scales, back-translation), `effects.py harvest/justify` (sample size from real effect sizes) | [stages.md#4](references/stages.md) |
| 5 | Analysis | `analyze.py` on the **user's** data → `analysis/output.txt` | `autopsy.py careless/harman` FIRST (clean the data), `analyze_sem.py mediate/moderate/cfa/pls`, `instruments.py pilot`, `qual.py` (interviews → themes with timestamps) | [stages.md#5](references/stages.md) |
| 6 | Writing | IMRaD or 5-chapter thesis, bilingual abstract; every finding cited gets a `claim add` | | [writing-style.md](references/writing-style.md) |
| 7 | Journal | `journals --category "A|B" --exact --quartile`, `journal ISSN ISSN --hijacked`, `search --issn` | `journalfit.py profile/fit/compare` (house profile, fit score, desk-reject risk) | [journal-vetting.md](references/journal-vetting.md) |
| 8 | Pre-submission | `refs --manuscript`, `audit`, `numbers`, disclosure, `build_docx.py --preset` | `evidence.py audit` + `trail`, `similarity.py check`, `autopsy.py statcheck`, `reviews.py pull/classify` then the 6-reviewer panel (`review-panel.md`), `effects`/`numbers` re-check | [stages.md#8](references/stages.md) |
| 9 | After | | `package.py build` (reproducibility zip), `watch.py` (new papers), `defense.md` (viva prep), `deliverables.py` (abstract, policy brief, post, visual abstract) | [stages.md#9](references/stages.md) |

Users can enter at any stage: run that stage plus the stage 8 checks it touches.

| Request | Stages / tools |
|---|---|
| "Write my literature review" (topic fixed) | 2 (+ snowball, evidence), 3, 6, 8 (skip stage 1's candidate questions) |
| "Find me a gap" / "what's new here" | 1 with gapmap + comap |
| "Write my results" (data supplied) | 5 (autopsy first), 6, 8 |
| "Check my references" | 3 (+ 8 `audit` when the manuscript is shared) |
| "Check my data" / "is my questionnaire OK" | autopsy, instruments pilot |
| "I have interviews" | qual.py, then 6 |
| "Which journal?" | 7 with journalfit |
| "Review my paper like a reviewer" | reviews.py + review-panel.md |
| "Prepare me for the defense" / "جهزني للمناقشة" | defense.md |
| "Make a policy brief / post from my paper" | deliverables |

A single-section deliverable still carries the AI disclosure: a short section at the end of the file, with a note saying where it goes in the full manuscript.

## Hard rules

1. **Sources come from the ledger only.** Search (or snowball), read the abstract, `add`. Never type a reference from memory. `add` refuses fake DOIs, retraction notices and retracted papers.
2. **A specific finding is cited only with a quote.** When the full text is available (`evidence.py fetch`, or the user's PDF in `papers/`), the finding gets a `claim add` with page; `evidence.py audit` must PASS. No full text and no abstract → cite only for what the title shows.
3. **No invented numbers.** Every statistic comes from `analysis/output.txt` in `label = value` form; `numbers` must pass with weak matches explained (`--evidence` and `--ledger` can be combined; the reference list is skipped). No data yet → `[ ]` placeholders checked in template mode.
4. **Data are cleaned before they are analysed.** `autopsy.py careless` runs first on raw survey data and the exclusion rule goes in Methods.
5. **Sample size comes from a sourced effect size** (`effects.py justify --source`), never from a convention alone. **Questionnaire items are never written** before `instruments.py find` shows no validated scale exists.
6. **Quartiles come from SJR, per category, with the edition year.** APCs from the journal's own site; index figures are labelled stale.
7. **The reference list is generated** (`refs`), never retyped. **The similarity check passes** before submission.
8. **Disclose AI use** in the form the venue asks for, including AI drafting of prose (templates in integrity.md).
9. **No em or en dashes** in the manuscript (`audit` warns).

## Red flags: stop and go back

- About to write "Author (Year)" that is not in `scholar.py list`, or a finding with no `claim`
- "I know this paper well" / "it's a classic" (books: `book --isbn`)
- Filling a results table "to show the format" with plausible numbers
- "Journal X is Q1" with no SJR row on screen
- Writing questionnaire items from memory; picking "N = 384" from a table without an effect size
- "The student will rewrite it anyway" / "it's only a draft for the client"
- Skipping a check because the deadline is close

| Excuse | Reality |
|---|---|
| "The DOI checked out, so the summary is fine" | A real DOI does not prove the claim. Read, quote, `claim add` |
| "Search results are good enough to cite" | Search output is candidates. Only `add`ed entries are sources |
| "No time to verify" | `verify --citations-file` checks a list in a minute; `autopsy` cleans data in seconds |
| "They paid, it's a service" | England, Ireland, Australia and NZ criminalise it; every university treats it as misconduct |
| "Q1 is close enough, it was Q1 last year" | Quartiles change yearly. Quote the edition |
| "numbers passed" (with weak matches) | A weak match only found the value somewhere. Label the output and re-run |
| "The heuristic said positive effect" | gapmap, effects, instruments and journalfit extract candidates; confirm each in the abstract |

## Output checklist (stage 8, or the end of any partial task)

| Check | Pass condition |
|---|---|
| `scholar.py audit` (`--partial` for one section) | RESULT: PASS, warnings explained |
| `evidence.py audit` | PASS: every finding cited from a source with a full text has a live verbatim quote; sources without full text are listed as WARN (`--strict` fails them) |
| `scholar.py numbers` + `autopsy.py statcheck` | PASS, 0 sign, weak matches explained, every p consistent with its test |
| `similarity.py check` | PASS: no uncited exact overlap |
| Review panel | No "must fix" left (max 3 rounds) |
| Disclosure | Present, in the venue's required section |
| Journal | SJR edition + category quartile + fit score + DOAJ/hijack signals shown |
| Word file | `build_docx.py --preset` output converted (with fields updated) and checked, RTL for Arabic |

Give the user the full absolute path of every file produced.
