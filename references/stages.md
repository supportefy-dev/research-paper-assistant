# The 8 stages in detail

`S` = this skill's base directory + `/scripts` (normally `~/.claude/skills/research-paper-assistant/scripts`). Run from the project folder (`cd "<project>" && ...` in the same call) with `python -X utf8`.

## 1. Topic and gap

**Goal:** one research question narrow enough to answer, with a gap that real literature shows.

1. Get the basics in one message: field, population, country, degree or journal goal, deadline, data access (do they have data, or can they collect it?).
2. Search precisely. Quoted phrases with AND/OR beat loose words; `--core` keeps CWTS-core journals and drops most local or predatory outlets; `--has-doi` keeps only citable works:
   ```bash
   python -X utf8 "$S/scholar.py" search '"social media" AND "academic performance" AND Jordan' --since 2018 --core --out cand.json
   python -X utf8 "$S/scholar.py" search '"academic performance" AND (TikTok OR Instagram)' --sort cites --since 2015 --has-doi
   python -X utf8 "$S/scholar.py" search "القيادة التحويلية الأداء الوظيفي" --lang ar --type ""
   ```
   `--sort cites` finds the classics, `--sort recent` the frontier, the default ranks by relevance. Venues marked `*` are outside the core list: vet them before relying on them. `--source both` adds Semantic Scholar (slow, often throttled without a key). Each OpenAlex search costs 10 of a shared 1,000 daily credits without a key: plan searches, save them with `--out` (abstracts are saved by default).
   Known syntheses and meta-analyses: pull them by DOI (`scholar.py add <doi>`, 0 credits) instead of searching for them. Many Elsevier classics have no abstract in any index: budget a title-level citation for them, or ask the user for the PDFs.
3. **Arabic literature is thin in OpenAlex.** Also search by hand in Google Scholar, the Egyptian Knowledge Bank journals (journals.ekb.eg, DOIs 10.21608), ASJP (Algeria), Al Manhal, and Arab university repositories, then confirm each find with `verify --citation` or `add DOI`. Most Arab-university theses expect Arabic studies in the review: ask whether the user's programme requires them.
4. Map what exists with the two power tools (both read the saved candidates, so they cost few credits):
   ```bash
   python -X utf8 "$S/gapmap.py" run --topic '"social media" AND "academic performance"' --relation "social media|academic performance" --syn "social media=Facebook,Instagram,TikTok,social networking" --since 2015 --out gapmap.md --json gapmap.json
   python -X utf8 "$S/comap.py" build --in cand.json --out comap.md --html comap.html
   ```
   `gapmap` gives a population x country matrix, the studies that disagree (with the sentence each direction came from), empty cells, and 3 draft gap sentences marked [DRAFT, verify]. `comap` gives the schools of thought, seminal papers, the frontier and bridge papers from co-citations, plus a structure skeleton for the review. Both are regex/graph heuristics: confirm every direction, N and cluster name by reading before it reaches the manuscript.
5. Offer 3 candidate questions, each with: the gap (ideally a contradiction or an empty cell from gapmap), why it matters, the data needed, feasibility in the time available. The user chooses.

**Test:** the question fits in one sentence and names population, variables and setting.

| Weak | Strong |
|---|---|
| Social media and students | Does problematic TikTok use predict GPA among Jordanian public-university undergraduates, and is the effect mediated by sleep duration? |
| أثر القيادة على الأداء | أثر القيادة التحويلية على الأداء الوظيفي لموظفي البنوك التجارية الأردنية: الدور الوسيط للتمكين النفسي |

## 2. Literature

**Goal:** a ledger of sources actually read, organised by idea rather than by author, with the findings you will cite recorded as quotes.

0. When 2-5 key papers are known, snowball from them instead of guessing more keywords:
   ```bash
   python -X utf8 "$S/snowball.py" run --seeds 10.1016/j.chb.2010.03.024 10.1016/j.chb.2011.08.026 --topic "social media academic performance university students" --rounds 2 --out cand_snowball.json --prisma prisma.md
   ```
   Backward references and forward citers from OpenAlex (about 1 credit per batch), ranked by topic overlap, citations and co-citation; a retracted seed is flagged. `prisma.md` holds the counts for a systematic review's flow diagram.
