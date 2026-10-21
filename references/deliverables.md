# One study, five outputs (AR + EN)

After the paper exists (stage 8 passed), the same study is told five more times: a conference abstract, a one-page Arabic policy brief (ملخص سياسات), a LinkedIn post, a three-minute lay summary and a visual abstract. All five come from one set of numbers and one source line. Script: `scripts/deliverables.py` (`visual`, `check`, `selftest`).

## Rules that apply to all five

| Rule | How it is enforced |
|---|---|
| One number set. Pick at most four key statistics from `analysis/output.txt`, write them once in a "key numbers" block (below), and reuse those exact values and rounding everywhere | `deliverables.py check <file> --evidence analysis/output.txt` on every output; `visual` reads the file directly and refuses any label not in it |
| Every number has a source: the study itself (named once) or a ledger entry | `check --kind post/brief/lay` fails without a source line |
| No hype, no causal verbs for correlational designs | `check` fails on the hype list, warns on causal verbs (`--causal-design` for experiments) |
| Same meaning in Arabic and English, not a word-for-word translation; technical terms identical (English term in parentheses once) | writing-style.md, bilingual abstract rule |
| Numbers: English drops the leading zero for r, β, p (APA); Arabic keeps it (0.31) and uses Western digits | `fmt_value` in the script does both |
| No em or en dashes | `check` fails on them |
| Nothing goes out before the paper is accepted, in press, or posted as a preprint; the source line says which | the source line template below |
| AI disclosure: the abstract and the brief carry the paper's one-line disclosure; the post and lay summary do not need it unless the venue asks | integrity.md templates |

Order of writing: abstract, lay summary, policy brief, LinkedIn post, visual abstract. Each later one is shorter than the one before; the numbers never change.

### Key numbers block (write it first, keep it in the project folder as `key_numbers.md`)

```
# key numbers | from analysis/output.txt | 2026-10-21
main effect : corr.sleep~gpa.r = 0.311146        -> r = .31 (EN) / r = 0.31 (AR)
precision   : corr.sleep~gpa.ci_low/ci_high      -> 95% CI [.18, .43]
sample      : corr.sleep~gpa.n = 199             -> n = 199
one more    : freq.gender.female.pct = 55        -> 55% women
design      : cross-sectional survey, one university, self-reported sleep
source line : Author, A. and Author, B. (2026). Title. Journal. https://doi.org/10.xxxx (or: under review / preprint DOI)
```

Choose: the effect for the main hypothesis (an effect size, not a p-value), its precision (CI) or p, the sample, and one descriptive that a reader needs. A null result is a key number too: "no difference, p = .314, d = -0.14".

## 1. Conference abstract (structured, 250 words)

Most conferences (and Emerald, Elsevier health journals) ask for a structured abstract. Headings vary: match the call for papers exactly; the default below is the common one.

Rules: past tense for what was done; numbers with their statistic; no citations unless the call allows them; no abbreviations without expansion; 4 to 6 keywords not already in the title; the limit (usually 250 or 300) includes everything except the title and keywords. Check with `deliverables.py check abstract.md --kind abstract --evidence analysis/output.txt` (fails over 250 words; `--max-words 300` if the call allows 300).

### Template EN

```
# [Title: variables + population, 10 to 15 words]

**Background:** [Two sentences: the problem and the gap. No numbers from other studies unless in the ledger.]
**Purpose:** [One sentence: this study examined whether ... among ...]
**Methods:** [Design; population and sample: n = [ ] [who, where]; instrument(s) and reliability: α = [ ]; analysis.]
**Results:** [Main finding with its statistic: r = [ ], p [ ], 95% CI [[ ], [ ]]. One or two secondary findings. A null result stated as a result.]
**Conclusions:** [What it means for practice or theory in one sentence; the main limitation in half a sentence.]
**Keywords:** [4 to 6]
```

### Template AR (الملخص الهيكلي)

