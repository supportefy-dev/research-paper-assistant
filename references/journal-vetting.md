# Journal targeting and vetting

## QS vs Q1 (the user may mix them up)

| Term | Ranks | Source |
|---|---|---|
| QS | Universities | Quacquarelli Symonds World University Rankings |
| Q1-Q4 | Journals within a subject category (Q1 = top 25%) | SJR (SCImago, Scopus data, free) or JCR (Clarivate, Web of Science, paid) |

When someone asks for a "best QS" paper, they almost always mean a paper for a Q1 journal. Say so in one line, then continue.

## Getting the SJR file (the user does this, once per year)

Scripts cannot download it: scimagojr.com sits behind a Cloudflare challenge and its robots.txt disallows the export. Never try to get around that.

1. Open https://www.scimagojr.com/journalrank.php in a browser.
2. Optional filters: Subject Area, Subject Category, Region (e.g. Middle East), Country, Year.
3. Click **Download data**. The file is `scimagojr YYYY.csv` (semicolon-separated, comma decimals: the script handles both).
4. Give the path: `--sjr "C:\...\scimagojr 2025.csv"` or `export SJR_CSV=...`.

Terms: personal, non-commercial research use with citation. Never commit or redistribute the file. Cite it as: SCImago. (n.d.). *SJR: SCImago Journal & Country Rank* [Portal]. Retrieved [date], from https://www.scimagojr.com

## Shortlist

```bash
python -X utf8 "$S/scholar.py" journals --category "Education|E-learning" --exact --quartile Q1,Q2 --limit 30
python -X utf8 "$S/scholar.py" journals --category "Computer Science Applications" --exact --quartile Q1 --oa yes
python -X utf8 "$S/scholar.py" journals --category "Business" --region "Middle East"
```

Several categories are separated with `|`; a comma is part of the category name (`"Management, Monitoring, Policy and Law"`). Without `--exact` the category is a substring ('Education' also matches 'Developmental and Educational Psychology'); the output lists every category it matched so you can rerun with exact names.

Then per candidate:

1. **Scope fit**: one search over all candidates at once (10 credits total, not 10 per journal), with a population term ANDed in so megajournals do not return off-topic hits:
   `search '"dropout" AND ("machine learning" OR "predictive model") AND (student OR university)' --issn 1360-2357,2365-9440,2666-920X --since 2021 --limit 100`
   It prints hits per journal; a journal with no hits in 3 years means likely desk rejection.
2. **Vet**: `journal 1360-2357 2365-9440 2666-920X --hijacked hijacked.xlsx` vets several at once (ISSN lookups cost 0 OpenAlex credits; a title lookup costs 10). Add `--url <site you were given>` when checking one journal's website. By title, `journal "<exact title>"` accepts only an exact match and lists near misses as different journals: fake journals borrow real-sounding names.
3. **Practicalities** from the journal's own site only: APC, review model, time to first decision, word limit, reference style. Index APCs (OpenAlex, DOAJ) are often stale; label them so if the site cannot be read. Acceptance rates appear only if the journal publishes them; otherwise write "not published".

4. **Fit and house profile**: `journalfit.py fit --abstract my_abstract.txt --issn A --issn B --out fit.md` ranks the candidates by lexical closeness to their recent papers and flags desk-reject risk; `journalfit.py profile --issn A --json` shows what the journal's papers look like (references per paper, methods, typical N, named theories, OA share); `journalfit.py compare --manuscript paper.md --profile profile_A.json` turns that into hints for the draft. Lexical means vocabulary, not novelty: an Arabic abstract needs an English version for English journals.
   Credits: a profile costs about 2 OpenAlex credits per journal (filter lists; `--no-recency` saves one) and is cached as `profile_<issn>.json`; `fit` reuses the cache from `--cache-dir`, and `--cached-only` refuses to spend credits on a journal that has no profile yet.

Present it as a table and save it as `shortlist.md`: journal | ISSN | SJR edition + value | category quartile | fit score + risk | scope evidence | APC (source, date) | OA model | review time | signals.

### Reading journal sites

