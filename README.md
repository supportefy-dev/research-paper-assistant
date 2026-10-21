# Research Paper Assistant

A [Claude Code](https://claude.com/claude-code) skill for writing and reviewing academic research papers, theses and proposals, in **Arabic and English**, with integrity enforced by scripts rather than by promises:

- **No source without a verified DOI or ISBN.** The source ledger refuses fake DOIs, retraction notices and retracted papers. A whole reference list can be checked in one command, including the common AI hallucination of a fake paper that borrows a real journal, volume and page.
- **No finding without a verbatim quote.** Full texts are fetched from open-access sources (or the user's own PDFs), and every cited finding must carry a quote with a page number.
- **No number without analysis output.** Statistics are computed on the user's data and every value in the Results section is checked against the matching label in the output (a flipped sign or a wrong df fails).
- **No ghostwriting.** Work that someone else will submit as their own is declined and turned into coaching.

All tools are free: OpenAlex, Crossref (with Retraction Watch data), Semantic Scholar, Europe PMC, Unpaywall, DOAJ, Open Library, OpenReview, eLife, plus a journal-ranking file the user downloads.

## Install

Clone into your Claude Code skills folder:

```bash
git clone https://github.com/supportefy-dev/research-paper-assistant ~/.claude/skills/research-paper-assistant
pip install -r ~/.claude/skills/research-paper-assistant/requirements.txt
```

On Windows the skills folder is `%USERPROFILE%\.claude\skills\`. The [skills CLI](https://github.com/vercel-labs/skills) also works: `npx skills add supportefy-dev/research-paper-assistant`.

Requirements: Python 3.10+, `numpy`, `scipy`, `requests`, `pymupdf`, `pypdf`, `python-docx`, `openpyxl`. Optional: `semopy` (CFA fit indices), `ffmpeg` and `whisper.cpp` (interview transcription, fully local).

Then, in Claude Code, ask for anything research-related ("find me a gap on X", "check my references", "write my results from this CSV", "which Q1 journal fits this abstract", "جهزني للمناقشة"). The skill loads itself.

### Optional setup

| What | Why | How |
|---|---|---|
| OpenAlex API key (free) | Without a key, everyone on your network shares 1,000 credits a day (a search costs 10). A key gives 10,000. | `curl -X POST https://api.openalex.org/api-keys -H "Content-Type: application/json" -d '{"email":"you@example.com"}'`, click the activation email, then save the key to `~/.config/research-paper-assistant/openalex.key` (one line) or set `OPENALEX_API_KEY` |
| `RESEARCH_MAILTO` | Faster Crossref, and required for Unpaywall full texts | Set it to your own email |
| SJR journal file | Quartiles (Q1-Q4) per category | Download from https://www.scimagojr.com/journalrank.php ("Download data") and pass `--sjr <file>` or set `SJR_CSV`. The site blocks scripts and the file may not be redistributed |

## What it does, stage by stage

| Stage | Tools |
|---|---|
| 1. Topic and gap | literature search (OpenAlex, Crossref for Arabic journals), `gapmap.py` (where studies disagree, empty cells), `comap.py` (co-citation map: schools of thought, seminal papers, frontier) |
| 2. Literature | source ledger (`add`, `abstract`, `fix`), `snowball.py` (citation chasing with PRISMA counts), `evidence.py` (full texts, quotes with pages, claim audit, evidence trail) |
| 3. Verify sources | `verify --citations-file` (REAL / REAL with errors / RETRACTED / FABRICATED / UNVERIFIED, with corrected APA) |
| 4. Design | theory registry (30 theories, sources verified), red-team the design before data collection, `instruments.py` (validated scales, pilot item analysis, back-translation protocol, licence table), `effects.py` (effect sizes from the literature, power incl. mediation) |
| 5. Analysis | `autopsy.py` (careless responders, GRIM, Harman, statcheck), `analyze.py` (descriptives, correlation, regression with diagnostics, t-test, ANOVA, alpha), `analyze_sem.py` (mediation, moderation, CFA with CR/AVE/HTMT, PLS), `qual.py` (interviews: transcription, coding, kappa, themes with timestamps) |
| 6. Writing | IMRaD or the five-chapter Arab-university thesis, bilingual abstract, APA 7 in both languages |
| 7. Journal | SJR shortlist by category quartile, DOAJ and hijacked-journal checks, `journalfit.py` (house profile, fit score, desk-reject risk) |
| 8. Pre-submission | citation audit, numbers audit, `similarity.py` (paraphrase risk), `reviews.py` (real open peer reviews), a 6-reviewer panel, AI-use disclosure templates (Elsevier, Springer Nature, ICMJE, IEEE, T&F, theses), `build_docx.py` (Word with correct Arabic RTL, APA tables, university presets) |
| 9. After | `package.py` (OSF reproducibility zip), `watch.py` (new papers), defense preparation, `deliverables.py` (conference abstract, policy brief, visual abstract from real numbers) |

Every script has `--help`, and most have a `selftest`.

## How the checks look

```
$ python -X utf8 scripts/scholar.py verify --citations-file refs.txt
| # | verdict      | as cited                                   | doi                       | detail                              |
| 1 | REAL         | Junco, R. (2012). Too much face and ...    | 10.1016/j.chb.2011.08.026 |                                     |
| 4 | REAL, ERRORS | Kirschner, P. A., & Karpinski (2011)...    | 10.1016/j.chb.2010.03.024 | year 2011 -> 2010                   |
| 5 | RETRACTED    | Wakefield, A. J., et al. (1998). Ileal...  | 10.1016/s0140-6736(97)... | retracted 2010 by notice ...        |
| 6 | FABRICATED?  | Hamdan, K., & Zoubi, R. (2021). TikTok...  |                           | its journal/volume/page belongs to a different paper ... |

$ python -X utf8 scripts/scholar.py numbers results.md --evidence analysis/output.txt
SIGN DIFFERS line 3: r = -.31  | Sleep correlated with GPA, r(194) = -.31, p < .001 ...
RESULT: FAIL (0 unsupported, 1 sign, 0 weak)
```

## Honest limits

- Regex extractions (direction of an effect in an abstract, sample sizes, scale reliability, a journal's typical methods) are **candidates** the agent confirms by reading; every output says so.
- Open peer reviews exist only for some fields (OpenReview, eLife, F1000); for business and education the skill falls back on published studies of reviewer comments.
- Paywalled papers are never bypassed: drop the PDF into `papers/` and the skill quotes from it.
- Quartiles come only from the SJR file you download; the skill never estimates one.
- A transcript from Whisper is ASR output until a human has checked it against the audio.

## Tests

```bash
python -X utf8 tests/run_tests.py          # every module's selftest + the planted-error regression (offline)
python -X utf8 tests/run_tests.py --live   # also checks a real and a fake DOI against Crossref
```

## Contributing

Read `references/module-contract.md` first: it holds the data formats, the CLI conventions, the honesty rules every script enforces, and the testing rule (a positive case and a planted-error negative control before anything is reported done).

## License

MIT. Built by [Supportefy](https://supportefy.com).

---

## بالعربية

مهارة لـ Claude Code لكتابة ومراجعة الأبحاث العلمية والرسائل الجامعية بالعربية والإنجليزية، تفرض النزاهة بالسكربتات لا بالوعود: لا مرجع بدون DOI أو ISBN متحقق منه، لا نتيجة مقتبسة بدون اقتباس حرفي مع رقم الصفحة، لا رقم إحصائي بدون مخرجات تحليل حقيقية على بيانات الباحث، ولا كتابة لعمل يقدمه شخص آخر باسمه.

تغطي المراحل من إيجاد الفجوة البحثية (أين تختلف الدراسات)، إلى الدراسات السابقة، والمنهجية (المقاييس المعتمدة، حجم العينة المبرر، نظرية لكل فرضية)، والتحليل (تنظيف البيانات، الانحدار، الوساطة والتعديل، CFA و PLS، تحليل المقابلات)، واختيار المجلة (الربع في SJR، كشف المجلات المختطفة)، والمراجعة قبل الإرسال (لجنة من ستة محكّمين افتراضيين، فحص التشابه، الإفصاح عن استخدام الذكاء الاصطناعي)، ثم ملف Word بإخراج عربي صحيح وقوالب لعدد من الجامعات العربية، والتحضير للمناقشة.

التثبيت: استنسخ المستودع داخل مجلد `~/.claude/skills/` ثم `pip install -r requirements.txt`. كل الأدوات مجانية.