1. From `cand*.json`, read titles, then abstracts: `scholar.py abstract <doi>` (tries OpenAlex, Crossref, Semantic Scholar, Europe PMC). No abstract anywhere: ask the user for the PDF or open an open-access copy (unpaywall.org, core.ac.uk). Until read, cite it only for what its title shows.
2. Add only what will be cited, saying what it supports:
   ```bash
   python -X utf8 "$S/scholar.py" add 10.1016/j.chb.2011.08.026 --note "Facebook time vs GPA (finding + N from the abstract)"
   python -X utf8 "$S/scholar.py" add 10.1080/0144929X.2021.1891460 --note "Jordan: SM addiction and performance" --read full
   ```
   `--read full` only when the full text was read. The default is `abstract`. A file of DOIs goes in at once with `add --dois-file dois.txt`. A manual, report or standard with no DOI or ISBN: `add --manual --title "..." --authors "Family, Given; Family, Given" --year 2020 --publisher "..." --url https://...` records it marked unverified, so the user knows it was never checked against a registry.
3. Read the `check:` lines `add` prints and fix the record (spelling and form only, never identity):
   ```bash
   python -X utf8 "$S/scholar.py" fix samedaladwan2020 --author "1:Al-Adwan,Ahmad Samed"     # Crossref name split
   python -X utf8 "$S/scholar.py" fix lau2017 --title "Effects of social media usage on ..."  # APA sentence case
   python -X utf8 "$S/scholar.py" fix junco2012 --year 2012                                   # must be a Crossref date
   ```
   `fix` refuses a different person, different title words, or a year Crossref does not hold, and changes nothing when any part is refused. A name hint that is right as it stands (a real one-word or compound family name) is silenced with `fix <key> --confirm-author N`. It may also drop ®/™ symbols, strip an English translation that Arabic registries append to a title (`العنوان = Title`), and fill a volume / issue / pages that the record leaves empty or 0 (in-press EKB records), taken from the journal page: `fix <key> --volume 6 --issue 3 --pages 76-107`. The sentence-case suggestion in `check:` lowers proper nouns: re-capitalise countries, platforms and named theories before pasting it.
4. Books and classics: `book --title ... --author ...`, then `add --isbn ... --edition-year ... --publisher ...` for the edition used.
5. Get the full texts and record the findings you will cite as verbatim quotes:
   ```bash
   python -X utf8 "$S/evidence.py" fetch                      # OA copies into fulltext/, user PDFs from papers/
   python -X utf8 "$S/evidence.py" quote --key junco2012 --claim "time on Facebook negatively related to GPA"
   python -X utf8 "$S/evidence.py" claim add --key junco2012 --page 193 --quote "..." --claim "..."
   ```
   `fetch` tries the user's `papers/` folder, OpenAlex OA locations, Europe PMC and arXiv, and Unpaywall only when `RESEARCH_MAILTO` is set; paywalled papers are never bypassed (ask the user to drop the PDF into `papers/`). `quote` finds candidate passages; `claim add` refuses a quote that is not verbatim in the text. A finding cited in the manuscript without a claim fails `evidence.py audit` at stage 8.
6. Build `matrix.md`: rows = themes, columns = sources, cells = finding + method + sample (from the quotes). The review is written from the matrix, theme by theme.

| Theme | source key 1 | source key 2 | source key 3 | Agreement |
|---|---|---|---|---|
| Time spent and GPA | direction, N, country, method | ... | ... | consistent / mixed / contradictory |

Fill each cell from the abstract or full text in the ledger, never from memory.

Size guide: master's thesis 40-80 sources, journal article 30-60, proposal 15-30. More than half from the last 5-7 years, plus the classics that define the constructs.

## 3. Verify sources

`add` already enforces this for new sources. For a list the user brings (the common "my supervisor says some references are fake" case):

```bash
python -X utf8 "$S/scholar.py" verify --citations-file refs.txt --add-to sources.jsonl
python -X utf8 "$S/scholar.py" verify 10.1016/j.chb.2010.03.024 "10.1016/S0140-6736(97)11096-0"
python -X utf8 "$S/scholar.py" verify --citation "Paul, J. A., ... (2012). Effect of online social networking ... 28(6), 2117-2127."
python -X utf8 "$S/scholar.py" book --isbn 9780029018101
```

