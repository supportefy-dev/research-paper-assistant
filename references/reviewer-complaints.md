# Reviewer complaints: what real reviewers object to, and the pre-review checklist

Why this file exists: the stage 8 reviewer pass is only as good as the objections it looks for. This file gives the panel (a) a taxonomy of reviewer objections, (b) their frequencies from a live pull of public reviews and from published studies of reviewer comments, (c) a checklist per category to run before submission, and (d) the rules for using it in the review prompts. Tool: `scripts/reviews.py`.

Honesty first: the open sources that expose full reviews are ML/CS conferences (OpenReview), life sciences (eLife) and an open-publishing platform (F1000Research). Business, education and social-science journals almost never publish their reviews, so for those fields the evidence comes from published studies of reviewer comments (section 3), not from the live pull. Arabic-language reviews exist in none of the sources.

## 1. Commands

```
python -X utf8 S/reviews.py pull --query "social media academic performance" --source all --n 20 --out reviews.jsonl
python -X utf8 S/reviews.py pull --query "..." --source elife|openreview|f1000|peerj --n 20 --out reviews.jsonl [--since 2018] [--append] [--loose]
python -X utf8 S/reviews.py classify reviews.jsonl --out complaints.md [--examples 3] [--show-untagged 20] [--source f1000,elife]
python -X utf8 S/reviews.py selftest
```

- `pull` writes one JSON per line: `source, review_id, url, paper_title, paper_url, venue, year, reviewer, kind, recommendation, text, strengths, summary, query, pulled`. `text` is the complaint-bearing part (weaknesses, questions, limitations, the free-text review or report); strengths and summary are kept apart.
- Every source matches full text OR-style, so a hit that contains fewer than half of the query words is dropped (printed as "skipped N"); `--loose` keeps them. A query with no hits prints `RESULT: FAIL (0 reviews)` and exit code 1. Nothing is ever invented.
- `classify` splits `text` into sentences, drops strengths blocks and form boilerplate ("I confirm that I have read this submission...", "Thank you for submitting..."), tags each sentence with a regex taxonomy (a sentence can carry several tags) and prints frequencies plus verbatim examples attributed to the review URL. Untagged sentences are listed with `--show-untagged N` so the taxonomy can be extended.
- `selftest` runs the classifier on five real review sentences (positive) and three planted boilerplate lines (negative control: must be dropped), checks strengths stripping, and checks that an empty file yields `0 reviews`.

### Source status (verified live 2026-10-21)