```
# [العنوان: المتغيرات والمجتمع، 10 إلى 15 كلمة]

**الخلفية:** [جملتان: المشكلة والفجوة.]
**الهدف:** [هدفت الدراسة إلى الكشف عما إذا كان ... لدى ...]
**المنهج:** [التصميم؛ مجتمع الدراسة وعينتها: ن = [ ] [من، أين]؛ الأداة وثباتها: ألفا = [ ]؛ أسلوب التحليل.]
**النتائج:** [النتيجة الرئيسة بإحصاءها: r = [ ]، p [ ]، فترة الثقة 95% [[ ]، [ ]]. نتيجة أو نتيجتان ثانويتان. النتيجة غير الدالة تُذكر بوصفها نتيجة.]
**الخلاصة:** [الدلالة النظرية أو التطبيقية في جملة؛ وأهم محدد للدراسة في نصف جملة.]
**الكلمات المفتاحية:** [4 إلى 6]
```

Write the two from the same key numbers block, separately, then run `check` on each.

## 2. Policy brief in Arabic (ملخص سياسات، صفحة واحدة)

Decision-makers read the title, the executive summary and the recommendation; the rest is there for their advisor. One page is about 450 to 550 Arabic words in a 12-point font with one table or figure. Sections, in the order ministries, municipalities and NGOs in the region expect them:

| Section | Content | Length |
|---|---|---|
| العنوان | A message, not a topic: "النوم الكافي يرتبط بتحصيل أعلى: ما الذي يمكن للجامعات فعله" | one line |
| الخلاصة التنفيذية | Three lines: the problem, what the study found (one number), what is recommended | 40 to 60 words |
| المشكلة والسياق (لماذا الآن) | Why the decision-maker's institution should care now; one ledger-backed number at most | 60 to 90 words |
| ما تقوله الأدلة | Three bullets, one number per bullet, the source after each number: (الدراسة الحالية، ن = 199) or a ledger citation | 90 to 130 words |
| الخيارات أمام صانع القرار | Two or three options with cost and expected effect in plain words; the "do nothing" option is allowed | 80 to 120 words |
| التوصية | One option, one sentence, with who does it and by when | 30 to 50 words |
| حدود الدليل | What the study cannot say (design, one site, self-report) in two lines; this section is what makes the brief credible | 30 to 50 words |
| المصدر وجهة الاتصال | The source line, the AI-disclosure line of the paper, the author's institutional email | 2 lines |

Rules: no statistics symbols in the body (write "ارتباط إيجابي متوسط (r = 0.31)" once in the evidence section, then "أكثر نوماً، معدل أعلى"); decision verbs (تعتمد، تخصص، تلزم، تراجع); no "يثبت" or "يؤدي إلى" for a cross-sectional study; Western digits; the document is RTL (build with `build_docx.py`, which sets paragraph direction; in Markdown the file is plain text). Check with `deliverables.py check brief.md --kind brief --evidence analysis/output.txt` (sections, length, source line, hype, numbers).

### Template AR

```
# [العنوان: رسالة واحدة]

## الخلاصة التنفيذية
[المشكلة في جملة.] [ما وجدته الدراسة في جملة برقم واحد: ... (الدراسة الحالية، ن = [ ]).] [التوصية في جملة.]

## المشكلة والسياق: لماذا الآن
[...]

## ما تقوله الأدلة
- [نتيجة 1 برقمها ومصدرها]
- [نتيجة 2 برقمها ومصدرها]
- [نتيجة 3 برقمها ومصدرها]

## الخيارات أمام صانع القرار
1. [الخيار الأول: ما هو، كلفته التقريبية، أثره المتوقع]
2. [الخيار الثاني]
3. [الإبقاء على الوضع الحالي: ما الذي سيستمر]

## التوصية
[خيار واحد، من ينفذه، ومتى.]

## حدود الدليل
[التصميم، الموقع الواحد، التقرير الذاتي، ما لا تستطيع الدراسة قوله.]

## المصدر وجهة الاتصال
[سطر المصدر الكامل مع DOI أو "قيد التحكيم".] [سطر الإفصاح عن استخدام الذكاء الاصطناعي كما ورد في الورقة.] [البريد المؤسسي.]
```

An English brief uses the same eight sections (Executive summary, Why now, What the evidence says, Options, Recommendation, Limits of the evidence, Source and contact).

## 3. LinkedIn post (EN and AR)

Structure, in this order: the finding as a plain sentence (the hook, no question-bait); what was done in one line (n, who, where); the key number with its statistic in parentheses; what it means in one line; what it does not mean in one line; the source line; 3 to 5 hashtags. Recommended under 1,300 characters (the platform cuts the preview after about 210 characters, so the first sentence is the finding); hard limit 3,000.

