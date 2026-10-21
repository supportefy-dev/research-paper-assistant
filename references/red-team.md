# Red team: kill the design before the data exists (الفريق الأحمر: اقتل التصميم قبل جمع البيانات)

A design that dies here costs a week. The same design dying in a reviewer's hands costs a year and a dataset. This document is the attack protocol: the agent writes `design.md` with the author, then attacks it from every angle a hostile reviewer would, then both pick fixes from the decision table and rewrite `design.md`. Run it at stage 4 (Methodology), before the instrument goes out. Written in English with Arabic headings so an Arab-university supervisor can follow the structure.

## 1. الملف الذي يُهاجَم: design.md template

The attack reads one file. Fill every row; an empty row is itself a finding. Keep it in the project folder; the review panel's methods and theory reviewers read it later to catch silent deviations.

```markdown
# design.md  (date, version)

## 1. السؤال والفرضيات  Question and hypotheses
RQ: <one sentence: population, variables, setting>
H1: <A is positively associated with B among ...>   (direction stated)
H2: <M mediates A -> B>  /  H3: <W moderates A -> B>
Theory: <name + ledger key>; mechanism for each H in one sentence

## 2. نوع التصميم  Design type
<cross-sectional survey | experiment / quasi-experiment | qualitative | mixed | secondary data>
Unit of analysis: <individual | team | organisation | document>
Time structure: <single wave | two waves, lag of N weeks | longitudinal | pre/post>

## 3. المتغيرات والقياس  Variables and measurement
| Variable | Role (IV/DV/M/W/control) | Instrument + ledger key | Items | Scale | Source of data (self-report / other-report / archival / objective) | Language (AR/EN/both) | Prior alpha |

## 4. المجتمع والعينة  Population and sample
Population: <who, where, how many exist>
Sampling: <probability / stratified / convenience / snowball>, frame: <list used>
Access: <through whom; permission letters needed>
Expected response rate and basis: <...>
Target N: <number>; justification: <a priori power: test, effect size + its source, alpha, power> or <information power / saturation argument>

## 5. الإجراءات  Procedure
Mode: <online form / paper / interview / lab>
Timeline: <dates per wave>
Order of sections in the instrument: <...>
Anonymity / confidentiality mechanism: <...>
Attention checks / careless-response screening: <yes: how | no>

## 6. الترجمة والتكييف  Translation and adaptation (if any AR instrument)
Forward translators: <n, profile>; back translators: <n, blind>; committee: <yes/no>; pilot: <n, with whom>; invariance plan: <groups compared, test planned>

## 7. خطة التحليل  Analysis plan
Per hypothesis: test, software, assumptions to check, effect size + CI to report
Common method bias plan: <procedural remedies> + <statistical test: marker variable / CFA marker / full-collinearity VIF>
Missing data: <method>; multiple testing: <how many tests, correction or justification>
Pre-registration: <OSF / AsPredicted / none, with reason>

## 8. الأخلاقيات  Ethics
Approval body: <name>, status: <submitted / approved no. [ ] >, consent form: <yes/no>, data storage: <where, how long>, vulnerable groups: <none / which>

## 9. الجدوى  Feasibility
Budget: <...>; time to collect: <weeks>; tools licensed: <SPSS / AMOS / R / SmartPLS>; risks: <access denied, low response, seasonal>

## 10. الحدود المعروفة  Known limits the author already accepts
- ...
```

## 2. محاور الهجوم  Attack dimensions

The agent writes one paragraph per dimension: the strongest honest attack, graded `fatal` (the study cannot answer its question), `serious` (a reviewer will demand a fix), or `note` (state it in limitations). Each attack quotes the `design.md` row it targets. Then it proposes fixes from section 4. Sources are given so the author can read the argument before accepting the fix.

