# Integrity: authorship, fabrication, AI disclosure

Checked against live sources on 2026-10-20. Policies change: when a venue matters, open its current author guidelines and follow them over this file.

## 1. Authorship modes

Ask once, at the start: "Who will be named as the author, and where will this be submitted?"

The rule is **who asks**: the author may get AI help with their own work (and must disclose it); nobody may get work produced for someone else to submit as their own.

| Signal in the request | Mode | Response |
|---|---|---|
| "my paper", "my thesis", "my results", the user's own data | A. Own research | Full help. For a student's own thesis: say once that the university's AI policy decides how much AI drafting is allowed and that the disclosure is required; the student makes the research decisions; mark sentences they must adapt (their RQ, their context) |
| "we", "our team", the user will be co-author or acknowledged | B. Co-author | Full help, include the credit line |
| "my student", "my daughter's thesis", a supervisor or tutor helping someone who writes | C. Coaching | Structure, questions, feedback, explanations, editing of the student's own text within university rules |
| Company, NGO, ministry report | D. Organisation | Full help |
| "my client will submit it", "write it in his name", "the student pays for the chapter", a writing service | Refused | One-line decline, then Mode C material in the same reply |
| Checking references, choosing or vetting a journal, running the stage 8 checks | Any | No gate: assume Mode A in one line |

### Service providers and other intermediaries

When the requester runs a writing service or stands between you and the student:

- Address the coaching material **to the student** ("you"), not to the provider.
- Give the structure and guiding questions, never an outline so detailed that each bullet is a ready sentence.
- Suggest the legal version of the business in one line: coaching, editing of the student's own drafts, statistics consulting, reference checking, formatting. These can be paid services.

### Mode C limits (coaching)

| Allowed | Not allowed |
|---|---|
| Chapter outline and guiding questions per section | Writing the chapter text to be submitted |
| A verified reading list from the ledger | Rewriting the student's draft wholesale |
| Line-level feedback and comments on the student's draft | Producing final research questions for them |
| Explaining a statistical test and how to read its output | Running the analysis and writing up their results for them |
| Language editing of text the student wrote, if the university allows it | Anything the university's own AI or editing policy forbids |
| Short model sentences that show a pattern (marked as examples) | Model paragraphs long enough to paste in |

### Decline wording

EN: "I can't write work that someone will submit as their own for a degree: that is contract cheating, whoever pays. I can coach the student through writing it themselves: outline, verified sources, feedback on their drafts, and explaining the analysis."

AR: "ما بقدر أكتب عمل رح يقدّمه شخص ثاني باسمه للحصول على درجة علمية، هذا انتحال أكاديمي (contract cheating) بغض النظر عن الدفع. بقدر أرافق الطالب وهو يكتبه بنفسه: خطة الفصل، مراجع متحقق منها، ملاحظات على مسوداته، وشرح التحليل."

Then deliver the Mode C material in the same reply. Do not lecture beyond this.

### Fabricated numbers: decline wording

EN: "I can't write results with numbers your data hasn't produced: that is data fabrication, and t, df and p values are easy to check against each other. Send me the data (CSV or Excel) and I'll run the analysis and write the section from the real output, or here is a template with placeholders and the exact analysis to run."

AR: "ما بقدر أكتب نتائج بأرقام ما طلعت من بياناتك، هذا تلفيق بيانات، والقيم (t وdf وp) سهل التحقق من تناسقها. ابعتلي البيانات (CSV أو Excel) وبشغّل التحليل وبكتب القسم من المخرجات الحقيقية، أو هذا قالب جاهز فيه أماكن فارغة للأرقام مع التحليل المطلوب بالضبط."

### Law, for context when the user is a service provider

| Jurisdiction | Law | Notes |
|---|---|---|
| England | Skills and Post-16 Education Act 2022, ss.26-30 | Offence to provide or advertise in commercial circumstances; a "for reference only" term is not by itself a defence (s.27(5)) |
| Ireland | QQI Amendment Act 2019, s.43A | No commercial element needed; up to EUR 100,000 and/or 5 years |
| Australia | TEQSA Act 2011, ss.114A-114B | First penalty: TEQSA v Chegg [2026] FCA 330 |
| New Zealand | Education and Training Act 2020, s.393 | Fine up to NZD 10,000 |
| California (US) | Education Code s.66400 | Selling papers known to be submitted for credit; many US states have similar laws |
| Jordan, KSA, UAE, Gulf | **Unknown**: no dedicated statute confirmed | Universities still treat it as misconduct (degree revoked). Never call it "legal" |

## 2. Fabrication rules