`refs.txt`: one reference per line (or per blank-line block); numbering is stripped. It prints a verdict table, then corrected APA versions built from the registry, and with `--add-to` puts the confirmed ones in the ledger.

| Verdict | Meaning | Action |
|---|---|---|
| REAL | Exists and the details match | Use |
| REAL, ERRORS | Exists, but the citation has a wrong year / volume / issue / pages / journal (listed) | Use the corrected version |
| RETRACTED / CONCERN | Integrity notice | Remove, or discuss the retraction explicitly |
| FABRICATED? | No such paper, and its journal + volume + page belong to a different, real paper (named) | Remove: a typical AI hallucination |
| WRONG DOI | The DOI resolves to a different paper | Find the right DOI or remove |
| UNVERIFIED | No confident match | Ask the user for the DOI, ISBN or PDF; do not cite until shown |

Single-DOI verdicts: `found` / `found-non-crossref` (a DataCite DOI: dataset, arXiv, Zenodo) / `NOT-FOUND`, plus integrity `ok`, `corrected`, `retracted`, `expression_of_concern`, or "this DOI IS a notice" (the retraction notice, not the paper).

After `--add-to`, run `scholar.py list` and handle the `check:` hints (author splits, title case) with `fix`. The **Details** block under the table names the paper that really sits at a fabricated locator and the retraction notice DOI and date.

Report to the user as a short table: # | as cited | verdict | what was wrong | corrected reference. Supervisors want exactly that. Then tell the user:
- Every in-text citation whose year or author changed must be updated too (e.g. Kirschner & Karpinski 2011 becomes 2010); once they share the manuscript, run `refs --manuscript` and `audit`.
- Sentences that relied on removed references have lost their support: re-source or rewrite them.
- Entries added from a list are marked `read=metadata`: a real DOI does not prove the paper says what the sentence claims. Re-read at least the abstract of each.

## 4. Methodology

Draft the Methods with the user's real design, never an assumed one. Four tools make the design defensible before any data are collected:

| Tool | When | Command / doc |
|---|---|---|
| Theory fit | Every hypothesis | [theories.md](theories.md): 30 verified theories (EN/AR, original source DOIs); map each hypothesis to a proposition, or re-argue, relabel exploratory or drop it |
| Red team | Before data collection | [red-team.md](red-team.md): fill `design.md`, attack confounds, reverse causality, common-method bias, invariance, power, ethics; pick fixes from the decision table |
| Instruments | Any construct measured by questionnaire | `instruments.py find --construct "job satisfaction"` (validated scales, Arabic versions, reliability as candidates), `instruments.py protocol --scale "..." --from en --to ar` (back-translation checklist with verified Brislin/Beaton sources). Licence table in [instruments.md](instruments.md): never copy items from a commercial scale |
| Sample size | Always | `effects.py harvest --in cand.json --ledger sources.jsonl --relation "x|y"` (effect sizes reported in abstracts, as candidates), then `effects.py justify --test corr --effect 0.25 --source "key1; key2" --evidence analysis/output.txt --append` (EN + AR Methods paragraph, evidence lines). Power without `--source` prints UNJUSTIFIED |

`harvest` rarely finds `r` in abstracts for well-studied pairs (the classics report it only in the full text): fetch one OA full text in the target context first (`evidence.py fetch`, stage 2 step 5), then harvest again. `justify --label` names the evidence lines, and `--test mediation` sizes the indirect-effect test; both are in `--help`.

| Element | Must state |
|---|---|
| Design | e.g. cross-sectional correlational, quasi-experimental, qualitative phenomenological, mixed |
| Population and sample | Who, where, sampling method, N and how N was justified |
| Sample size | G*Power or formula: test, effect size (cite where it came from), alpha, power. Cohen's conventions only if no prior effect exists |
| Instruments | Name, source (in the ledger), items, scale, reliability in prior studies, translation and back-translation for Arabic versions |
| Validity and reliability | Pilot, Cronbach's alpha / CR / AVE planned |
| Procedure | Steps, dates, mode (online, paper) |
| Ethics | IRB / ethics committee approval number, consent, anonymity. Never invent an approval number: leave `[approval no.]` |
| Analysis plan | Software, the test for each question or hypothesis, assumption checks |