| # | المحور | Dimension | The attack asks | Grounding |
|---|---|---|---|---|
| 1 | المتغيرات المربكة | Confounds | Which third variable could produce the A-B association by itself? Is it measured? Is any "control" actually a mediator or a collider (controlling for it introduces bias rather than removing it)? | Rohrer (2018); Elwert and Winship (2014) |
| 2 | السببية العكسية | Reverse causality | Could B cause A just as plausibly? A single-wave survey cannot tell; the hypothesis wording must not claim it | Antonakis et al. (2010); Rindfleisch et al. (2008) |
| 3 | تحيز الاختيار | Selection | Who enters the sample and who refuses or drops out, and does that depend on A or B? Convenience samples from one institution, snowball chains, and self-selected online respondents all carry it | Heckman (1979); Elwert and Winship (2014) |
| 4 | تحيز الطريقة المشتركة | Common-method bias | Same respondent, same questionnaire, same moment for both A and B? Then part of the correlation is the method. Which procedural and statistical remedies are planned? Harman's one-factor test alone proves nothing | Podsakoff et al. (2003, 2012); Spector (2006); Lindell and Whitney (2001); Williams et al. (2010); Kock (2015); Siemsen et al. (2010); Fuller et al. (2016) |
| 5 | صدق البناء | Construct validity | Does the instrument measure the construct the theory defines, in this population? Was it built for another sector or culture? Are two constructs operationally the same items with different names (discriminant validity)? | Fornell and Larcker (1981); Henseler et al. (2015); Bagozzi and Yi (1988) |
| 6 | تكافؤ القياس (الترجمة العربية) | Measurement invariance (AR translation) | A translated scale may measure something slightly different, or the items may work differently for AR and EN respondents, men and women, two countries. Was the adaptation procedure full (forward, back, committee, pilot)? Is invariance testable with the planned N per group? | Beaton et al. (2000); Brislin (1970); Sousa and Rojjanasrirat (2011); Vandenberg and Lance (2000); Cheung and Rensvold (2002); Chen (2007); Putnick and Bornstein (2016) |
| 7 | القوة الإحصائية | Power | Is N justified against a named effect size with its source, or a rule of thumb? Small samples miss real effects and inflate the ones they find. Moderation and invariance tests need far more than main effects | Cohen (1992); Faul et al. (2007); Button et al. (2013); Lakens (2022) |
| 8 | المرونة التحليلية | Analytic flexibility | How many tests, DVs, item deletions and subgroup splits could be run? Which ones are committed to before the data? | Simmons et al. (2011); Nosek et al. (2018) |
| 9 | جودة الاستجابات | Response quality | Sensitive items (income, religiosity, misconduct) invite social desirability; long online forms invite careless responding. What screening is planned? | Tourangeau and Yan (2007); Krosnick (1999); Meade and Craig (2012) |
| 10 | الأخلاقيات | Ethics | Approval before collection; consent that a participant can actually withhold (students graded by the researcher cannot); anonymity vs the need to link waves; data on minors or employees; storage | reporting guideline for the design (STROBE, CONSORT, COREQ) |
| 11 | الجدوى | Feasibility | Can this N be reached, through this gate, in this time, at this budget, with these tools? What is the plan if the response rate is half the expectation? | design.md row 9 |
| 12 | قابلية التفسير | Interpretability | If H1 is rejected, what does the author conclude: no effect, bad measure, wrong sample? If the design cannot tell these apart, a null result is uninformative | Wasserstein and Lazar (2016); Cumming (2014) |

## 3. قوائم الفحص حسب نوع التصميم  Checklists per design type

Run the general dimensions first, then the list for the design type. Each unchecked box is an attack.

### أ. المسح المقطعي  Cross-sectional survey

