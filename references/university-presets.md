# University formatting presets for build_docx.py

`--preset NAME` loads `references/university-presets.json` and applies the university's page, font, spacing, cover, numbering and TOC rules. A CLI flag (`--size`, `--margins-cm`, `--spacing`...) always beats the preset; the preset beats the built-in defaults. `--list-presets` prints the table below from the JSON.

```bash
python -X utf8 "$S/build_docx.py" thesis.md -o thesis.docx --preset ju
python -X utf8 "$S/build_docx.py" thesis.md -o thesis.docx --preset generic-arab --lang ar
python -X utf8 "$S/build_docx.py" --list-presets
```

## What each preset says (read on 2026-10-21)

| preset | university | verified | paper | margins cm (T/B/binding/other) | fonts (AR / EN) | spacing | page numbers | refs |
|---|---|---|---|---|---|---|---|---|
| `ju` | University of Jordan | yes, Deans Council spec read | A4 | 2.5 / 2.5 / 3.5 / 2.5 | Arabic Transparent 14 (headings 16) / Times New Roman 12 (headings 14) | AR 1.5, EN 2.0, refs single | top centre; roman (EN) or abjad (AR) front matter; none on the title page | guide's author-year |
| `yarmouk` | Yarmouk University | yes, 2007/2008 guide read | A4 | 2.5 / 2.5 / 3.5 / 2.5 | not stated (defaults) | AR 1.5, EN 2.0 | abjad front matter (AR); position not stated | guide's author-year |
| `just` | Jordan Univ. of Science and Technology | yes, official MSc template read | A4 | 2.5 (5.0 on chapter-title pages) / 2.5 / 3.0 left / 2.5 | not stated / Times New Roman 12 | 2.0 | bottom centre; roman front matter | not stated |
| `ksu` | King Saud University | yes, Deanship guide read | Letter | 2.54 / 2.54 / 3.81 left / 2.54 | not stated / Times New Roman 12 | 2.0, refs single, left-aligned | top right; roman front matter; title page unnumbered | discipline style |
| `qu` | Qatar University | yes, OGS template 2016 read | Letter (template) | 3.175 all | not stated / 12 pt | 2.0 | bottom right; roman front matter; title page unnumbered | APA default |
| `uaeu` | UAE University | NO (templates behind login) | A4 | 2.54 / 2.54 / 3.54 / 2.54 | Simplified Arabic 14 / Times New Roman 12 | 1.5 | bottom centre | APA assumed |
| `cairo` | Cairo University | NO (per-faculty rules; unofficial CUFE template only) | A4 | 2.54 / 2.54 / 3.54 / 2.54 | Simplified Arabic 14 / Times New Roman 12 | 1.5 | bottom centre | faculty decides |
| `mutah` | Mutah University | yes, 2025 guide read | A4 (not stated) | 2.5 / 2.5 / 3.5 / 2.5 | Simplified Arabic 16 / Times New Roman 14 | not stated (1.5), refs single | abjad (AR) or roman (EN) front matter | APA, footnotes for Law/History/Arabic/Sharia |
| `generic-arab` | any Arab university | NO (common practice) | A4 | 2.54 / 2.54 / 3.54 / 2.54 | Simplified Arabic 14 / Times New Roman 12 | 1.5 | bottom centre; abjad / roman | APA 7 |
| `apa7` | APA 7 student paper | yes, via Purdue OWL | Letter | 2.54 all | Times New Roman 12 (or Calibri 11, Arial 11...) | 2.0, left-aligned | top right on every page incl. title page | APA 7 |

"binding" = the wide margin. Presets with `swap_for_arabic` put it on the left for an English thesis and on the right for an Arabic one (`--lang ar`, or an Arabic title in the block). Every preset's `notes` field lists the rules the script cannot apply (committee pages, authorization forms, abstract word limits, Arabic abstract at the end for KSU...): print them to the user. `source_url`, `verified`, `verified_date` and `verification` say what was actually read; an unverified preset is a conservative default to hand to the supervisor, never a claim about the university.

## Cover page

A YAML-ish block at the top of the Markdown (no preset needed, but the preset decides the field order and sizes):

```markdown
---
title: أثر استخدام وسائل التواصل الاجتماعي على التحصيل الأكاديمي
author: محمد أحمد العلي
supervisor: الأستاذ الدكتور خالد محمود
co_supervisor: (optional)
university: الجامعة الأردنية
faculty: كلية الدراسات العليا
department: قسم علم النفس التربوي
degree: الماجستير في علم النفس التربوي
program: علم النفس التربوي
date: تشرين الأول 2026
year: 2026
logo: logo.png            (path relative to the .md; optional)
copyright: © 2026 Name. All Rights Reserved.   (QU)
affiliation / course / instructor               (APA 7 student title page)
---
```

Labels (By / إعداد, Supervisor / إشراف) follow the title's script; the preset may rename them (JUST: Advisor, QU: BY). The "submitted in partial fulfillment" statement comes from the preset's template with `{degree}` / `{program}` / `{faculty}` filled in; give `statement:` in the block to override it. Lines whose placeholder is empty are dropped.

## Front matter, page numbering, TOC

- The cover is page 1 of the front matter but shows no number (`title_page_number: false`). Front matter is numbered in roman numerals (English) or abjad letters أ، ب، ج (Arabic, Word format `arabicAbjad`); the body restarts at 1 in a new section the script inserts automatically.
- The body starts at `<!-- body -->` if present, otherwise at the first `##` heading that is not front matter (abstract, dedication, acknowledgements, abbreviations, declaration, contents, lists). Put `<!-- body -->` before chapter one when in doubt; a warning is printed when no body start is found.
- With a preset, `##` becomes Heading 1 (chapter), `###` Heading 2, `####` Heading 3, so `TOC \o "1-3"` lists them. `chapter_new_page` starts every `##` on a new page.
- `toc: true` inserts a `TOC \o "1-3" \h \z \u` field; `lists: [tables, figures]` insert `TOC \t "Table Caption,1"` / `"Figure Caption,1"` fields over the caption paragraphs (`### جدول 1: ...`, `**Table 1**`, `Figure 2.` ...). python-docx cannot compute page numbers, so the fields hold a placeholder sentence until Word fills them: the file carries `w:updateFields`, so Word asks to update on open; or Ctrl+A, F9; or in Word COM `$d.Fields.Update()` before `ExportAsFixedFormat`. Entries use the TOC 1-3 styles, which the script makes RTL for Arabic theses.
- The APA two-line caption (`**Table 1**` then an italic title) lists only the label line.
- Page-number position: `bottom-center | bottom-right | bottom-left | top-center | top-right | top-left`.

## Margins

- `--margins-cm T,B,L,R` sets asymmetric margins by hand; `--margin-cm X` sets all four (unchanged).
- `--mirror-margins` (or `mirror_margins: true` in a preset) writes Word's mirror-margins setting, so left/right act as inside/outside for two-sided printing. No preset read today asks for it, so none sets it.

## Adding a preset

Copy an entry, read the university's guide, and record `source_url`, `verified: true`, `verified_date` and in `verification` what was and was not found. Never fill a value you did not read: leave the skill default and say so in `notes`. Keys are documented in the `_schema` entry of the JSON.