| Never | Instead |
|---|---|
| A reference typed from memory | `scholar.py search` then `add` |
| A DOI "that looks right" | `scholar.py verify` |
| A finding attributed to a paper whose abstract you have not read | `scholar.py abstract DOI`, or ask the user for the PDF |
| "Realistic" statistics | A template with `[ ]` placeholders + the `analyze.py` commands to run; `numbers template.md` must pass |
| A quartile, SJR value, impact factor or acceptance rate from memory | `scholar.py journal ISSN --sjr file`; acceptance rates only from the journal's own page |
| An AI-generated figure presented as data | Charts drawn from the analysis output only |
| Citing an AI chat as the source of a fact | Find the primary source (ICMJE forbids AI output as a primary source) |

Retracted papers enter the ledger only with `--allow-retracted`, and only when the sentence discusses the retraction itself.

## 3. AI-use disclosure templates

Ask for the target venue first: placement differs.

| Venue | Where | What |
|---|---|---|
| Elsevier | Separate section **immediately before the references**, heading: *Declaration of generative AI and AI-assisted technologies in the manuscript preparation process* (new heading since June 2026) | Template below |
| Springer Nature | **Methods** (books: acknowledgements, introduction or preface). AI copy editing now *should* be declared | Tool, version, what it did, human checks |
| COPE-member journals | Materials and Methods or similar | Tool and how it was used |
| ICMJE (medical) | **Cover letter + manuscript**: writing help in acknowledgments; AI used in data, analysis or figures in methods | Never cite AI output as a primary source |
| IEEE | **Acknowledgments** | System name, sections affected, extent |
| Taylor & Francis | AI-usage disclosure statement | Full tool name **with version**, how and why |
| University thesis | The university's own form or a preface statement | Follow the graduate school's policy; if none, use the generic template |

### Elsevier (copy word for word, fill the brackets)

> During the preparation of this work, the author(s) used [NAME OF TOOL / SERVICE] in order to [REASON]. After using this tool/service, the author(s) reviewed and edited the content as needed and take(s) full responsibility for the content of the published article.

### Generic English (Springer Methods, T&F, theses)

> Generative AI use: [Tool name, version/model] was used for [literature search assistance / language editing / structuring drafts / drafting code for the analysis]. All sources were verified against Crossref and OpenAlex, all statistics were computed from the study data by the author(s), and the author(s) reviewed and edited all output and take full responsibility for the content.

### Arabic (theses and Arabic-language journals)

> الإفصاح عن استخدام الذكاء الاصطناعي: استُخدمت أداة [اسم الأداة والإصدار] في [المساعدة في البحث عن الأدبيات / التدقيق اللغوي / تنظيم المسودات / كتابة شيفرة التحليل]. وقد جرى التحقق من جميع المراجع عبر Crossref وOpenAlex، وحُسبت جميع النتائج الإحصائية من بيانات الدراسة من قِبل الباحث/الباحثين، الذين راجعوا جميع المخرجات وحرّروها ويتحمّلون المسؤولية الكاملة عن المحتوى.

### When AI drafted the prose (say so plainly)

EN:
> Generative AI use: [Tool name, version/model] drafted [sections, e.g. the literature review and discussion] from the author's research question, outline, verified sources and analysis output. The author(s) revised all text, checked every citation against its source and every statistic against the analysis output, and take full responsibility for the content.

AR:
> الإفصاح عن استخدام الذكاء الاصطناعي: استُخدمت أداة [اسم الأداة والإصدار] في صياغة مسودة [الأقسام، مثل: الدراسات السابقة والمناقشة] انطلاقاً من سؤال الدراسة وخطتها ومراجعها المتحقق منها ومخرجات التحليل التي أعدّها الباحث/الباحثون، الذين راجعوا النص كاملاً وتحققوا من كل توثيق مقابل مصدره ومن كل قيمة إحصائية مقابل مخرجات التحليل، ويتحمّلون المسؤولية الكاملة عن المحتوى.

Some universities forbid AI-drafted thesis text outright: that is the student's call to check, and the skill says so once.

No declaration is needed for basic spelling and grammar checks or reference-manager functions (Elsevier), but declare when unsure.

### Citing an AI tool (APA 7, guidance updated 9 Sept 2025)

- A specific shared chat: `OpenAI. (2025, March 3). *Title of chat* [Generative AI chat]. ChatGPT/GPT-5. https://chatgpt.com/share/...` In text: (OpenAI, 2025).
- A tool in general: `Anthropic. (2026). *Claude* [Large language model]. https://claude.ai`
- The author is always the company, never the tool. Prompts can go in the text or an appendix.

## 4. Images

AI must not create or alter primary research images (microscopy, blots, scans, photos of results). Schematics are allowed only where the venue permits, disclosed in the caption. Data charts come from the analysis output.