- [ ] Hypotheses use association or prediction verbs, not effect or impact verbs (AR: يرتبط، يتنبأ، not يؤدي إلى، يؤثر)
- [ ] IV and DV come from different sources, or different times, or at least different sections with a procedural separation; the CMB statistical test is named (marker variable chosen before collection, or CFA marker, or full-collinearity VIF)
- [ ] At least one plausible confound measured and justified; no mediator or collider in the control list
- [ ] Sampling frame named; expected response rate with basis; non-response plan (compare early vs late respondents, or respondents vs frame on known variables)
- [ ] N from a priori power for the smallest test in the plan (interaction or invariance, not the main correlation)
- [ ] Instrument sources in the ledger; AR adaptation documented (forward, back, committee, pilot n)
- [ ] Attention check items placed; careless-response rule written before collection
- [ ] Reporting checklist: STROBE cross-sectional items (von Elm et al., 2008)
- [ ] Analysis plan per hypothesis with effect size and CI; number of tests stated

### ب. التجربة وشبه التجربة  Experiment and quasi-experiment

- [ ] Random assignment (or the quasi design named: non-equivalent groups, interrupted time series) and the allocation mechanism described
- [ ] Manipulation check planned; the treatment is the only systematic difference between arms
- [ ] Pre-test measures for the DV and known confounds (quasi designs need them)
- [ ] Blinding where possible (participants, raters); demand characteristics considered
- [ ] Attrition tracked per arm; intention-to-treat or per-protocol stated
- [ ] N per arm from a priori power on the expected difference with its source
- [ ] Fidelity of delivery: who delivers the treatment, trained how, checked how
- [ ] Ethics: control group receives the standard condition or the treatment later
- [ ] Reporting checklist: CONSORT 2010 (Schulz et al., 2010), or its extension for non-randomised designs
- [ ] Pre-registration of the primary outcome and the analysis

### ج. البحث النوعي  Qualitative