Qualitative work: sampling to saturation, interview guide, coding approach (e.g. thematic analysis, with its source in the ledger), trustworthiness.

## 5. Analysis

The user supplies the data. **Clean it first**, on the raw responses before reverse coding:

```bash
python -X utf8 "$S/autopsy.py" careless analysis/raw.csv --items q1 q2 q3 q4 --scale 1 5 --duration secs --id id --out analysis/autopsy.txt --clean analysis/data.csv
python -X utf8 "$S/autopsy.py" harman analysis/data.csv --items q1 q2 q3 q4 --items2 q5 q6 q7 >> analysis/output.txt     # common method bias: needs two or more constructs
```

Straight-liners, speeders, out-of-range values, duplicates and multivariate outliers are flagged with reasons (DROP vs REVIEW: the researcher decides the REVIEW rows); the `# APA:` line is the exclusion sentence for Methods with evidence keys `autopsy.before.n` / `autopsy.after.n`.

`analyze.py` covers the common cases with numpy + scipy only and writes `label = value` evidence lines plus a ready `# APA:` line:

```bash
mkdir -p analysis
A="$S/analyze.py"; D=analysis/data.csv; O=analysis/output.txt
python -X utf8 "$A" $D describe gpa sleep_hours >> $O
python -X utf8 "$A" $D freq gender >> $O
python -X utf8 "$A" $D corr sleep_hours gpa >> $O              # --spearman for ranks
python -X utf8 "$A" $D regress gpa sleep_hours stress --diagnostics >> $O   # B, SE, beta, t, p, CI, R2, F, VIF, sr2 + assumptions
python -X utf8 "$A" $D ttest gpa --by gender >> $O             # Welch t, df, p, d, mean difference + CI, Levene
python -X utf8 "$A" $D anova gpa --by faculty >> $O            # F, df, p, eta squared
python -X utf8 "$A" $D alpha q1 q2 q3 q4 --composite stress >> $O   # Cronbach's alpha; checks the composite = item mean
python -X utf8 "$A" $D describe stress --range 1 5 >> $O       # warns on out-of-range entries
```

- `ttest` subtracts in alphabetical group order and says so (`# order:` line): report the sign accordingly, or `numbers` flags SIGN DIFFERS.
- When the researcher's composite is not the item mean (a sum, a weighted score, an SPSS column), analyse the item mean and report the supplied score as a sensitivity analysis, saying so in the Methods.
- Any ad-hoc Python you run also needs `-X utf8`, or Arabic labels and the output file get mangled.
- Custom evidence lines must end with the statistic symbol (`power.min_detectable.d = 0.40`, not `...d_80`): `numbers` reads the last segment of the key as the label.

Indirect effects, interactions, measurement models and PLS (the usual Arab-university business thesis) use `analyze_sem.py`, same evidence format:

```bash
python -X utf8 "$S/analyze_sem.py" $D mediate --x leadership --m empowerment --y performance --boot 5000 >> $O   # PROCESS model 4
python -X utf8 "$S/analyze_sem.py" $D moderate --x stress --w support --y gpa --center >> $O                    # PROCESS model 1, simple slopes, Johnson-Neyman
python -X utf8 "$S/analyze_sem.py" $D cfa --model "TL = q1 q2 q3; JP = q4 q5 q6" >> $O                         # loadings, CR, AVE, HTMT, Fornell-Larcker; fit indices with semopy
python -X utf8 "$S/analyze_sem.py" $D pls --model "TL = q1 q2 q3; JP = q4 q5 q6" --paths "TL->JP" --boot 1000 >> $O
```
`analyze_sem.py selftest` reproduces Hayes' published PROCESS examples. The PLS command is a basic PLS path model; the output names what SmartPLS adds (PLSc, PLSpredict, MGA). Pilot item analysis for a new or translated scale: `instruments.py pilot data.csv --items q1 q2 ...`.