Banned: the hype list in the script ("groundbreaking", "proves", "ثوري", "يثبت"...), questions as hooks, numbers without the statistic, screenshots of tables. Allowed: one emoji at most, a link to the paper or preprint, tagging co-authors. Post only after acceptance or a public preprint; respect the journal's embargo. Arabic and English are two posts (or one post with the Arabic first), same number, same source line. Check with `deliverables.py check post.md --kind post --evidence analysis/output.txt`.

### Template EN

```
[The finding in one plain sentence.]

We surveyed [n = [ ]] [who] at [where] and measured [what].

Key number: [statistic] = [ ] ([what it means in words]).

What this means: [one line].
What it does not mean: [one line: correlation, one site, self-report].

Source: [Authors (year). Title. Journal. https://doi.org/...] or [preprint link] or [under review].
#[tag1] #[tag2] #[tag3]
```

### Template AR

```
[النتيجة في جملة واحدة واضحة.]

استطلعنا آراء [ن = [ ]] [من] في [أين] وقسنا [ماذا].

الرقم الرئيس: [الإحصاء] = [ ] ([معناه بالكلمات]).

ما تعنيه النتيجة: [سطر واحد].
ما لا تعنيه: [سطر واحد: ارتباط لا سببية، موقع واحد، تقرير ذاتي].

المصدر: [المؤلفون (السنة). العنوان. المجلة. https://doi.org/...] أو [قيد التحكيم].
#[وسم1] #[وسم2] #[وسم3]
```

## 4. Three-minute lay summary

