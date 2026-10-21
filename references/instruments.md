# Instruments: validated scales instead of home-made questionnaires

Script: `scripts/instruments.py` (`find`, `pilot`, `protocol`, `selftest`). Read this before stage 4 (Methodology) of any survey study, and before answering "can I write my own items?".

```
python -X utf8 S/instruments.py find --construct "job satisfaction" --since 2000 --out instruments.md
python -X utf8 S/instruments.py pilot pilot.csv --items q1 q2 q3 q4 --reverse q3 --min 1 --max 5 >> analysis/output.txt
python -X utf8 S/instruments.py protocol --construct "job satisfaction" --scale "JSS (Spector, 1985)" --from en --to ar --out protocol.md
```

`find` costs 20 OpenAlex credits (two list searches). Every row it prints is a candidate: items, subscales, alpha, CR, languages and n are regex guesses from the abstract and must be confirmed in the full text before they reach the thesis. Nothing is a source until `scholar.py add`.

## 1. When a validated scale beats a new one

Default: use a published, validated scale. A new scale is a study in itself (item pool, expert review, EFA on one sample, CFA on a second, reliability, convergent and discriminant validity, norms). A master's thesis that writes its own 20 items and reports one alpha has measured an unknown.

| Situation | Decision |
|---|---|
| A validated scale exists for the construct (any language) | Use it. Translate and adapt with the `protocol` checklist if no version exists in the study language |
| An Arabic version exists with published psychometrics | Use that version and cite its validation paper, not only the original |
| Only a long version exists | Use the authors' own short form if one is published; never shorten it yourself without their agreement and a CFA of the short form |
| The scale measures a neighbour construct (engagement, not satisfaction) | Do not stretch it. Search again with the theory's own term (`find --construct`) |
| Truly no scale exists (two searches with synonyms return nothing) | Scale development study: say so in the title, follow DeVellis-style steps, and expect the committee to treat the instrument as the main contribution |
| Context-specific items are needed (one organisation's policies) | Keep the validated scale intact and ADD a clearly separate block of context items; analyse them separately |

What committees and reviewers ask, in this order:

1. Who developed the scale, where was it validated, and on whom (sample, country, language)? Cite the development paper and at least one independent validation.
2. What are its subscales and how many items does each have? Did you keep all of them? If not, why, and with whose permission?
3. What was the reliability in the original study and in YOUR sample (alpha or omega per subscale, from `analysis/output.txt`)?
4. Was it translated? By whom, how (forward, back, committee, pre-test), and where are the translated and back-translated versions (appendix)?
5. Did you have permission or a licence to use and translate it? Keep the email or licence PDF.
6. Was the factor structure reproduced in your data (CFA fit, or at least EFA with the expected number of factors)?
7. Any ceiling or floor effects, or items the pilot flagged (`pilot` output)?

Things that are not evidence of validity: "widely used", "adapted from several previous studies", "reviewed by three experts" alone, one alpha for a 40-item multi-dimensional scale.

## 2. Licensing table (checked 2026-10-21)

Status was read from the publisher's or author's own page on the date above. A page that could not be reached, or that did not state the terms in extractable text, is marked UNVERIFIED: open the URL yourself before you copy a single item. Terms change; re-check before data collection and keep a screenshot or PDF of the terms page.

### Needs purchase or written permission

| Scale | Holder | Terms found on the page | Source checked |
|---|---|---|---|
| MLQ (Multifactor Leadership Questionnaire, Bass & Avolio) | Mind Garden | Priced products only: manual $50, licences and reports per use; copyright 1995 Bass & Avolio; translations through the publisher | https://www.mindgarden.com/16-multifactor-leadership-questionnaire |
| MBI (Maslach Burnout Inventory, all forms) | Mind Garden | "License to Administer" purchase required; translations free of charge WITH the licence purchase; 20% student discount on data licences for unfunded theses | https://www.mindgarden.com/117-maslach-burnout-inventory-mbi and https://www.mindgarden.com/content/14-translations-and-permissions |
| STAI (State-Trait Anxiety Inventory) | Mind Garden | License to Administer $2.75 per copy (minimum 50); permission needed to make a new translation | https://www.mindgarden.com/145-state-trait-anxiety-inventory-for-adults |
| BDI-II (Beck Depression Inventory) | Pearson | Store item, Qualification Level B (professional credentials required to buy), priced per form and per report | https://www.pearsonassessments.com/store/usassessments/en/Store/Professional-Assessments/Personality-%26-Biopsychosocial/Beck-Depression-Inventory-II/p/100000159.html |
| 16PF (Fifth Edition) | Pearson Clinical (UK store page) | Store item, Qualification level B | https://www.pearsonclinical.co.uk/store/ukassessments/en/Store/Professional-Assessments/Personality-%26-Biopsychosocial/16PF-Fifth-Edition/p/P100009049.html |
| NEO-PI-3 / NEO-FFI-3 | PAR | Kits $473 to $860, Qualification Level S; uses are purchased; 50+ translations through PAR | https://www.parinc.com/products/NEO-PI-3 |
| TCM Employee Commitment Survey (Meyer & Allen) | University of Western Ontario | Academic licence FREE for one research project (register, accept terms); commercial licence $300 to $5000 CAD | http://employeecommitment.com/ |
| PSS (Perceived Stress Scale, Cohen) | Cohen / Mapi Research Trust | Free of charge, but a permission request must be filed through Mapi ePROVIDE; translations belong to their translators | https://www.cmu.edu/dietrich/psychology/stress-immunity-disease-lab/scales/ |
| MSCEIT (Mayer-Salovey-Caruso EI Test) | MHS | Sold through the MHS storefront; price and research-use terms not extractable from the page: UNVERIFIED details, treat as purchase-only | https://storefront.mhs.com/collections/msceit |
| LPI (Leadership Practices Inventory, Kouzes & Posner) | Wiley / The Leadership Challenge | A "use the LPI in your research" page exists; the permission terms were not in extractable text: UNVERIFIED, assume written permission required | https://www.leadershipchallenge.com/research/ |
| MMPI-3 | University of Minnesota Press / Pearson | Page reached, terms not extractable: UNVERIFIED; clinical instrument, qualification level applies | https://www.upress.umn.edu/test-division/mmpi-3 |
| Denison Organizational Culture Survey | Denison Consulting | Commercial consulting product; terms not extractable: UNVERIFIED | https://www.denisonconsulting.com/culture-surveys/ |
| OCI (Organizational Culture Inventory) | Human Synergistics | Product page returned 404; UNVERIFIED, commercial product | https://www.humansynergistics.com/ |
| SF-36v2 (Optum / QualityMetric version) | Optum | Not checked today (only the RAND version below was checked): UNVERIFIED, known to be licensed | (none fetched) |

### Free for academic, non-commercial use (conditions apply)

| Scale | Holder | Terms found on the page | Source checked |
|---|---|---|---|
| JSS (Job Satisfaction Survey, Spector) | Paul Spector | Free use in return for sharing results, citing, and printing the copyright notice (copyright 1994 Spector); translations listed on the site | https://paulspector.com/assessments/pauls-no-cost-assessments/job-satisfaction-survey-jss/ |
| MSQ (Minnesota Satisfaction Questionnaire, long and short) | Vocational Psychology Research, U of Minnesota | CC BY-NC 4.0; free for research or clinical use without written consent, attribution required; no commercial use | https://vpr.psych.umn.edu/msq-minnesota-satisfaction-questionnaire |
| PHQ-9, GAD-7 (and all PHQ screeners) | Pfizer (phqscreeners) | "No permission is required to reproduce, translate, display or distribute them" | https://www.phqscreeners.com/select-screener |
| DASS-21 / DASS-42 | UNSW (Lovibond) | Public domain, downloadable; manual sold for a nominal $55 | https://www2.psy.unsw.edu.au/dass/ |
| IPIP scales (Big Five and 200+ others) | IPIP (Goldberg) | Public domain: copy, edit, translate, use for any purpose without permission or fee | https://ipip.ori.org/ |
| SWLS and other Diener scales | Ed Diener | Copyrighted but free for non-commercial research with credit; no individual permission answered | https://eddiener.com/scales/7 |
| SF-36 (RAND 36-Item Health Survey 1.0) | RAND | Public use, no charge or permission for non-commercial use; translation permitted without permission | https://www.rand.org/health-care/surveys_tools/mos/36-item-short-form.html |
| VSM 2013 (Hofstede Values Survey Module) | Hofstede | Free download for research purposes, many translations | https://geerthofstede.com/research-and-vsm/vsm-2013/ |
| WHOQOL-BREF / WHOQOL-100 | WHO | Distributed by WHO; the page warns that linked translations are not WHO's; the user agreement terms were not in extractable text: UNVERIFIED (WHO normally asks for a signed user agreement) | https://www.who.int/tools/whoqol |
| UWES (Utrecht Work Engagement Scale, Schaufeli) | Schaufeli | Author site returned HTTP 503 on the check date: UNVERIFIED today (the test manual states free use for non-commercial scientific research; confirm on the site); development paper DOI 10.1023/A:1015630930326 verified | https://www.wilmarschaufeli.nl/tests/ |
| JDS (Job Diagnostic Survey, Hackman & Oldham) | Items printed in the 1975 article (APA journal) | No licensing page exists; the article copyright belongs to the publisher: UNVERIFIED, cite the article (DOI 10.1037/h0076546 verified) and ask the journal if you reprint the full instrument | https://doi.org/10.1037/h0076546 |
| TAM items (perceived usefulness / ease of use, Davis 1989) | Items printed in the MIS Quarterly article | No licensing page; reused freely in thousands of studies but the article is copyrighted: UNVERIFIED, cite the article (DOI 10.2307/249008 verified) | https://doi.org/10.2307/249008 |
| PANAS (Watson, Clark & Tellegen 1988) | Items printed in the JPSP article (APA) | Licensing page not checked: UNVERIFIED; DOI 10.1037/0022-3514.54.6.1063 verified | https://doi.org/10.1037/0022-3514.54.6.1063 |
| BFI-2 (Soto & John) | Colby College personality lab | Page is script-rendered, terms not extractable: UNVERIFIED (authors state free research use on the page when opened in a browser) | https://www.colby.edu/academics/departments-and-programs/psychology/research-opportunities/personality-lab/the-bfi-2/ |
| Rosenberg Self-Esteem Scale | University of Maryland (Rosenberg estate) | Site unreachable on the check date: UNVERIFIED | https://socy.umd.edu/about-us/using-rosenberg-self-esteem-scale |
| GSE (General Self-Efficacy, Schwarzer & Jerusalem) | Schwarzer | Site unreachable (connection timeout): UNVERIFIED | https://userpage.fu-berlin.de/~health/engscal.htm |
| WHO-5 Well-Being Index | Region Hovedstaden (Psychiatric Research Unit) | Page script-rendered, terms not extractable: UNVERIFIED | https://www.psykiatri-regionh.dk/who-5/Pages/default.aspx |
| CBI (Copenhagen Burnout Inventory) | NFA Denmark | Page returned 404: UNVERIFIED; development paper DOI 10.1080/02678370500297720 (seen in OpenAlex, verify before citing) | https://nfa.dk/ |
| OLBI (Oldenburg Burnout Inventory, Demerouti) | Demerouti | Author pages unreachable: UNVERIFIED | (none reached) |
| SUS (System Usability Scale, Brooke) | Brooke / public | usability.gov page reached, no licence sentence: UNVERIFIED (commonly reported as free with attribution) | https://www.usability.gov/how-to-and-tools/methods/system-usability-scale.html |

Rules of thumb:

- "Free" never means "free to modify or shorten": the holder's page states the conditions (attribution, copyright notice, sharing results, no commercial use).
- A translation is a derivative work. Mind Garden and PAR sell or control translations; free scales usually allow translation but want to be told and credited.
- Journal copyright covers the article, not necessarily the items; when the only source is the article, cite it, reproduce the items in an appendix only with the journal's reprint permission, and say so.
- Keep the permission email or licence PDF: committees ask for it, and journals increasingly require a statement.

## 3. Reporting scale adaptation in Methods

The `protocol` command prints the full checklist with verified sources (Brislin 1970, DOI 10.1177/135910457000100301; Beaton et al. 2000, DOI 10.1097/00007632-200012150-00014; Sousa & Rojjanasrirat 2011, DOI 10.1111/j.1365-2753.2010.01434.x; Guillemin et al. 1993, DOI 10.1016/0895-4356(93)90142-N; all resolved through Crossref on 2026-10-21). Add them to the ledger with `scholar.py add` before citing; the command re-verifies them on every run and refuses to print an unverified one.

Minimum content of the instrument paragraph (every bracket is filled from the ledger, the licence, or `analysis/output.txt`):

1. Name, authors, year, DOI of the development paper and of the version used (short form, language).
2. Structure: number of items, subscales, response format and anchors, scoring direction, reverse-coded items.
3. Original psychometrics (from the development or validation paper, with the source named).
4. Adaptation steps, who did them (qualifications), and the sizes of the pre-test and pilot.
5. Reliability and validity in the present sample (alpha / omega per subscale, CFA fit if run), as evidence lines.
6. Permission or licence, with date.

### English template

> Job satisfaction was measured with the [Job Satisfaction Survey; Spector, 1985], a [36]-item scale with [nine] subscales ([pay, promotion, ...]) answered on a [6]-point agreement scale (1 = disagree very much, 6 = agree very much); [19] items are reverse-scored. In the development sample the subscale alphas ranged from [.60] to [.82] and the total-scale alpha was [.91] ([Spector, 1985]). The [Arabic] version was produced for this study following the back-translation procedure of Brislin (1970) and the cross-cultural adaptation guidelines of Beaton et al. (2000): two independent forward translations, reconciliation, blind back-translation, an expert committee of [k] members, cognitive interviews with [n] [population], and a pilot with [n] [population] (alpha = [ ]). [n] items were reworded after the pre-test; no item was removed. In the main sample, Cronbach's alpha was [ ] for the total scale and ranged from [ ] to [ ] across subscales; a confirmatory factor analysis supported the original structure (CFI = [ ], TLI = [ ], RMSEA = [ ], SRMR = [ ]). Permission to use and translate the instrument was obtained from [holder] on [date] [or: the scale is free for non-commercial research under the conditions stated by the author, which were met].

### قالب عربي

> قيس الرضا الوظيفي بمقياس [الرضا الوظيفي؛ Spector, 1985] المكون من [36] فقرة موزعة على [تسعة] أبعاد ([الأجر، الترقية، ...]) يُجاب عنها على تدريج من [6] درجات (1 = لا أوافق بشدة، 6 = أوافق بشدة)، ومنها [19] فقرة عكسية التصحيح. بلغت معاملات ألفا للأبعاد في عينة التطوير بين [0.60] و[0.82] وللمقياس الكلي [0.91] ([Spector, 1985]). أُعدت النسخة [العربية] لهذه الدراسة وفق إجراء الترجمة العكسية (Brislin, 1970) وإرشادات التكييف عبر الثقافات (Beaton et al., 2000): ترجمتان أماميتان مستقلتان، ثم توفيق بينهما، ثم ترجمة عكسية من مترجم لا يعرف الأصل، ثم لجنة خبراء من [ك] أعضاء، ثم مقابلات معرفية مع [ن] من [المجتمع المستهدف]، ثم تطبيق تجريبي على [ن] من [المجتمع المستهدف] (ألفا = [ ]). عُدلت صياغة [ن] فقرات بعد الاختبار الأولي ولم تُحذف أي فقرة. وفي العينة الأساسية بلغ معامل ألفا كرونباخ [ ] للمقياس الكلي وتراوح بين [ ] و[ ] للأبعاد، وأيد التحليل العاملي التوكيدي البنية الأصلية (CFI = [ ]، TLI = [ ]، RMSEA = [ ]، SRMR = [ ]). وحُصل على إذن استخدام المقياس وترجمته من [مالك الحقوق] بتاريخ [التاريخ] [أو: المقياس متاح مجانا للبحث غير التجاري وفق شروط مؤلفه، وقد استوفيت].

Keep the English names of the scale and the statistics (CFI, RMSEA, alpha) inside the Arabic text; Arab universities expect them untransliterated. Wrap Arabic paragraphs in `dir="rtl"` when the manuscript is HTML; `build_docx.py` handles Word.

### Pilot paragraph (from `pilot` output)

> A pilot with [n] [population] showed corrected item-total correlations between [ ] and [ ] and a Cronbach's alpha of [ ]; item [q3] correlated negatively with the rest of the scale ([r = ]) and its wording was corrected before the main study [or: was confirmed to be reverse-scored]. No item showed floor or ceiling effects above 15%.

Every number in these paragraphs must exist as an evidence line (`pilot.alpha = ...`, `pilot.q3.item_total.r = ...`, `pilot.q3.floor.pct = ...`) and pass `scholar.py numbers`; write the prose with labels (`r = .68`, `alpha = .87`) so the match is strict, not weak.