**Qualitative studies** (interviews, focus groups): `qual.py transcribe interview1.m4a --lang ar` (local Whisper, no cloud), `codebook init`, `code add --transcript ... --start mm:ss --end mm:ss --code C --coder A`, `agreement coding.jsonl --coders A B --evidence analysis/output.txt` (Cohen's kappa), `themes coding.jsonl --out themes.md` (counts, co-occurrence, best quotes with [transcript mm:ss], saturation curve), `quote --code C`. Speakers stay `null` until the researcher labels them; a transcript is ASR output until a human has checked it against the audio.

- Excel files: save as CSV first. Missing cells are dropped listwise per analysis and `n` / `excluded` are reported: write them in the Methods.
- Other software (SPSS, SmartPLS, AMOS, R, JASP): export the output to text or CSV in `analysis/`. Where possible rewrite key results as `label = value` lines (`r = 0.312`, `beta = 0.29`) so `numbers` checks each statistic against its own label.
- Check assumptions (normality, homoscedasticity, multicollinearity via VIF) and report what was done when they fail.
- Report effect sizes and confidence intervals, not only p-values.
- No data yet: write the analysis commands and a results template with `[ ]` placeholders; `numbers template.md` (no evidence) must PASS, proving no statistic slipped in.

## 6. Writing

See [writing-style.md](writing-style.md). Order: Methods, Results, Discussion, Literature review, Introduction, Conclusion, Abstract, Title. Every citation written as `Author (Year)` or `(Author, Year)` must exist in `scholar.py list`. Paste statistics from the `# APA:` lines; do not retype them.

## 7. Journal

See [journal-vetting.md](journal-vetting.md). Output `shortlist.md` in the project folder (so a later session can reuse it): 3 to 5 journals with SJR edition, the category quartile, scope evidence (2-3 recent on-topic papers from `search --issn <ISSN>`), APC and review time from the journal's own site, OA model, the `journal` signals, and the fit score:

```bash
python -X utf8 "$S/journalfit.py" profile --issn 0747-5632 --json            # house profile: refs per paper, methods, typical N, theories
python -X utf8 "$S/journalfit.py" fit --abstract my_abstract.txt --issn 0747-5632 --issn 0360-1315 --out fit.md
python -X utf8 "$S/journalfit.py" compare --manuscript paper.md --profile profile_0747-5632.json
```
`fit` is lexical (TF-IDF against the journal's recent abstracts): it ranks candidates and flags desk-reject risk, it does not judge novelty. An Arabic abstract needs an English version for English journals.

## 8. Pre-submission

Run all of these, fix, re-run until they pass:

```bash
python -X utf8 "$S/scholar.py" refs --manuscript paper.md > refs.md            # paste under References (--format ris for Zotero)
python -X utf8 "$S/scholar.py" audit paper.md                                   # --partial for one chapter/section
python -X utf8 "$S/evidence.py" audit paper.md                                  # every cited finding has a live verbatim quote; no full text = WARN, --strict makes it FAIL
python -X utf8 "$S/scholar.py" numbers results.md --evidence analysis/output.txt
python -X utf8 "$S/autopsy.py" statcheck results.md                             # every reported p agrees with its test and df
python -X utf8 "$S/scholar.py" numbers litreview.md --ledger sources.jsonl      # figures quoted from abstracts
python -X utf8 "$S/similarity.py" check paper.md --out similarity.md            # exact and near copies vs the ledger and full texts
python -X utf8 "$S/evidence.py" trail paper.md --out evidence-trail.md --html evidence-trail.html   # appendix for the supervisor
python -X utf8 "$S/build_docx.py" paper.md -o paper.docx --preset ju            # --list-presets; apa7 for journals
```

- `refs` options: `--heading "المراجع"`, `--arabic-first` (Arabic references first, as many Arab universities require). Any `check:` lines it prints go to `fix`.
- `audit --keys` also counts ledger keys written in coaching notes or matrices. The manuscript goes positionally or as `--manuscript`.
- `numbers` skips the References section in every mode, takes `--evidence` and `--ledger` together, strips `[bracketed placeholders]`, ignores section numbers (`section 3.2`), reads thousands separators (15,199) and knows the `ab` / indirect, `pm`, Cook's D and VIF labels.
- `numbers` verdicts: UNSUPPORTED (no such value), SIGN DIFFERS (fail: direction is the finding), WEAK MATCH (matched only an unlabelled number: label the evidence and re-run).
- `numbers` reads statistics written in APA italics (`*r*(197) = .31`), labels table cells by their column header (M, SD, B, *p*...), and skips the AI-use declaration and `<!-- notes -->`. In ledger mode it also checks counts (sample sizes, number of studies) against the abstracts; weak matches there are expected and must be confirmed against the cited source.
- `build_docx.py`: A4 by default (`--paper letter` for US journals); write significance stars as `\*\*`; `<!-- notes -->` are dropped; `--table-style grid` if the university wants all borders. Put a blank line between a table note and a probability note, or they merge into one paragraph. In Arabic paragraphs write decimals with a leading zero (0.44, not .44): it is the Arabic norm and renders unambiguously.
- `--preset ju|yarmouk|just|ksu|qu|mutah|uaeu|cairo|generic-arab|apa7` applies the university's margins (binding side), fonts, spacing, a cover page from a `---` block (title, author, supervisor, university, degree, year), TOC and list-of-tables fields and roman front-matter numbering. `--list-presets` says which presets were verified against the real guide and when ([university-presets.md](university-presets.md)); re-read the guide before a submission.
- Check the Word file by converting it to PDF and looking at it, especially the Arabic pages. On Windows with Word installed (fields updated first, or the TOC shows a placeholder):
  ```bash
  powershell.exe -NoProfile -Command "$w=New-Object -ComObject Word.Application; $d=$w.Documents.Open('C:\full\path\paper.docx'); $d.Fields.Update() | Out-Null; foreach ($t in $d.TablesOfContents) { $t.Update() }; $d.SaveAs([ref]'C:\full\path\paper.pdf',[ref]17); $d.Close(); $w.Quit()"
  python -X utf8 -c "import fitz; d=fitz.open('paper.pdf'); d[0].get_pixmap(matrix=fitz.Matrix(1.6,1.6)).save('page1.png')"
  ```
  then read `page1.png` (PyMuPDF is installed; `pdftoppm` is not). From the Bash tool, escape each `$` in the PowerShell part as `\$`.

**Review panel.** First see what real reviewers in the field object to: `reviews.py pull --query "<paper keywords>" --source all --n 20 --out reviews.jsonl` then `reviews.py classify reviews.jsonl --out complaints.md` (open reviews exist for ML/CS, life science and F1000; for business and education the published studies in [reviewer-complaints.md](reviewer-complaints.md) stand in). Then run the 6 reviewer prompts in `references/reviewers/` (methods, statistics, field expert, editor, Arabic language, theory) as parallel subagents, merge with the template in [review-panel.md](review-panel.md), fix every "must fix", and re-run until none remains or 3 rounds. The venue's own reviewer guidelines outrank the defaults when they can be fetched. Build `paper.docx` and convert it to PDF before the panel runs: the Arabic-language reviewer checks the rendered pages. When parallel agents are unavailable, run the six one after another and say so in `merged.md`.

**Final checks:** the AI disclosure in the right section; the cover letter (3 short paragraphs: what was studied, the main finding and why it matters to this journal's readers, the declarations); the author guidelines checklist (word limit, reference style, anonymised file for double-blind review); the university's similarity check (Turnitin or iThenticate) after `similarity.py` passed.

## 9. After submission

| Need | Command / doc |
|---|---|
| Reproducibility package for OSF or the journal | `package.py build --project . --data analysis/data.csv --out reproducibility.zip` (data dictionary, scripts, evidence, ledger, README with rerun commands and SHA-256, CITATION.cff; key files and anything outside the project are refused), then fill the `description` column and the [bracket] placeholders; `package.py verify reproducibility.zip` |
| Keep the review current until the defense | `watch.py add --name topic --query '"a" AND "b"' --since 2024`, `watch.py run` (new OpenAlex works since the last run, 10 credits per query), `watch.py schedule` prints the weekly Task Scheduler command for the user to create |
| Defense (المناقشة) | [defense.md](defense.md): 5 committee personas x 10 page-anchored questions generated from the thesis, claim / evidence location / limit answers, 20-slide deck outline, mock-viva protocol, AR + EN stems |
| Five outputs from one study | [deliverables.md](deliverables.md): structured conference abstract, Arabic policy brief, LinkedIn post, lay summary; `deliverables.py visual --evidence analysis/output.txt --labels "corr.sleep~gpa.r:Sleep and GPA" --title "..." --out visual_abstract.svg` (numbers only from evidence lines); `deliverables.py check brief.md --kind brief --evidence analysis/output.txt` |