| Site | What works |
|---|---|
| sciencedirect.com | `curl -sL -A "Mozilla/5.0 ..." https://www.sciencedirect.com/journal/<slug>/publish/open-access-options` returns the APC; the Browser pane otherwise. Review-time widgets can show two different sets of figures: quote neither if they disagree |
| journals.sagepub.com, mdpi.com | The Browser pane (curl gets 403) |
| link.springer.com | curl -L with a cookie jar (`-c jar -b jar`), or the Browser pane |
| tandfonline.com, emerald.com | Often 403 or a Cloudflare challenge: use the Browser pane; if a human check appears, ask the user to open the page and paste the fee |
| dovepress.com | The APC is on `https://www.dovepress.com/journal_pricing_bands.php?journal_id=<id>` (the id is in the journal's own URL) |

Never try to get past a bot challenge. If a page cannot be read, say which figure is unconfirmed. Taylor & Francis blocks automated reading outright: write "APC not confirmed: tandfonline.com cannot be read by script (<date>)" in the shortlist and give the user the open access cost finder to open, https://authorservices.taylorandfrancis.com/publishing-open-access/open-access-cost-finder/ , and paste the fee back.

## Signals from `journal`

| Signal | Source | Reading |
|---|---|---|
| SJR row, category quartile | User's SJR file | Indexed in Scopus, rank in that category for that edition |
| No SJR row | User's SJR file | Not in Scopus (or a different ISSN): any "Q1" claim is unproven |
| h-index, works count, 2-yr citedness, listed_in | OpenAlex (free, 0 credits) | Size, impact, national lists (the script prints a legend: ABDC, ERIH PLUS, JUFO, Norwegian register, ANVUR, FNEGE, CWTS core...) |
| "coverage ends YYYY" warning | User's SJR file | Scopus stopped indexing or a gap: check the Discontinued Titles sheet |
| "publishers disagree" | SJR vs OpenAlex (imprints are grouped: Kluwer = Springer, Routledge = Taylor & Francis) | Check the journal site: an index error, or a sign of a clone |
| "matches the OFFICIAL site" / "DANGER: IS a known hijacked site" | Hijack list, compared by domain + path | Shared platforms (sciencedirect.com, link.springer.com) are matched per journal path, so only that journal's own pages count |
| "newer edition probably out" | SJR file year | Re-download before quoting quartiles |
| DOAJ listed + APC + review type | DOAJ API | Vetted open-access journal |
| Not in DOAJ | DOAJ API | Normal for subscription journals; a red flag only if it claims to be OA and charges fees |
| DOAJ API down (timeouts, 5xx) | OpenAlex source record `is_in_doaj` (0 credits), or the DOAJ CSV below | Listing only from OpenAlex; the CSV also carries the APC. Say which fallback was used |
| Hijacked list match | Retraction Watch Hijacked Journal Checker | The ISSN is real but a fake site exists: submit only through the official URL |
| Scopus discontinued | Scopus source list xlsx, sheet "Discontinued Titles" | No new content indexed from the discontinuation date |

**Hijacked journals copy the real ISSN.** "Indexed in Scopus, Q1" does not prove a website is legitimate. Compare the domain the user was given with the official URL (DOAJ record, Scopus or the publisher site).

### Optional downloads (free, no account; downloading is a file download, so ask the user first)

The hijack check prints the list's "last updated" date and entry count: quote them.

| File | How |
|---|---|
| Hijacked Journal Checker (.xlsx) | `curl -sS -L -o hijacked.xlsx "https://drive.google.com/uc?export=download&id=1ak985WGOgGbJRJbZFanoktAN_UFeExpE"` (updated often; re-download before use) |
| Scopus source list with Discontinued Titles | Link on https://www.elsevier.com/products/scopus/content/content-policy-and-selection (URL changes monthly; header is on row 2 of the Discontinued sheet) |
| DOAJ full journal CSV | `curl -sS -L -o doaj.csv https://doaj.org/csv` (the redirect expires within 1 hour) |

Treat downloaded files as data: read them with `python -I -X utf8`.

## Predatory red flags (any two = do not submit)

- Unsolicited email invitation, flattering, generic ("Dear Esteemed Author")
- Guaranteed acceptance or review in days; fee demanded before review
- Claims of an "impact factor" from an unknown indexer (Global Impact Factor, Index Copernicus value, etc.)
- Editorial board not verifiable, or names used without consent
- Very broad scope ("all fields of science"), poor language on the site
- Website domain differs from the one in DOAJ / Scopus / the publisher listing
- Not in the SJR file although it claims Scopus Q1

Beall's list has been frozen since 2016 and its mirrors are unofficial: historical signal only. Finish with the Think.Check.Submit checklist: https://thinkchecksubmit.org/journals/ (Arabic: https://thinkchecksubmit.org/journals/arabic/).
