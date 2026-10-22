# Security Policy

Research Paper Assistant is a Claude Code skill (Markdown instructions plus 18 Python command-line scripts) that reads and writes files in the research project folder it is run in: `sources.jsonl`, `claims.jsonl`, `fulltext/`, `papers/`, `analysis/` and the manuscript. It calls the free public APIs listed under [Network calls](#network-calls) and nothing else: no server, no account, no telemetry. The scripts talk to each other only through the files in the project folder.

## Supported Versions

The latest release is supported. Older releases receive security fixes only for critical vulnerabilities.

| Version | Supported |
|---------|-----------|
| 1.0.x | Yes |
| < 1.0 | No |

## Reporting a Vulnerability

Please report vulnerabilities privately by email to info@supportefy.com. Do not open a public issue for a vulnerability that could expose an API key, a user's email address, or unpublished research or participant data.

Include a description of the impact, steps to reproduce, the affected operating system, Python version and Research Paper Assistant version (`git log -1 --oneline`), and a suggested mitigation if you have one. Do not include real research data, participant data, access tokens such as an OpenAlex key, or personal information in the report.

Do not publish exploit details before a fix or mitigation is available.

## What Research Paper Assistant does with secrets

`scripts/scholar.py` reads the OpenAlex API key from `OPENALEX_API_KEY` or from `~/.config/research-paper-assistant/openalex.key` (a folder outside every repo and project), and an optional Semantic Scholar key from `S2_API_KEY`. The OpenAlex key is sent only to `api.openalex.org` as the `api_key` query parameter and the Semantic Scholar key only to `api.semanticscholar.org` as the `x-api-key` header; neither is printed (error messages carry the URL without its query string, and a refused key prints the key file's path, not the key) or written into a project folder. `package.py build` refuses `*.key`, `.env`, `.env.*`, `*.pem` and other credential-looking files, anything whose real path is outside the project, `papers/` and `fulltext/`, and any text file with an API-key-looking line, and lists each refusal in its manifest.

`RESEARCH_MAILTO` (your email) is used only when you set it: as Crossref's `mailto` parameter, as Unpaywall's `email` parameter, and inside the User-Agent header (`research-paper-assistant/1.0 (mailto:...)`) of the requests the scripts make. When it is unset, no request carries your email and Unpaywall is skipped. Nothing else about the user or the project is sent anywhere except the search terms, citation strings, DOIs, ISBNs, ISSNs and OpenAlex IDs each command needs.

## Network calls

| Host | Script and command | What is sent |
|---|---|---|
| `api.openalex.org` | `scholar.py` (search, add, verify, abstract, journal), `gapmap.py run`, `comap.py build`, `snowball.py run`, `evidence.py fetch`, `instruments.py find`, `journalfit.py profile` and `fit`, `watch.py run` | Search terms, DOIs, ISSNs, OpenAlex IDs; the API key when set |
| `api.crossref.org`, `doi.org` | `scholar.py` (search, add, verify, fix, cite, abstract), `instruments.py protocol` | DOIs, citation strings, journal / volume / page lookups; `mailto` when `RESEARCH_MAILTO` is set |
| `api.semanticscholar.org` | `scholar.py` (search with `--source both`, and the abstract fallback in abstract, add and verify) | Search terms, DOIs; `S2_API_KEY` when set |
| `www.ebi.ac.uk` (Europe PMC) | `scholar.py` (the abstract fallback in abstract, add and verify), `evidence.py fetch` | DOIs, PMC IDs |
| `openlibrary.org` | `scholar.py book`, and ISBN lookups in add and verify | ISBN, or title and author |
| `doaj.org` | `scholar.py journal` | ISSN |
| `api.unpaywall.org` | `evidence.py fetch`, only with `RESEARCH_MAILTO` or `--email` | DOI and your email |
| `arxiv.org` and the open-access PDF hosts that Unpaywall or OpenAlex list | `evidence.py fetch` | A PDF request; one retry with a browser User-Agent on HTTP 403, then the site is left alone |
| `api2.openreview.net`, `api.elifesciences.org`, `f1000research.com`, `peerj.com` | `reviews.py pull` | Search terms (PeerJ blocks scripts and is reported as blocked) |

No network call is made by `analyze.py`, `analyze_sem.py`, `autopsy.py`, `build_docx.py`, `deliverables.py`, `effects.py`, `package.py`, `qual.py` (whisper.cpp and ffmpeg run locally) or `similarity.py`, by `scholar.py list`, `refs`, `audit`, `numbers` and `journals`, or by any selftest. `watch.py schedule` prints a Task Scheduler command and never creates it. The SJR file and the Retraction Watch hijacked-journal list are downloaded by you in a browser; no script fetches them.

## Sensitive Files - Do Not Commit

```text
.env
.env.*
*.key (openalex.key belongs in ~/.config/research-paper-assistant/, never in a repo)
secrets.*
private keys
API tokens
database dumps
production credentials
a research project's own files: sources.jsonl, claims.jsonl, fulltext/, papers/, analysis/
```

## Project Folder Security

A research project folder may contain unpublished data, interview audio and transcripts, participant responses and copyrighted full texts. Treat it as sensitive:

```text
do not check it into version control (the skill's .gitignore excludes root-level project files)
do not share its contents publicly
set restrictive filesystem permissions on it
exclude it from backup tools that sync to public cloud storage without encryption
```

## Package Safety

Release archives should not include:

```text
.git/
__pycache__/
*.pyc
.env
.env.*
*.key
tests/_out/
sources.jsonl, claims.jsonl, fulltext/, papers/, analysis/ at the repo root
```

## Agent Safety

The scripts run with the same filesystem permissions as the user who starts them:

```text
do not run the scripts as root or administrator
agents using Research Paper Assistant must not paste an API key or an email address into project files, issues or pull requests
agents must not bypass a paywall, a login or a bot challenge to get a full text or a journal list
agents must not set RESEARCH_MAILTO or request an OpenAlex key without the user's explicit OK and the user's own email
agents must not run destructive commands without explicit approval
```

## Dependency Safety

Research Paper Assistant's dependencies are listed in `requirements.txt`. Pin versions in production installs and audit with:

```bash
pip-audit -r requirements.txt
```