- [ ] The question is one a qualitative design answers (how, why, meaning), not a prevalence or effect question
- [ ] Approach named and sourced (thematic analysis per Braun and Clarke, 2006; phenomenology; grounded theory) and the analysis steps match that approach
- [ ] Sampling rationale: purposive criteria written; sample size by saturation (Guest et al., 2006) or information power (Malterud et al., 2016), with the argument, not a number from habit
- [ ] Interview guide piloted; language of interviews and of transcription stated; translation of quotes planned (who, when, back-check)
- [ ] Researcher position and reflexivity stated (relationship to participants, prior assumptions)
- [ ] Trustworthiness steps planned: audit trail, peer debriefing, member checking, thick description (Nowell et al., 2017)
- [ ] Coding reliability approach stated (second coder, consensus) if the tradition uses one
- [ ] Ethics: consent for recording, anonymisation of quotes, withdrawal
- [ ] Reporting checklist: COREQ (Tong et al., 2007) for interviews and focus groups; SRQR (O'Brien et al., 2014) otherwise

### د. المنهج المختلط  Mixed methods

- [ ] The design is named (convergent, explanatory sequential, exploratory sequential) with the reason for mixing (Schoonenboom and Johnson, 2017)
- [ ] The point of integration is written: where and how the two strands meet (connecting, building, merging, embedding) and how results will be joined (joint display) (Fetters et al., 2013)
- [ ] Each strand passes its own checklist above
- [ ] Priority and timing stated; sample relationship stated (same participants, subset, different)
- [ ] A plan for divergent findings (what if the interviews contradict the survey)

### هـ. البيانات الثانوية  Secondary data

- [ ] Source named, access terms stated, version and extraction date recorded
- [ ] The variables available measure the constructs the theory needs (not proxies renamed to fit)
- [ ] Known limitations of the dataset documented by its owner are quoted
- [ ] Missingness pattern examined before the analysis plan is fixed
- [ ] Selection into the dataset considered (who gets recorded)
- [ ] Multiple comparisons: the number of models the data could support is large; the committed ones are listed
- [ ] Ethics: de-identification confirmed, data use agreement in the project folder
- [ ] Reporting: STROBE where the data are observational

## 4. جدول القرار: الإصلاحات  Decision table of fixes

Pick the fix that removes the attack at the lowest cost that the author can afford. The last column says what is given up.

| Attack | Fix | Cost | What it buys | What it does not | Source |
|---|---|---|---|---|---|
| Confound unmeasured | Add it as a measured control variable, justified by theory | 2 to 5 items | Removes that confound | Not the ones you did not think of | Rohrer (2018) |
| Control is a mediator or collider | Remove it from the control set; model it as a mediator if the theory says so | none | Avoids bias you were about to introduce | | Rohrer (2018); Elwert and Winship (2014) |
| Reverse causality | Time-lag the measures: IV at wave 1, DV at wave 2 (weeks apart), linked by a code | second wave, attrition | Rules out simultaneity; weakens CMB too | Still not a causal design | Rindfleisch et al. (2008); Podsakoff et al. (2012) |
| Reverse causality (strong) | Experiment or quasi-experiment on the IV | redesign | Causal inference | Feasibility, ethics | Antonakis et al. (2010) |
| Causal wording in a correlational design | Rewrite RQ, hypotheses and title with association / prediction verbs | none | Matches the design; the most common reviewer objection removed | | writing-style.md |
| CMB: same source | Different sources for IV and DV (supervisor rates performance; archival DV) | access | Strongest CMB remedy | Rater bias of its own | Podsakoff et al. (2003) |
| CMB: same moment | Temporal separation (two sessions) or psychological separation (cover story, separated sections) | design time | Reduces consistency motif | Partial | Podsakoff et al. (2003, 2012) |
| CMB: no test planned | Add a marker variable: a short scale theoretically unrelated to the model, chosen before collection; test with the partial-correlation or CFA marker technique | 3 to 4 items | A defensible statistical check | Does not fix a design that is all one source | Lindell and Whitney (2001); Williams et al. (2010) |
| CMB in PLS-SEM | Full-collinearity VIF test (all VIFs below 3.3) | none | A test for variance-based models | | Kock (2015) |
| CMB in regression with interactions | Note that interaction effects are deflated, not inflated, by CMB; a found interaction is robust to it | none | Argument for the limitations section | | Siemsen et al. (2010) |
| Construct validity weak | Replace the instrument with the construct's validated one from the ledger; run CFA with AVE and discriminant validity (Fornell-Larcker, HTMT) | items, N | Measurement model that reviewers accept | | Fornell and Larcker (1981); Henseler et al. (2015) |
| AR translation undocumented | Full adaptation: two forward translators, two blind back translators, expert committee, pilot of 30 to 40 with cognitive interviews | 3 to 6 weeks | Defensible Arabic instrument | | Beaton et al. (2000); Brislin (1970); Sousa and Rojjanasrirat (2011) |
| Groups compared on a latent construct | Plan configural, metric, scalar invariance tests with change in CFI <= .01; size N per group for it | N | Legitimate group comparison | | Vandenberg and Lance (2000); Cheung and Rensvold (2002); Chen (2007); Putnick and Bornstein (2016) |
| N by rule of thumb | A priori power in G*Power for the smallest planned effect, with the effect size from a cited prior study or a smallest effect of interest | none | Defensible N; often shows the moderation test needs 3x the sample | Larger N to collect | Faul et al. (2007); Cohen (1992); Lakens (2022) |
| Power unreachable | Drop the under-powered test (usually the moderation) or make it exploratory, stated as such | scope | Honest design | A thinner contribution | Button et al. (2013) |
| Selection: one institution, convenience | Stratify across institutions or units; record the frame; compare respondents with the frame on known variables; model non-response | access | Bounded generalisation | | Heckman (1979) |
| Selection: online self-selection | Invitation through a frame (lists) not open links; record source of each response; report response rate | admin | Known denominator | | Krosnick (1999) |
| Analytic flexibility | Pre-register hypotheses, measures, exclusions and the primary analysis (OSF or AsPredicted) | an hour | Credibility; protection against the "you fished" objection | | Nosek et al. (2018); Simmons et al. (2011) |
| Sensitive items | Anonymity assured and visible; indirect wording; sensitive items late in the form; a social desirability short scale as a control if needed | items | Less misreporting | | Tourangeau and Yan (2007) |
| Careless responding | Two attention-check items, a response-time floor, a written exclusion rule | items | Cleaner data, reported exclusions | | Meade and Craig (2012) |
| Interpretation of nulls | Add effect sizes with CIs and a smallest effect of interest so a null can be read as "smaller than X" | none | Informative nulls | | Lakens (2022); Cumming (2014); Wasserstein and Lazar (2016) |
| Ethics gap | Submit to the committee now; add consent text; separate the researcher from any grading or supervisory power over participants; use a third party to administer | time | Collection can legally start | | the design's reporting guideline |
| Feasibility gap | Halve the instrument length, pay for access, or change the population to one the author can reach, and re-run the power step | scope | A study that finishes | | design.md row 9 |

## 5. بروتوكول التشغيل  Running the attack

1. The author (or the agent with the author) fills `design.md`. Empty rows stay empty; they are findings.
2. The agent attacks: one paragraph per dimension in section 2, graded fatal / serious / note, each quoting the `design.md` row it targets (`row 3, Variable 'burnout': self-report, same form as DV`). Then the checklist for the design type with every unchecked box listed.
3. For every fatal and serious attack the agent proposes one or two fixes from section 4 with their cost. The author chooses.
4. Rewrite `design.md` (new version number) with the chosen fixes; the `Known limits` row holds every attack graded `note` and every fix declined, each in one sentence that can later be pasted into the limitations section.
5. Re-attack once. A design with a fatal attack still open after the second pass goes back to stage 1 (the question) or stage 4 (a different design), not to data collection.
6. Output file: `design-redteam.md` next to `design.md`, in the format below. The review panel reads `design.md` later and flags any silent deviation from it.

```
# Red team, pass <1|2>, design.md v<version>, <date>
Design type: <...>   Unit: <...>   Waves: <...>

| # | Dimension | Grade | Attack (quotes the design.md row) | Fix chosen (section 4 row) | Cost |
|---|---|---|---|---|---|
| 1 | Confounds | serious | row 3: no control for ...; "..." | add control: ... | 3 items |
| 2 | Reverse causality | fatal | row 2: single wave; H2 says "leads to" | time-lag, 4 weeks; rewrite H2 | second wave |
...

Checklist (<design type>): <n> of <m> boxes checked; unchecked: <list>
Open fatal attacks after this pass: <n>  -> <proceed to collection | back to stage 1/4>
Limits accepted (for the limitations section): <list>
```

## 6. ما لا يفعله هذا البروتوكول  What this protocol cannot do

- It does not know the field's specific confounds; it asks for them. The author and the field-expert reviewer supply them.
- A fix from the table is a known remedy, not a guarantee that a given reviewer accepts it; the source column lets the author read the argument and decide.
- It cannot run power calculations: the author runs G*Power (free) and pastes the output into `design.md` row 4; the agent checks that the effect size has a cited origin.
- It cannot approve ethics or confirm access; it only refuses to call a design ready without them.

## Verified sources (DOIs resolved with `python -X utf8 scholar.py verify <doi>`)

| Source | DOI |
|---|---|
| Antonakis, Bendahan, Jacquart and Lalive (2010), On making causal claims | 10.1016/j.leaqua.2010.10.010 |
| Bagozzi and Yi (1988), evaluating structural equation models | 10.1007/BF02723327 |
| Beaton, Bombardier, Guillemin and Ferraz (2000), cross-cultural adaptation | 10.1097/00007632-200012150-00014 |
| Braun and Clarke (2006), thematic analysis | 10.1191/1478088706qp063oa |
| Brislin (1970), back-translation | 10.1177/135910457000100301 |
| Button et al. (2013), power failure (erratum exists; paper stands) | 10.1038/nrn3475 |
| Chen (2007), fit indexes and invariance | 10.1080/10705510701301834 |
| Cheung and Rensvold (2002), fit indexes for invariance | 10.1207/S15328007SEM0902_5 |
| Cohen (1992), A power primer | 10.1037/0033-2909.112.1.155 |
| Cumming (2014), The new statistics | 10.1177/0956797613504966 |
| Elwert and Winship (2014), endogenous selection bias | 10.1146/annurev-soc-071913-043455 |
| Faul, Erdfelder, Lang and Buchner (2007), G*Power 3 | 10.3758/BF03193146 |
| Fetters, Curry and Creswell (2013), integration in mixed methods | 10.1111/1475-6773.12117 |
| Fornell and Larcker (1981), SEM with unobservable variables | 10.2307/3151312 |
| Fuller et al. (2016), CMV detection | 10.1016/j.jbusres.2015.12.008 |
| Guest, Bunce and Johnson (2006), how many interviews | 10.1177/1525822X05279903 |
| Heckman (1979), sample selection bias | 10.2307/1912352 |
| Henseler, Ringle and Sarstedt (2015), HTMT | 10.1007/s11747-014-0403-8 |
| Kock (2015), full collinearity CMB test | 10.4018/ijec.2015100101 |
| Krosnick (1999), survey research | 10.1146/annurev.psych.50.1.537 |
| Lakens (2022), sample size justification | 10.1525/collabra.33267 |
| Lindell and Whitney (2001), marker variable | 10.1037/0021-9010.86.1.114 |
| Malterud, Siersma and Guassora (2016), information power | 10.1177/1049732315617444 |
| Meade and Craig (2012), careless responding | 10.1037/a0028085 |
| Nosek, Ebersole, DeHaven and Mellor (2018), preregistration | 10.1073/pnas.1708274114 |
| Nowell et al. (2017), trustworthiness in thematic analysis | 10.1177/1609406917733847 |
| O'Brien et al. (2014), SRQR | 10.1097/ACM.0000000000000388 |
| Podsakoff, MacKenzie, Lee and Podsakoff (2003), common method biases | 10.1037/0021-9010.88.5.879 |
| Podsakoff, MacKenzie and Podsakoff (2012), sources of method bias | 10.1146/annurev-psych-120710-100452 |
| Putnick and Bornstein (2016), invariance conventions | 10.1016/j.dr.2016.06.004 |
| Rindfleisch, Malter, Ganesan and Moorman (2008), cross-sectional vs longitudinal | 10.1509/jmkr.45.3.261 |
| Rohrer (2018), graphical causal models | 10.1177/2515245917745629 |
| Schoonenboom and Johnson (2017), mixed methods design | 10.1007/s11577-017-0454-1 |
| Schulz, Altman and Moher (2010), CONSORT 2010 | 10.1136/bmj.c332 |
| Siemsen, Roth and Oliveira (2010), CMB in regression with interactions | 10.1177/1094428109351241 |
| Simmons, Nelson and Simonsohn (2011), false-positive psychology | 10.1177/0956797611417632 |
| Sousa and Rojjanasrirat (2011), translation and validation of instruments | 10.1111/j.1365-2753.2010.01434.x |
| Spector (2006), method variance: truth or urban legend | 10.1177/1094428105284955 |
| Tong, Sainsbury and Craig (2007), COREQ | 10.1093/intqhc/mzm042 |
| Tourangeau and Yan (2007), sensitive questions in surveys | 10.1037/0033-2909.133.5.859 |
| Vandenberg and Lance (2000), measurement invariance review | 10.1177/109442810031002 |
| von Elm et al. (2008), STROBE | 10.1016/j.jclinepi.2007.11.008 |
| Wasserstein and Lazar (2016), ASA statement on p values | 10.1080/00031305.2016.1154108 |
| Williams, Hartman and Cavazotte (2010), CFA marker technique | 10.1177/1094428110366036 |
