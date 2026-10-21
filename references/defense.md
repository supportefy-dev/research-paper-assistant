# Defense preparation (التحضير للمناقشة)

The viva (المناقشة) is won before the room: the candidate who has already answered the committee's questions, with the page of the thesis that proves each answer, is calm. This document gives the agent five committee personas, each generating ten questions **from the thesis text with page references**, the answer format the candidate rehearses, a 20-slide deck outline, a mock-defense protocol, and the question stems in Arabic and English. Mode C (coaching) applies: the thesis is the candidate's; the agent prepares, it does not answer for them in the room.

## 1. التحضير  Inputs

1. The thesis as text with page markers: `fulltext/thesis.txt` with `[[page N]]` lines (the skill's full-text format). From a PDF:
   ```bash
   python -X utf8 -c "import fitz,sys; d=fitz.open(sys.argv[1]); print(''.join(f'[[page {i+1}]]\n'+p.get_text() for i,p in enumerate(d)))" thesis.pdf > fulltext/thesis.txt
   ```
   From the project's own `paper.md`, use line numbers instead of pages and say so on every question.
2. `sources.jsonl`, `analysis/output.txt`, `design.md` and `design-redteam.md` (the accepted limits are the committee's favourite questions), `review/round-*/merged.md` (every must-fix the panel found is a question the committee may still ask).
3. The university's viva rules if the user has them (duration of the presentation, committee size, who speaks first, whether the public attends). Never assume them; mark anything not given as "confirm with the department".

## 2. شخصيات اللجنة  Committee personas

Each persona is one Agent call (or one Workflow step), run in parallel. Prompt = the persona block below + the inputs block + the output format in section 3. The persona reads the thesis text and writes exactly ten questions, each anchored to a page (or line) and a quoted phrase. A question without a page anchor is dropped. The questions are sorted from the one most likely to be asked to the least.

### أ. صقر المنهجية  The methods hawk

Role: a methodologist who reads Chapter 3 first and believes every thesis overclaims. Hunts: design-question mismatch, causal wording in correlational work, sample justification, instrument adaptation and invariance, common-method bias, selection, ethics, deviations from `design.md`. Reads the limitations section to see what the candidate already admits, then asks about what is missing from it.

### ب. حارس النظرية  The theory purist

Role: reads Chapter 2 and the hypotheses; wants the mechanism. Hunts: a theory named but not used, constructs defined twice, hypotheses justified by prior findings only, Western theory applied to an Arab sample without an argument, a discussion that never returns to the theory, "fills a gap" offered as a contribution.

### ج. الممارس  The practitioner

Role: a senior person from the sector studied (a hospital director, a bank executive, a ministry official, a school principal). Hunts: whether the recommendations follow from the results, whether they are addressed to someone who can act, what it would cost, what the sector already does, whether the sample resembles the real population, and what the candidate would tell the minister in one minute.

### د. ممتحن الإحصاء  The statistics examiner

Role: opens Chapter 4 at the tables. Hunts: numbers that do not match across text, tables and `analysis/output.txt`; assumptions never checked; effect sizes and CIs absent; p values read as importance; mediation by Baron and Kenny steps; reliability only from another sample; a non-significant result called "no effect"; what the candidate would do with the same data and one more week.

### هـ. رئيس اللجنة  The chair

Role: the supervisor's peer who runs the session and reads the whole thesis for coherence. Hunts: the abstract's promise vs the conclusion's delivery, the one-sentence contribution, the title's fit, the clarity of the research questions, originality, the AI-use disclosure and integrity, publication potential, and the questions that close a viva ("what would you do differently", "what is the next study").

## 3. صيغة السؤال والإجابة  Question and answer format

The agent writes the question and a **model answer skeleton** in three parts that the candidate fills and rehearses. It never writes the final spoken answer: the candidate must own the words.

```
Q<persona-letter><n> | p. <page> | "<quoted phrase from the thesis>" | <the question, one or two sentences, in the thesis language>
Likely follow-up: <one sentence>
Answer skeleton:
  Claim:    <the one-sentence position the candidate holds>
  Evidence: <where in the thesis it is shown: chapter, section, page, table or figure number; and the analysis/output.txt line if a number is involved>
  Limit:    <what the candidate concedes, in one sentence, and why the thesis still stands>
```

Rules for the skeleton:

| Part | Must | Must not |
|---|---|---|
| Claim | Be answerable in 20 seconds; take a position | Open with a defence of the whole thesis |
| Evidence | Point to a page, table or figure the candidate can open in the room | Cite anything not in the thesis or the ledger |
| Limit | Concede the real limit and bound it ("this limits generalisation to public universities, not the association itself") | Concede the question ("yes, the design is weak") or deny an obvious limit |

Ten questions per persona, fifty in total, saved as `defense/questions.md`. The candidate marks each as `ready / shaky / unknown` after a first pass; the mock defense (section 5) uses the shaky and unknown ones first.

## 4. عرض المناقشة: 20 شريحة  The 20-slide defense deck

Presentation length is set by the university (often 15 to 25 minutes for a master's, up to 40 for a doctorate: confirm). One slide per minute is the ceiling. Every number on a slide comes from `analysis/output.txt`; every citation is a ledger key. Arabic deck: RTL layout, English terms kept in parentheses as in the thesis.

| # | Slide | Shows | Not |
|---|---|---|---|
| 1 | Title | Thesis title, candidate, supervisor, university, date, degree | Logos crowding the title |
| 2 | The problem in one picture | One figure or one number from the literature that makes the problem visible, with its ledger source | A wall of text |
| 3 | What is known | Three to four bullets: the established findings, each with a citation | A list of every study read |
| 4 | The gap | The empty cell: population x variable x method; one sentence, "no study has... (search: N results, date)" | A gap asserted without the search |
| 5 | Research questions and hypotheses | RQs numbered; hypotheses with direction; the conceptual model figure with H labels | Hypotheses rephrased differently from the thesis |
| 6 | Theory and mechanism | The theory in one sentence; the mechanism per path in a few words on the model figure | A biography of the theorist |
| 7 | Design | Design type, unit of analysis, time structure, why this design answers these RQs | Apologies |
| 8 | Population and sample | Population size, sampling method, frame, N, response rate, a priori power line (test, effect size + source, alpha, power, required N) | "A sample of 300 was chosen" with no justification |
| 9 | Instruments | Table: construct, instrument + source, items, scale, alpha in this sample; AR adaptation steps in one line | Item lists |
| 10 | Procedure and ethics | Timeline, mode, approval body and number, consent, anonymity, attention checks | |
| 11 | Data quality and assumptions | Exclusions with reasons (n), missing data method, normality / VIF / Levene results, CMB test result | Raw histograms |
| 12 | Descriptives | M, SD, correlations matrix of the main variables with alphas on the diagonal | Every demographic |
| 13 | Result: H1 | The test, effect size with CI, p; one sentence of plain meaning; the table or figure | Three hypotheses on one slide |
| 14 | Result: H2 (and the mediation or moderation figure) | Indirect effect with bootstrap CI, or the interaction plot | |
| 15 | Result: remaining hypotheses and summary table | One row per hypothesis: supported / not supported with the key statistic | |
| 16 | Discussion: what agrees and what does not | Each main result vs two or three prior studies (ledger keys): agrees / disagrees and the candidate's reason | Restating results |
| 17 | Theoretical contribution | One sentence: what the theory can now say that it could not (scope, mechanism, boundary, resolution) | "Fills a gap" |
| 18 | Practical implications | Two or three recommendations, each tied to a result, each addressed to a named actor | Generic advice |
| 19 | Limitations and future research | The accepted limits from `design-redteam.md`, each paired with the future study that removes it | Boilerplate |
| 20 | Conclusion and thanks | The contribution in one sentence, the one number to remember, thanks; the AI-use disclosure line if the university requires it on the slides | New information |

Backup slides (not counted): the full regression table, the CFA / invariance table, the instrument items, the ethics approval letter, the pre-registration link, the power analysis screenshot. The committee asks; the candidate jumps to the backup.

## 5. بروتوكول المناقشة التجريبية  Mock-defense protocol

Run it at least twice: once a week before, once two days before. The agent plays the committee (one persona at a time or all five in rotation), the candidate answers aloud, and the agent scores each answer against the skeleton.

### Timing (confirm the university's actual rules)

| Phase | Typical duration | Notes |
|---|---|---|
| Chair opens, introduces the committee | 2 to 5 min | The candidate listens; no slides |
| Presentation | 15 to 25 min master's; 30 to 40 min doctorate | Rehearse to 90% of the limit; the chair cuts a long presentation |
| Questions, in committee order (external examiner first in many Arab universities) | 45 to 90 min | Each examiner takes 10 to 25 min; the supervisor usually speaks last or not at all |
| Closed deliberation | 10 to 30 min | The candidate leaves the room |
| Verdict and corrections | 5 to 10 min | Accept / accept with minor corrections / major corrections / resubmit / fail: wording varies by university |

### Rules the candidate rehearses

1. **Listen to the end of the question.** Then repeat its core in one clause ("You are asking whether the single-wave design can support H2.") before answering. It buys three seconds and confirms the question.
2. **Answer in the skeleton order**: claim, evidence (open the page), limit. Twenty to sixty seconds. Then stop. Silence is the examiner's turn.
3. **"I don't know" protocol.** Four moves, in order, never skipping the first:
   - Acknowledge: "I did not examine that" / "لم أتناول هذه النقطة في الرسالة".
   - Bound: say what the thesis does cover closest to it, with the page.
   - Reason: offer the best-informed guess, labelled as a guess ("my expectation, which I did not test, would be...").
   - Bridge: "it belongs in the future-research list; I would test it by..." Never invent a result, a source or a number under pressure: a fabricated citation in a viva is the one unrecoverable move.
4. **Concede the real limits early and precisely.** A limit conceded in the presentation (slide 19) cannot be "discovered" by an examiner. Conceding a limit is not conceding the thesis.
5. **Do not argue with an examiner's premise unless it is factually wrong about the thesis.** Then correct it gently with the page: "On page 74 the sample is stratified by faculty, not convenience."
6. **The chair's closing questions** ("what would you do differently", "what next") are answered from slide 19, in the positive.
7. **Numbers only from the thesis.** If asked for a statistic not in the thesis, say so and offer to compute it in the corrections.
8. **Arabic viva with English terms**: say the Arabic term and the English in the same breath the first time, as the thesis does; do not switch languages mid-answer unless the examiner does.

### Scoring the mock (the agent fills this per question)

| Question | Claim stated (0/1) | Evidence located with page (0/1) | Limit bounded, not conceded (0/1) | Under 60 s (0/1) | Note |
|---|---|---|---|---|---|

Questions scoring under 3 return to the next mock. The candidate also records which questions were asked twice in different words: those are the committee's real concerns.

## 6. جذوع الأسئلة  Question stems (Arabic and English)

The persona agents instantiate these stems with the thesis's own constructs, pages and numbers. Ten per persona, in the thesis language; both languages are given so a bilingual committee can be rehearsed.

### أ. صقر المنهجية  Methods hawk

| # | العربية | English |
|---|---|---|
| 1 | لماذا يصلح التصميم المقطعي للإجابة عن سؤال يتضمن كلمة "أثر" في صفحة [N]؟ | Why does a cross-sectional design answer a question that uses the word "effect" on page [N]? |
| 2 | ما الذي يمنع أن يكون [المتغير التابع] هو الذي يؤثر في [المتغير المستقل]؟ | What rules out [DV] driving [IV] rather than the reverse? |
| 3 | أي متغير مربك لم تقسه، ولماذا؟ | Which confounder did you not measure, and why? |
| 4 | كيف تم تبرير حجم العينة قبل جمع البيانات، وما مصدر حجم الأثر المستخدم؟ | How was the sample size justified before collection, and where does the effect size you used come from? |
| 5 | مَن لم يُستجب في عينتك، وفي أي اتجاه يحرّف غيابهم النتائج؟ | Who is missing from your sample, and in which direction does their absence bias the estimate? |
| 6 | كل بياناتك من مصدر واحد وفي وقت واحد: ما الذي فعلته إجرائياً وإحصائياً لتحيز الطريقة المشتركة؟ | All your data come from one source at one moment: what did you do, procedurally and statistically, about common-method bias? |
| 7 | صف خطوات ترجمة الأداة وتكييفها، ومن قام بالترجمة العكسية؟ | Describe the translation and adaptation steps for the instrument; who did the back-translation? |
| 8 | قارنتَ بين [مجموعتين] على بناء كامن: هل اختبرت تكافؤ القياس؟ | You compared [two groups] on a latent construct: did you test measurement invariance? |
| 9 | ما الذي تغيّر بين خطة البحث المعتمدة وما نُفّذ فعلاً؟ | What changed between the approved proposal and what was actually done? |
| 10 | أين رقم الموافقة الأخلاقية، وكيف ضمنت أن المشاركين يستطيعون الرفض؟ | Where is the ethics approval number, and how did you ensure participants could refuse? |

### ب. حارس النظرية  Theory purist

| # | العربية | English |
|---|---|---|
| 1 | ما الآلية التي تجعل [أ] يغيّر [ب] وفق النظرية التي تبنّيتها، لا وفق الدراسات السابقة؟ | By what mechanism does [A] change [B] under the theory you adopted, rather than according to prior studies? |
| 2 | أين تستخدم النظرية بعد الفصل الثاني؟ أرني صفحة في الفصل الخامس تعود إليها. | Where is the theory used after Chapter 2? Show me a page in Chapter 5 that returns to it. |
| 3 | عرّفتَ [البناء] في صفحة [N] وبصيغة مختلفة في صفحة [M]: أيهما قستَ؟ | You defined [construct] on page [N] and differently on page [M]: which one did you measure? |
| 4 | لماذا هذه النظرية وليس [النظرية المنافسة]؟ ماذا كانت ستتنبأ به بدلاً من ذلك؟ | Why this theory and not [the rival]? What would the rival have predicted instead? |
| 5 | نُظّرت هذه النظرية في سياق غربي: ما الذي يبرر انتقالها إلى عينتك، وما الذي يتغير؟ | This theory was built in a Western context: what justifies its transfer to your sample, and what changes? |
| 6 | الوسيط في نموذجك عملية أم متغير أُضيف لأن الدراسات السابقة أضافته؟ | Is the mediator in your model a process, or a variable added because prior studies added it? |
| 7 | هل مستوى النظرية ومستوى العينة ومستوى التحليل واحد؟ | Are the theory, the sampling unit and the analysis at the same level? |
| 8 | الفرضية [H] لم تُدعم: ماذا يعني ذلك للنظرية، لا للقياس؟ | Hypothesis [H] was not supported: what does that mean for the theory, not for the measurement? |
| 9 | ما إسهامك النظري في جملة واحدة لا تحتوي على عبارة "سدّ فجوة"؟ | State your theoretical contribution in one sentence that does not contain "fills a gap". |
| 10 | لو كانت كل فرضياتك مرفوضة، هل كان النموذج سيبقى صالحاً؟ وإذا كان كذلك، فهل هو نظرية؟ | If every hypothesis had been rejected, would the model still stand? If so, is it a theory? |

### ج. الممارس  Practitioner

| # | العربية | English |
|---|---|---|
| 1 | لو كان أمامك دقيقة واحدة مع الوزير أو المدير العام، ماذا تقول له من نتائجك؟ | If you had one minute with the minister or the CEO, what would you tell them from your results? |
| 2 | التوصية في صفحة [N]: مَن ينفذها، وكم تكلف، وما الدليل في الفصل الرابع عليها؟ | The recommendation on page [N]: who implements it, what does it cost, and which result in Chapter 4 supports it? |
| 3 | ما الذي يفعله القطاع فعلاً في هذا الموضوع اليوم، وهل تضيف رسالتك شيئاً إليه؟ | What does the sector already do about this today, and does your thesis add to it? |
| 4 | هل تشبه عينتك الناس الذين سيطبَّق عليهم هذا الكلام؟ | Does your sample resemble the people this would be applied to? |
| 5 | حجم الأثر الذي وجدته [قيمة]: هل يستحق قراراً إدارياً أم هو مجرد دلالة إحصائية؟ | The effect you found is [value]: does it warrant a management decision, or is it only statistically significant? |
| 6 | ما أول خطوة عملية في أول أسبوع بعد تبنّي توصياتك؟ | What is the first practical step in the first week after your recommendations are adopted? |
| 7 | أي نتيجة من نتائجك قد تُفهم خطأً إذا نُشرت في الصحافة؟ | Which of your results could be misread if it appeared in the press? |
| 8 | ما الأثر الجانبي المحتمل لتوصيتك على [فئة أخرى]؟ | What is the possible side effect of your recommendation on [another group]? |
| 9 | كيف يقيس المدير نجاح التوصية بعد سنة؟ | How would a manager measure, after a year, whether the recommendation worked? |
| 10 | لو لم تكن هناك ميزانية إضافية، ماذا يبقى من توصياتك؟ | With no extra budget, what remains of your recommendations? |

### د. ممتحن الإحصاء  Statistics examiner

| # | العربية | English |
|---|---|---|
| 1 | في الجدول [N] درجة الحرية [df] والعينة في النص [N]: كيف يتفقان؟ | Table [N] shows df = [df] and the text says N = [N]: how do they agree? |
| 2 | لماذا هذا الاختبار وليس [البديل]؟ ما الافتراضات التي فُحصت، وأين النتائج؟ | Why this test and not [the alternative]? Which assumptions were checked, and where are the results? |
| 3 | أعطني حجم الأثر وفترة الثقة لكل نتيجة رئيسة، لا قيمة p فقط. | Give me the effect size and the confidence interval for each main result, not only p. |
| 4 | النتيجة غير الدالة في الفرضية [H]: هل تعني عدم وجود أثر، أم عدم كفاية القوة؟ | The non-significant result for [H]: does it mean no effect, or insufficient power? |
| 5 | اختبرتَ الوساطة بخطوات بارون وكيني: لماذا لم تستخدم فترات ثقة Bootstrap للأثر غير المباشر؟ | You tested mediation by the Baron and Kenny steps: why not bootstrap confidence intervals for the indirect effect? |
| 6 | معامل ألفا الذي تذكره: من عينتك أم من الدراسة الأصلية؟ | The alpha you report: is it from your sample or from the original study? |
| 7 | كم اختباراً إحصائياً أُجري في الرسالة كلها، وكيف تعاملت مع تعدد الاختبارات؟ | How many statistical tests were run in the whole thesis, and how did you handle multiple testing? |
| 8 | ما نسبة الاستجابات المستبعدة ولماذا، وهل تختلف النتائج بدونها؟ | What share of responses was excluded and why, and do the results differ without the exclusion? |
| 9 | في صفحة [N] تقول إن R² = [قيمة] "قوية": بأي معيار؟ | On page [N] you call R² = [value] "strong": by what criterion? |
| 10 | لو أُعطيت البيانات نفسها وأسبوعاً إضافياً، أي تحليل تضيف؟ | Given the same data and one more week, which analysis would you add? |

### هـ. رئيس اللجنة  The chair

| # | العربية | English |
|---|---|---|
| 1 | لخّص إسهام رسالتك في جملة واحدة. | Summarise your thesis's contribution in one sentence. |
| 2 | يعِد الملخص بـ[X] وتختم الرسالة بـ[Y]: أين التقى الاثنان؟ | The abstract promises [X] and the conclusion delivers [Y]: where do they meet? |
| 3 | هل يعكس العنوان ما فعلته فعلاً؟ | Does the title reflect what you actually did? |
| 4 | ما الجديد هنا الذي لم يكن معروفاً قبل رسالتك؟ | What is new here that was not known before your thesis? |
| 5 | ما السؤال الذي كنت تتمنى ألا تسأله اللجنة؟ | Which question did you hope the committee would not ask? |
| 6 | لو بدأت من جديد، ماذا تغيّر؟ | If you started again, what would you change? |
| 7 | ما الدراسة التالية التي تخرج من هذه الرسالة مباشرة؟ | What is the next study that follows directly from this thesis? |
| 8 | أين أفصحت عن استخدام الذكاء الاصطناعي، وما الذي استُخدم فيه تحديداً؟ | Where did you disclose AI use, and for what exactly was it used? |
| 9 | أي جزء من الرسالة يصلح للنشر، وفي أي مجلة؟ | Which part of the thesis is publishable, and in which journal? |
| 10 | ما الذي تعلمته عن البحث العلمي من هذه الرسالة ولم يكن في الكتب؟ | What did you learn about research from this thesis that was not in the books? |

## 7. الملفات الناتجة  Output files

```
defense/
  questions.md        50 questions with answer skeletons (section 3 format), grouped by persona, sorted by likelihood
  deck-outline.md     the 20 slides with the exact numbers and ledger keys that go on each (section 4), plus backup slides
  mock-1.md, mock-2.md  the scoring tables from each mock (section 5)
  open-points.md      every question marked unknown after the second mock, with the page the candidate will re-read
```

Give the user the full absolute path of each file.

## 8. ما لا يفعله هذا الدليل  What this guide cannot do

- It does not know the university's viva rules (durations, order of speakers, verdict categories, whether slides must be in Arabic). Every such item here is marked typical; the department's guide decides.
- It cannot predict the committee's actual questions; it generates the fifty most defensible ones from the text. A committee member's personal interests are outside the thesis.
- It does not write the spoken answers. The skeleton is a scaffold; a candidate who reads an AI-written answer aloud fails the "own words" test that examiners apply instinctively.
- It cannot verify that the candidate can open the page in the room: that is the rehearsal's job.

## Verified sources

The statistics examiner's stems rely on arguments sourced and verified in [reviewers/statistics.md](reviewers/statistics.md): Preacher and Hayes (2008), DOI 10.3758/BRM.40.3.879 (bootstrapped indirect effects); Wasserstein and Lazar (2016), DOI 10.1080/00031305.2016.1154108 (p values); Cumming (2014), DOI 10.1177/0956797613504966 (effect sizes and CIs); Simmons, Nelson and Simonsohn (2011), DOI 10.1177/0956797611417632 (multiple testing). The methods hawk's stems rely on the sources verified in [reviewers/methods.md](reviewers/methods.md) and [red-team.md](red-team.md): Antonakis et al. (2010), DOI 10.1016/j.leaqua.2010.10.010; Podsakoff et al. (2003), DOI 10.1037/0021-9010.88.5.879; Beaton et al. (2000), DOI 10.1097/00007632-200012150-00014; Vandenberg and Lance (2000), DOI 10.1177/109442810031002; Lakens (2022), DOI 10.1525/collabra.33267. The viva timings and verdict categories are conventions, not sourced claims, and are marked as such.