| Source | Endpoint | What comes back | Status |
|---|---|---|---|
| OpenReview | `api2.openreview.net/notes/search?term=...&source=reply` (keyless) | `Official_Review` notes with summary / strengths / weaknesses / questions / rating, or a free-text `review`; ICLR, NeurIPS, smaller venues | Works. The paper note (`notes?id=` or `?forum=`) answers 403 "Challenge verification required" to guests, so `paper_title` is empty unless the review repeats it; `paper_url` still opens the forum in a browser |
| eLife | `api.elifesciences.org/search?for=...&type[]=research-article` then `/articles/{id}` | `publicReviews` (2023+ model, one record per reviewer, each with its own DOI) or `decisionLetter` (2013-2022 model: the editor's merged list of essential revisions) | Works. Reviewed preprints expose only the short `elifeAssessment` through the API, so they are skipped |
| F1000Research | `f1000research.com/extapi/search?q=...&page=N` (100 DOIs per page) then `/extapi/article/xml?doi=...` | JATS with `<sub-article article-type="reviewer-report">`: reviewer name, report DOI (10.5256/...), recommendation (approve / approve-with-reservations / reject), full text | Works. Search relevance is loose (full-text), hence the half-the-words filter |
| PeerJ | `peerj.com/articles/index.json`, `/articles/<id>/reviews/`, `.xml`, `.json` | Review histories exist on the site | Blocked: every article and review URL returns a Cloudflare challenge page (HTTP 403) to scripts, with a browser user agent too; the search page is JS-rendered. `pull --source peerj` tries once, prints the browser URL and returns 0 |

## 2. Live pull (query "social media academic performance", 2026-10-21)

`pull --source all --n 20`: openreview 20 reviews (16 papers; ICLR 2025/2026, NeurIPS 2023/2024, MathAI 2026), elife 2 (10 scanned, 8 skipped as off-topic), f1000 20 (7 papers, 2014-2020), peerj 0 (blocked). 42 reviews, 1,158 sentences after boilerplate removal, 592 tagged.

| Category | Sentences | % of tagged | Reviews touching it |
|---|---|---|---|
| Theory / rationale / definitions | 145 | 24% | 28/42 |
| Literature coverage / comparisons | 135 | 23% | 31/42 |
| Statistics / analysis | 126 | 21% | 29/42 |
| Methodology / sample / design | 121 | 20% | 28/42 |
| Figures / tables | 69 | 12% | 21/42 |
| Writing / clarity / presentation | 64 | 11% | 22/42 |
| Novelty / contribution / motivation | 54 | 9% | 21/42 |
| Ethics / data and code availability / reporting | 51 | 9% | 15/42 |
| Overclaiming / causal language / limitations | 20 | 3% | 9/42 |

Read these as keyword counts, not as a measurement: "theory" is inflated by words such as "hypothesis" and "assumption" that ML reviewers use loosely, and "overclaiming" is deflated because reviewers phrase it indirectly ("the data do not allow this conclusion"). The column that matters most is "reviews touching it": literature coverage, statistics, methodology and theory each appear in two thirds of reviews.

Three classified sentences, verbatim:

- Methodology / sample: "Limited Dataset Evaluation: The experiments are confined to the Social Media Prediction Dataset (SMPD)." (OpenReview, ICLR 2025, https://openreview.net/forum?noteId=bvzfqP46ZH&id=adrPcTD2cz)
- Statistics / analysis: "Alpha values, and hence p-values, should be adjusted to account for Type-I error on the confirmatory tests." (F1000Research, Brian M. Donovan, 2018, https://doi.org/10.5256/f1000research.10808.r18117)
- Ethics / reporting: "Although strongly mitigated by the fact that the main results are replicated, one possible drawback of the study is that it was not preregistered." (eLife decision letter, 2023, https://doi.org/10.7554/eLife.85767.sa1)

Rerun the pull with the paper's own keywords before a review pass; the complaints of the closest field are the ones to weigh.

## 3. Published studies of reviewer comments (DOIs verified with `scholar.py verify`, 2026-10-21)

Numbers below are only those stated in each abstract; "no figure in abstract" means the full text was not read for this file.

| Study | Field, material | What reviewers complained about (as reported) |
|---|---|---|
| Bordage (2001), Academic Medicine, https://doi.org/10.1097/00001888-200109000-00010 | Medical education; 151 manuscripts to the RIME conference, 123 with an exclude rating; 4.1 reviewers per paper, 8.1 reasons per excluding reviewer | Top ten reasons for rejection, in order: inappropriate or incomplete statistics; overinterpretation of results; inappropriate or suboptimal instrumentation; sample too small or biased; text difficult to follow; insufficient problem statement; inaccurate or inconsistent data reported; incomplete, inaccurate or outdated literature review; insufficient data presented; defective tables or figures. Strengths of accepted papers: importance of the problem, writing, sound design |
| Stout, Rebele and Howard (2006), Issues in Accounting Education, https://doi.org/10.2308/iace.2006.21.2.81 | Accounting education (business + education); about 500 manuscripts over ten years at two journals, content analysis of rejected files | Most rejections happen after the first round. Primary reasons: a poorly motivated study, a poorly designed study, an insignificant contribution to the literature. Poor writing is the common secondary reason. After resubmission the main reason is failing to address earlier reviewer concerns. No percentages in the abstract |
| Wyness, McGhee and Patel (2009), Clinical and Experimental Ophthalmology, https://doi.org/10.1111/j.1442-9071.2009.02190.x | Ophthalmology; 662 submissions in 2008, rejection rate 73.6%; content analysis of reviewer and editor comments on rejected papers | In order: does not add to current literature; poor methodology; problematic control groups; poor English and grammar / poorly organised; needs further work or clarification; simultaneous submission or plagiarism |
| van Lent, Overbeke and Out (2015), BMJ Open, https://doi.org/10.1136/bmjopen-2015-007961 | Medicine; reviewer reports on 246 drug-trial manuscripts at eight journals, predefined checklist | Poor experimental design in 52.9% to 69.7% of manuscripts depending on sponsorship; inappropriate statistical analyses 15.1% to 28.4%; inappropriate conclusions 29.3% (negative results) vs 18.9% (positive); rejected papers drew more comments on lack of novelty (8.3% vs 2.6%) and on the question not being clinically relevant (7.8% vs 1.6%) |
| Hesterman et al. (2018), Headache, https://doi.org/10.1111/head.13343 | Neurology; 784 submissions 2014-2016, 434 peer reviewed, rejection after review 35.7% | Six most common reasons: flaws in methodology and study design; poor reporting of methodology; poor statistical analysis; overstatement of conclusions; problems with covariates or outcomes; problems with the control or case group |
| Menon et al. (2020 online, 2022 print), Indian Journal of Psychological Medicine, https://doi.org/10.1177/0253717620965845 | Psychiatry; 898 rejection reports 2018-2020, predefined coding frame | Desk rejection: lack of novelty, out of scope. After peer review: inappropriate study design, poor methodological description, poor writing, weak rationale. Rejection rates 26.7% (viewpoints) to 72.1% (reviews) |
| O'Brien et al. (2021), PLoS ONE, https://doi.org/10.1371/journal.pone.0260558 | Health professions education; 358 reviews of 168 manuscripts, qualitative content analysis of confidential comments to the editor | 49% of reviews carried comments to the editor; of these, 56% addressed argument quality and 51% research design / methods / data; tone critical 40%, constructive 34%; for "reject" reviews, 80% of the editor comments also appeared in the comments to authors |
| Tharirian and Sadri (2013), Journal of Teaching Language Skills, https://doi.org/10.22099/jtls.2013.1558 (DOI registered outside Crossref; venue outside the CWTS core list, treat as supplementary) | Applied linguistics; reviewer reports on 32 manuscripts by Iranian authors in engineering, medicine and social sciences | Content defects first (procedural problems, poor study design, ignoring the literature), language problems second (lexico-grammar, clarity, spelling, verbosity); the two overlap |

A ninth candidate, Bornmann et al. (2012) on public reviews at Atmospheric Chemistry and Physics (https://doi.org/10.1007/s11192-012-0731-8), is real but its abstract was not retrievable through the APIs, so no finding is quoted.

### What the two bodies of evidence agree on

| Rank | Objection | Evidence |
|---|---|---|
| 1 | Design and methodology (sample, controls, instruments, procedure) | First or second in every published study; 20% of tagged sentences live, 28/42 reviews |
| 2 | Statistics and analysis, including reporting of data | Bordage's #1 reason; 15-28% of trials (van Lent); #3 at Headache; 21% live, 29/42 reviews |
| 3 | Contribution, motivation and fit (novelty, gap, scope, relevance) | Stout's three primary reasons; Wyness's #1; Menon's desk-rejection reasons; low live count (9%) because ML venues score it as a number rather than prose |
| 4 | Literature coverage and comparison with prior work | Bordage #8; Wyness #1 phrased as "does not add"; 23% live, 31/42 reviews (ML reviewers ask for baselines) |
| 5 | Overclaiming: conclusions beyond the data, causal wording | Bordage #2 ("overinterpretation"); Headache #4; 29% of negative-result trials (van Lent); the live count (3%) undercounts it |
| 6 | Writing and clarity | Secondary reason in Stout; #4 at Wyness; Bordage #5; 11% live |
| 7 | Theory and rationale | "Weak rationale" (Menon), "insufficient problem statement" (Bordage #6), "poorly motivated" (Stout); 24% live but keyword-inflated |
| 8 | Figures and tables | Bordage #10; 12% live |
| 9 | Ethics, data and code availability, reporting standards | Rare in older studies; rising in the live pull (preregistration, data bias, privacy, code release) |

Field note: in business and education journals the decisive complaints are motivation, contribution and design (Stout 2006; Menon 2020), and the failure that kills a resubmission is not answering the previous round. In medicine the decisive complaints are design, statistics and overstatement. Writing is rarely the sole reason for rejection but it is almost always present.

## 4. Pre-review checklist (run before the reviewer pass, every item answered with a page or section number)

For each item the agent records: location in the manuscript, pass / fix / cannot tell, and the one-line fix. "Cannot tell" is allowed; "looks fine" without a location is not.

### 4.1 Methodology / sample / design
- The design can answer the stated question (a correlational design is not asked to show change; a cross-sectional survey is not asked to show order of events).
- Sample size is justified before the fact (power analysis, saturation rule, or the sampling frame), and the achieved N, response rate and exclusions are reported.
- Sampling and recruitment are described well enough to judge representativeness; a convenience sample is named as such and its limits stated.
- Control or comparison group exists where a claim of effect is made, and is comparable on the obvious confounders.
- Instruments: source, adaptation, translation procedure, reliability (alpha or omega) and validity evidence in this sample, not only in the original paper.
- Procedure is reproducible from the text: who collected what, when, in what order, with what instructions.
- Single-site, single-dataset or single-country designs are flagged as such in the limitations.

### 4.2 Statistics / analysis
- Every test matches the data type and design (paired vs independent, nested data, ordinal scales), and assumptions were checked and reported (`analyze.py` output in `analysis/output.txt`).
- Effect sizes and confidence intervals accompany p-values; "marginally significant" does not appear.
- Multiple comparisons are acknowledged and corrected, or the analysis is declared exploratory.
- Missing data: amount, pattern, handling.
- Descriptives (M, SD, n) are complete for every group in every test; numbers in text, tables and abstract agree (`scholar.py numbers`).
- No analysis is described that does not appear in results, and no result lacks its analysis.

### 4.3 Novelty / contribution / motivation
- The gap is stated in one sentence with the two or three papers that come closest, and why they leave it open (stage 1 output).
- The contribution is named explicitly (what is known after this paper that was not known before) and matches what the results show.
- Scope fits the target journal (`scholar.py search --issn`, stage 7); the abstract makes the contribution visible in the first three sentences.
- Practical or theoretical implications are concrete, not "has implications for policy".

### 4.4 Theory / rationale / definitions
- Each hypothesis is derived from a named theory or prior finding, not asserted.
- Every key construct has one definition, used consistently, with its operational measure named next to it.
- The model (variables and the direction of each arrow) is drawn or stated once and matches the analysis.
- Assumptions that the argument depends on are stated and, where possible, tested.

### 4.5 Writing / clarity / presentation
- Reader can state the question, design and main finding after the abstract and the first page.
- Terms, acronyms and notation are defined at first use; one term per concept.
- Sections follow the venue's structure; no paragraph repeats another; the discussion does not restate results.
- Grammar and spelling pass; the file is free of em and en dashes (`scholar.py audit`).
- Length, headings and reference style follow the author guidelines.

### 4.6 Literature coverage / comparisons
- The closest prior work is cited and discussed, including work that disagrees with the findings.
- Recent work (last five years) and the seminal sources are both present; nothing cited from memory (ledger only, `scholar.py audit`).
- Findings are compared with earlier findings in the discussion, with direction and size, not just "consistent with".
- No reference is retracted, fabricated or misattributed (`scholar.py verify --citations-file`).

### 4.7 Ethics / data and code availability / reporting
- Ethics approval (body, number) and consent are stated where humans or their data are involved; anonymisation described.
- Data availability statement present; code or analysis script available or its absence explained.
- Reporting guideline named where one exists (CONSORT, STROBE, PRISMA, COREQ) and the checklist attached.
- Conflicts of interest, funding and the AI-use disclosure are present in the sections the venue requires (`integrity.md`).
- Preregistration status stated, or exploratory status declared.

### 4.8 Overclaiming / causal language / limitations
- Verbs match the design: correlational studies "are associated with", "predict" (statistically), never "cause", "lead to", "improve" unless the design supports it.
- Conclusions do not exceed the sample, the measures or the time frame; the title and abstract make no claim the results section does not.
- Limitations section names the design, sample and measurement limits that a hostile reviewer would raise, and says what each one does to the conclusions.
- Null and negative results are reported, not reinterpreted as support.

### 4.9 Figures / tables
- Every table and figure is cited in the text, numbered in order, self-explanatory from its caption, with units and n.
- Axes labelled, error bars defined, legends complete, resolution adequate; no table that repeats the text.
- Values in tables agree with the text (`scholar.py numbers`).

## 5. How the review panel uses this file

The stage 8 reviewer pass (stages.md) reads the manuscript as three reviewers: Methods, Field expert, Editor. Assign the categories to them:

| Reviewer | Categories owned | Weight from the evidence |
|---|---|---|
| Methods | 4.1 methodology, 4.2 statistics, 4.8 overclaiming, 4.9 figures | The reasons that reject papers in medicine and that fill two thirds of open reviews |
| Field expert | 4.3 contribution, 4.4 theory, 4.6 literature | The reasons that reject papers in business and education (Stout; Menon) |
| Editor | 4.5 writing, 4.7 ethics and reporting, scope and guidelines | Rarely fatal alone; always present; decides desk rejection |

Rules for the prompts:

1. Each reviewer works through its checklist items in order and reports every item as pass / fix / cannot tell with a location. A reviewer that reports only strengths has not reviewed.
2. Each "fix" is written the way reviewers write it: the objection, where it is, what would satisfy it. Severity is labelled fatal (the design cannot answer the question, a claim the data cannot support, a fabricated or retracted source), major (fixable with new analysis or substantial rewriting) or minor.
3. Reviewers quote the manuscript, never paraphrase it, and never invent a missing source, number or prior finding to make a point; "I believe there is work on X" is forbidden, the Field expert runs `scholar.py search` and cites what it finds.
4. Before the pass, run `reviews.py pull` with the paper's keywords and `classify`; show the panel the top five categories and two example sentences each, so the reviewers calibrate to the field's actual tone and priorities (ML reviewers ask for baselines and ablations; medical reviewers ask for controls and corrected p-values; education and business reviewers ask why the study matters).
5. The author-response rule from Stout (2006): when a manuscript comes back after a round of real reviews, the first check is whether every earlier comment has a point-by-point answer; unanswered comments are the most common reason for rejection on resubmission.
6. The panel's output ends with the same `RESULT:` convention as the scripts: `RESULT: FAIL` while any fatal item is open, `RESULT: PASS (n major, m minor open)` otherwise.

## 6. Limits of the evidence

- Live reviews come from three sources with their own cultures: OpenReview is ML/CS, eLife is life science, F1000Research is open-platform with many science-policy and education papers. None publishes business or education journal reviews; none has Arabic reviews.
- The classifier is a keyword tagger: a sentence that mentions a figure is tagged "figures" even when the complaint is about the statistics in it. Frequencies are indicative; the quoted examples are the evidence.
- Published studies count reasons per manuscript or per report with different coding frames, so their percentages are not comparable with each other or with the live counts; only the ranking is used above.
- OpenReview hides paper titles from guests; F1000 and eLife search loosely, and the half-the-words filter can drop relevant papers whose abstracts use synonyms. Read `paper_title` before treating a review as evidence about a specific field.