For a department newsletter, a university news page, a radio slot or the "plain language summary" box some journals now ask for. Three minutes of speech is about 400 to 450 English words or 350 to 400 Arabic words (the script's `--kind lay` range is 300 to 520 words). Sentences under 25 words; no statistics symbols; every technical term replaced or defined on first use; numbers translated into everyday units ("students who slept one hour more had, on average, a GPA 0.13 points higher").

Structure: the question in everyday words; why anyone should care; what we did (who, how many, how); what we found (one or two numbers in plain words); what it does not mean; what happens next. Check with `deliverables.py check lay.md --kind lay --evidence analysis/output.txt` (warns on jargon and long sentences, fails on numbers that are not in the evidence).

### Template EN

```
# [Title as a question or a plain statement]

[The question, in one or two sentences a neighbour would understand.]

[Why it matters to the reader: one short paragraph.]

[What we did: "We asked [n] [who] at [where] about [what] and compared it with [what]." No instrument names.]

[What we found: the key number in plain words, then one secondary finding. "On average, students who slept one more hour had a GPA 0.13 points higher. Stress went the other way."]

[What it does not mean: "This is a snapshot of one university, and students reported their own sleep, so we cannot say that sleep causes better grades."]

[What next: one sentence.]

Source: [source line].
```

### Template AR

```
# [العنوان سؤالاً أو جملة بسيطة]

[السؤال في جملة أو جملتين يفهمهما القارئ غير المتخصص.]

[لماذا يهم القارئ: فقرة قصيرة.]

[ماذا فعلنا: "سألنا [ن] [من] في [أين] عن [ماذا] وقارنّاه بـ[ماذا]." من دون أسماء الأدوات.]

[ماذا وجدنا: الرقم الرئيس بكلمات يومية، ثم نتيجة ثانوية واحدة.]

[ما لا تعنيه النتيجة: "هذه صورة لحظية من جامعة واحدة، والطلبة هم من أبلغوا عن نومهم، لذا لا نستطيع القول إن النوم يسبب تحصيلاً أعلى."]

[ما التالي: جملة واحدة.]

المصدر: [سطر المصدر].
```

## 5. Visual abstract (specification)

One image that a reader understands in ten seconds: the finding as a sentence, up to four numbers, the source. Generated, never hand-typed:

```
python -X utf8 deliverables.py visual --evidence analysis/output.txt \
    --labels "corr.sleep~gpa.r:Sleep hours and GPA (correlation)" \
             "regress.gpa.sleep.beta:Sleep predicting GPA, controlling for stress" \
             "freq.gender.female.pct:Women in the sample" \
    --title "More sleep goes with higher grades among 199 students" \
    --subtitle "Cross-sectional survey, one university, self-reported sleep" \
    --source "Author (2026). Under review." --out visual_abstract.svg
```

Arabic: add `--lang ar` with Arabic title, captions and source; the text runs right to left (`direction="rtl"` on the SVG root and every Arabic text element), the cards fill from the right, the statistics stay left-to-right, and the leading zero is kept (r = 0.31).

| Element | Spec |
|---|---|
| Canvas | 1200 x 675 px (16:9) by default; `--width 1200 --height 1200` for journals that ask for square; check the author guidelines |
| Title | The finding as one sentence, at most 12 words, 40 px bold, wrapped to two lines at most. Any number in it must be in the evidence (the script refuses otherwise) |
| Subtitle | Design and sample in one line (optional) |
| Cards | 1 to 4, one row, each: the statistic with its symbol (r = .31, β = .29, 55%, n = 199, p < .001), a plain caption of at most three short lines, the sample size from the sibling `.n` key, and the evidence key in small monospace so a reader can trace the number |
| Colours | White background, one accent colour (`--accent "#087F8C"`), near-black text, grey captions; no gradients, no icons that imply causation (arrows only for experimental designs) |
| Fonts | System fonts only, named in the SVG (`Segoe UI, Tahoma, Arial, Noto Naskh Arabic, sans-serif`); nothing is downloaded, so the file is self-contained |
| Footer | Source line (authors, year, venue, DOI or "under review") and the evidence file name with the date |
| Null results | Show them: "d = -0.14" with caption "No gender difference in GPA (p = .314)"; a visual that hides the null is a biased abstract |
| Export | Open the SVG in a browser and print to PDF or use Inkscape / `rsvg-convert` for PNG; PyMuPDF (`fitz`) rasterises it too but its fallback font may break Arabic letter joining, so proof Arabic in a browser |

What the script refuses: a label whose key is not in the evidence file (it prints the closest keys and writes nothing), more than four labels, and any number typed into the title, subtitle, caption or source line that the evidence does not contain. What it cannot check: whether a caption describes the statistic truthfully (a correlation captioned as an effect). Read each card against the `# APA:` line in `output.txt`.

## Commands

| Command | Purpose |
|---|---|
| `deliverables.py visual --evidence analysis/output.txt --labels "KEY:Caption" ... --title "..." --out va.svg` | draw the visual abstract from evidence only (`--lang ar`, `--subtitle`, `--source`, `--accent`, `--width/--height`, `--no-n`) |
| `deliverables.py check abstract.md --kind abstract --evidence analysis/output.txt` | numbers + 250-word limit + the four structured sections |
| `deliverables.py check brief.md --kind brief --evidence analysis/output.txt` | numbers + one-page length + the brief's sections + source line + hype |
| `deliverables.py check post.md --kind post --evidence analysis/output.txt` | numbers + 3,000-character limit (1,300 warning) + source line + hashtags |
| `deliverables.py check lay.md --kind lay --evidence analysis/output.txt` | numbers + 3-minute length + jargon and long-sentence warnings + source line |
| `deliverables.py check any.md --evidence analysis/output.txt` | numbers, dashes and hype only (a tweet, a slide, an email) |
| `deliverables.py selftest` | the positive case and the negative controls |

`check` exits 1 on any FAIL (a number not in the evidence, a flipped sign, over the limit, a missing section or source line, a hype word, a dash). WEAK matches (a value found only against an unlabelled evidence number) are warnings: label the evidence line or restate the number with its statistic.

## Output checklist

| Deliverable | Pass condition |
|---|---|
| key_numbers.md | at most four statistics, each with its evidence key, one source line |
| abstract (EN, AR) | `check --kind abstract` PASS for both; same numbers in both |
| policy brief (AR) | `check --kind brief` PASS; eight sections; opened in Word RTL after `build_docx.py` |
| LinkedIn post (EN, AR) | `check --kind post` PASS; posted only after acceptance or preprint |
| lay summary | `check --kind lay` PASS; read aloud in under three minutes |
| visual abstract | `visual` RESULT PASS; proofed in a browser (Arabic shaping); null results shown |
| all five | the same values and rounding as the paper's results section; `scholar.py numbers` passed on the paper first |
