#!/usr/bin/env python3
"""package.py - OSF-ready reproducibility package for a paper project.

build      zip the data, the auto-generated data dictionary, every script under
           analysis/, the evidence output, the source ledger and claims, with a
           README (study, rerun commands, Python + package versions, SHA-256
           checksums) and a CITATION.cff skeleton. Prints the manifest.
dictionary write only the data dictionary (variable, inferred type, range or
           levels, missing count, description column for the agent to fill).
verify     recompute every checksum inside an existing package: RESULT PASS/FAIL.

Never packaged: *.key, .env, .env.*, *.pem and other credential-looking files,
anything whose real path is outside the project folder (symlinks included),
papers/ and fulltext/ (copyrighted PDFs and full text), and any text file that
contains an API-key-looking string (listed in the manifest, never silently).
Data are copied as they are: this tool never edits a data file.

Usage
  python -X utf8 package.py build --project . --data analysis/data.csv --out reproducibility.zip
  python -X utf8 package.py build --project . --title "Sleep and GPA" --extra matrix.md --with-analyzer
  python -X utf8 package.py dictionary --data analysis/data.csv --out data_dictionary.csv
  python -X utf8 package.py verify reproducibility.zip
"""

import argparse
import csv
import datetime as dt
import fnmatch
import hashlib
import io
import json
import os
import platform
import re
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scholar import clean, load_ledger, table, TODAY  # noqa: E402

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

SCRIPT_EXT = {".py", ".r", ".do", ".sps", ".sas", ".jl", ".m", ".sh", ".ps1", ".bat", ".cmd",
              ".ipynb", ".rmd", ".qmd", ".sql"}
SECRET_NAMES = ["*.key", ".env", ".env.*", "*.pem", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*", "*.kdbx",
                "credentials*", "secrets*", "*.secret", "*token*"]
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".idea", ".vscode", "papers", "fulltext"}
SECRET_RE = re.compile(r"(?i)(api[_\-]?key|secret|token|passw(or)?d|bearer)\s*[=:]\s*[\"']?[A-Za-z0-9_\-]{16,}")
MISSING = {"", "NA", "N/A", "NaN", "nan", "NULL", "null", "None"}
TRACKED_PKGS = ("numpy", "scipy", "semopy")
INT_RE = re.compile(r"^[+-]?\d+$")
FLOAT_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


# ---------------------------------------------------------------- helpers

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def inside(project, path):
    """True when the resolved path (symlinks and junctions followed) is inside the project."""
    root = os.path.realpath(project)
    real = os.path.realpath(path)
    return real == root or real.startswith(root.rstrip(os.sep) + os.sep)


def secret_name(name):
    return any(fnmatch.fnmatch(name.lower(), pat) for pat in SECRET_NAMES)


def secret_content(path, limit=2 << 20):
    """(line number, snippet) of the first API-key-looking line in a text file, else None."""
    if os.path.getsize(path) > limit:
        return None
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for n, line in enumerate(f, 1):
                m = SECRET_RE.search(line)
                if m:
                    return n, m.group(1)
    except OSError:
        return None
    return None


def rel(project, path):
    return os.path.relpath(path, project).replace(os.sep, "/")


def same(a, b):
    return bool(a) and bool(b) and os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def package_versions():
    """pip freeze filtered to the packages the analyses depend on; importlib fallback."""
    found = {}
    try:
        out = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, timeout=60)
        for line in out.stdout.splitlines():
            name = re.split(r"[=<>@ ]", line.strip(), maxsplit=1)[0].lower()
            if name in TRACKED_PKGS:
                found[name] = line.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    if not found:
        import importlib.metadata as md
        for name in TRACKED_PKGS:
            try:
                found[name] = f"{name}=={md.version(name)}"
            except md.PackageNotFoundError:
                pass
    return [found.get(n, f"{n}: not installed") for n in TRACKED_PKGS]


# ---------------------------------------------------------------- data dictionary

def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        sys.exit(f"empty data file: {path}")
    header, body = rows[0], rows[1:]
    width = len(header)
    ragged = sum(1 for r in body if len(r) != width)
    body = [r + [""] * (width - len(r)) if len(r) < width else r[:width] for r in body]
    return header, body, ragged


def infer(values):
    """Type, range-or-levels text and distinct count for one column's non-missing values."""
    vals = [v.strip() for v in values]
    present = [v for v in vals if v not in MISSING]
    missing = len(vals) - len(present)
    distinct = sorted(set(present))
    nd = len(distinct)
    if not present:
        return "empty", "", missing, 0
    if all(INT_RE.match(v) for v in present):
        nums = [int(v) for v in present]
        kind = "integer"
        span = f"{min(nums)} to {max(nums)}"
        if nd <= 10:
            span += " (levels: " + ", ".join(str(x) for x in sorted(set(nums))) + ")"
        elif nd == len(present):
            span += " (all values unique: identifier?)"
        return kind, span, missing, nd
    if all(FLOAT_RE.match(v) for v in present):
        nums = [float(v) for v in present]
        return "numeric", f"{min(nums):g} to {max(nums):g}", missing, nd
    if all(DATE_RE.match(v) for v in present):
        return "date", f"{min(present)} to {max(present)}", missing, nd
    if nd <= 12:
        return "categorical", "levels: " + ", ".join(distinct), missing, nd
    return "text", f"{nd} distinct values, e.g. {', '.join(distinct[:3])}", missing, nd


def build_dictionary(header, body, old_desc=None):
    old_desc = old_desc or {}
    rows = []
    for i, var in enumerate(header):
        kind, span, missing, nd = infer([r[i] for r in body])
        rows.append({"variable": var, "type": kind, "range_or_levels": span, "missing": missing,
                     "n_distinct": nd, "description": old_desc.get(var, "")})
    return rows


def read_descriptions(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r.get("variable", ""): r.get("description", "") for r in csv.DictReader(f)}


def dictionary_csv(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["variable", "type", "range_or_levels", "missing", "n_distinct", "description"],
                       lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def dictionary_table(rows):
    return table([[r["variable"], r["type"], r["range_or_levels"], str(r["missing"]), str(r["n_distinct"]),
                   r["description"] or "[fill in]"] for r in rows],
                 ["variable", "type", "range or levels", "missing", "distinct", "description"])


# ---------------------------------------------------------------- rerun commands

HEADER_RE = re.compile(r"^#\s*(\w+)\s+(.*?)(?:\s+by\s+(\S+))?\s*\|\s*file\s+(\S+)\s*\|\s*rows\s+(\d+)\s*$")


def rerun_commands(evidence_path, data_rel):
    """analyze.py writes '# describe gpa sleep | file data.csv | rows 200' before each block."""
    cmds = []
    if not evidence_path or not os.path.exists(evidence_path):
        return cmds
    with open(evidence_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = HEADER_RE.match(line.strip())
            if not m:
                continue
            analysis, vars_, by, _file, rows = m.groups()
            cmd = f"python -X utf8 analysis/analyze.py {data_rel} {analysis} {vars_.strip()}"
            if by:
                cmd += f" --by {by}"
            cmds.append((cmd, f"{rows} rows read"))
    return cmds


# ---------------------------------------------------------------- README / CFF

def readme_text(ctx):
    L = []
    L.append(f"# Reproducibility package: {ctx['title']}")
    L.append("")
    L.append(f"Generated {TODAY} by package.py (research-paper-assistant skill). "
             "Lines in [square brackets] are placeholders for the authors to fill before upload.")
    L.append("")
    L.append("## Study")
    L.append("")
    L.append(f"- Title: {ctx['title']}{ctx['title_note']}")
    L.append("- Authors: [family, given; ORCID]")
    L.append("- Abstract: [one paragraph]")
    L.append("- OSF project: [https://osf.io/xxxxx]")
    L.append("- Preregistration: [link or 'none']")
    L.append("- Ethics approval: [committee, reference number]")
    L.append("")
    L.append("## Contents")
    L.append("")
    L.append(table([[p, what] for p, what in ctx["contents"]], ["file", "what it is"]))
    L.append("")
    if ctx["data"]:
        d = ctx["data"]
        L.append("## Data")
        L.append("")
        L.append(f"- File: `{d['rel']}`: {d['rows']} rows, {d['cols']} columns, copied unchanged.")
        L.append(f"- Missing values are any of: {', '.join(sorted(m for m in MISSING if m)) or ''} or an empty cell.")
        if d["ragged"]:
            L.append(f"- WARNING: {d['ragged']} row(s) have a different number of cells than the header: check the file.")
        L.append("- Data dictionary (`data_dictionary.csv`; types and ranges are inferred from the values, "
                 "the description column is written by the authors):")
        L.append("")
        L.append(dictionary_table(d["dictionary"]))
        L.append("")
    L.append("## How to rerun")
    L.append("")
    L.append("Environment used:")
    L.append("")
    L.append(f"- Python {platform.python_version()} on {platform.system()} {platform.release()}")
    for v in ctx["versions"]:
        L.append(f"- {v}")
    L.append("")
    L.append("Commands, run from the folder this package is unzipped into:")
    L.append("")
    if ctx["commands"]:
        for cmd, note in ctx["commands"]:
            L.append(f"    {cmd}    # {note}")
        L.append("")
        L.append("Flags that do not appear in the evidence header (for example --spearman, --diagnostics, "
                 "--composite, --range) are not recorded: confirm them against the output block. "
                 "Each command appends to `analysis/output.txt`; compare with the packaged copy.")
    else:
        L.append("    [no analyze.py headers found in the evidence file: list each command by hand]")
    if ctx["scripts"]:
        L.append("")
        L.append("Other scripts in `analysis/` (arguments to confirm):")
        L.append("")
        for s in ctx["scripts"]:
            L.append(f"    {s}")
    if ctx["analyzer_note"]:
        L.append("")
        L.append(ctx["analyzer_note"])
    L.append("")
    L.append("## Evidence")
    L.append("")
    if ctx["evidence_rel"]:
        L.append(f"`{ctx['evidence_rel']}` holds every statistic reported in the manuscript as `key.label = value` "
                 "lines; `# APA:` lines are the sentences used. The manuscript was checked against it with "
                 "`scholar.py numbers`.")
    else:
        L.append("[no evidence file packaged: the manuscript's numbers have no analysis output behind them]")
    L.append("")
    L.append("## Sources")
    L.append("")
    if ctx["ledger_n"] is not None:
        L.append(f"- `{ctx['ledger_rel']}`: {ctx['ledger_n']} verified sources (DOI or ISBN resolved, retraction status "
                 "checked at the date in each entry).")
    else:
        L.append("- [no source ledger packaged]")
    if ctx["claims_n"] is not None:
        L.append(f"- `{ctx['claims_rel']}`: {ctx['claims_n']} claim(s) with verbatim quotes and page numbers.")
    L.append("")
    L.append("## Checksums (SHA-256)")
    L.append("")
    L.append("Full list in `checksums.sha256` (which also covers this README). Verify with "
             "`python -X utf8 package.py verify <zip>` or `sha256sum -c checksums.sha256`.")
    L.append("")
    L.append(table([[p, h] for p, h in ctx["checksums"]], ["file", "sha256"]))
    L.append("")
    L.append("## Not included")
    L.append("")
    if ctx["excluded"]:
        for p, why in ctx["excluded"]:
            L.append(f"- `{p}`: {why}")
    else:
        L.append("- nothing was excluded")
    L.append("- `papers/` and `fulltext/` are never packaged (copyrighted PDFs and full text).")
    L.append("")
    L.append("## License")
    L.append("")
    L.append("[CC-BY-4.0 for data and text, MIT for code, or the license your institution requires]")
    L.append("")
    return "\n".join(L)


def cff_text(title):
    safe = title.replace('"', "'")
    return "\n".join([
        "cff-version: 1.2.0",
        'message: "If you use these data or this code, please cite them as below."',
        "type: dataset",
        f'title: "{safe}"',
        "authors:",
        '  - family-names: "[Family]"',
        '    given-names: "[Given]"',
        '    orcid: "https://orcid.org/[0000-0000-0000-0000]"',
        '    affiliation: "[University, Department]"',
        f'date-released: "{TODAY}"',
        'version: "1.0.0"',
        'license: "[CC-BY-4.0]"',
        'repository: "[https://osf.io/xxxxx]"',
        'doi: "[10.17605/OSF.IO/XXXXX once OSF mints it]"',
        "keywords:",
        '  - "[keyword 1]"',
        '  - "[keyword 2]"',
        'abstract: "[one paragraph]"',
        "",
    ])


# ---------------------------------------------------------------- collect

def detect_title(project, explicit):
    if explicit:
        return explicit, ""
    skip = {"readme.md", "matrix.md", "shortlist.md", "watch_log.md", "handoff.md"}
    for name in sorted(os.listdir(project)):
        if not name.lower().endswith(".md") or name.lower() in skip:
            continue
        try:
            with open(os.path.join(project, name), encoding="utf-8", errors="replace") as f:
                for line in f:
                    m = re.match(r"^#\s+(.+?)\s*$", line)
                    if m:
                        return clean(m.group(1)), f" (auto-detected from {name}: confirm)"
        except OSError:
            continue
    return "[study title]", ""


def collect(a):
    project = os.path.abspath(a.project)
    if not os.path.isdir(project):
        sys.exit(f"project folder not found: {project}")
    files = []       # (abs path, rel path, what)
    excluded = []    # (rel or given path, reason)
    out_abs = os.path.abspath(os.path.join(project, a.out) if not os.path.isabs(a.out) else a.out)

    def consider(path, what, requested=False):
        name = os.path.basename(path)
        if not os.path.isfile(path):
            excluded.append((path if requested else rel(project, path), "not found"))
            return False
        if same(path, out_abs):
            return False
        if not inside(project, path):
            excluded.append((path, "outside the project folder (real path): refused"))
            return False
        r = rel(project, path)
        if secret_name(name):
            excluded.append((r, "credential-looking file name"))
            return False
        hit = secret_content(path)
        if hit:
            excluded.append((r, f"line {hit[0]} contains an API-key-looking '{hit[1]}' value: remove it, then rebuild"))
            return False
        if any(f[1] == r for f in files):
            return True
        files.append((path, r, what))
        return True

    # data
    data = None
    data_path = os.path.join(project, a.data) if a.data else None
    if not a.data:
        cand = os.path.join(project, "analysis", "data.csv")
        if os.path.exists(cand):
            data_path = cand
        else:
            adir = os.path.join(project, "analysis")
            csvs = sorted(f for f in os.listdir(adir) if f.lower().endswith(".csv")) if os.path.isdir(adir) else []
            data_path = os.path.join(adir, csvs[0]) if csvs else None
    if data_path and consider(data_path, "the data the analyses ran on (unchanged)", requested=bool(a.data)):
        header, body, ragged = read_csv(data_path)
        old = read_descriptions(os.path.join(project, "data_dictionary.csv"))
        data = {"rel": rel(project, data_path), "rows": len(body), "cols": len(header), "ragged": ragged,
                "dictionary": build_dictionary(header, body, old)}
    elif a.data:
        why = excluded[-1][1] if excluded else "not found"
        sys.exit(f"data file not usable: {a.data}: {why}")

    # analysis/: scripts + evidence
    adir = os.path.join(project, "analysis")
    ev = os.path.join(project, a.evidence)
    scripts, others = [], []
    for n in sorted(os.listdir(project)):
        if secret_name(n) and os.path.isfile(os.path.join(project, n)):
            excluded.append((n, "credential-looking file name: never packaged"))
    if os.path.isdir(adir):
        for root, dirs, names in os.walk(adir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for n in sorted(names):
                p = os.path.join(root, n)
                if secret_name(n):
                    excluded.append((rel(project, p), "credential-looking file name: never packaged"))
                elif os.path.splitext(n)[1].lower() in SCRIPT_EXT:
                    if consider(p, "analysis script"):
                        scripts.append(rel(project, p))
                elif not same(p, data_path) and not same(p, ev):
                    others.append(rel(project, p))
    evidence_rel = None
    if os.path.exists(ev):
        if consider(ev, "evidence: every statistic as key.label = value"):
            evidence_rel = rel(project, ev)
    else:
        excluded.append((a.evidence, "not found: no evidence file"))
    for o in others:
        excluded.append((o, "in analysis/ but not a script, data or evidence file: add with --extra if needed"))

    # ledger, claims, extras
    ledger_n = claims_n = None
    ledger_rel = claims_rel = None
    lp = os.path.join(project, a.ledger)
    if os.path.exists(lp) and consider(lp, "source ledger (verified references)"):
        ledger_n, ledger_rel = len(load_ledger(lp)), rel(project, lp)
    elif not os.path.exists(lp):
        excluded.append((a.ledger, "not found: no source ledger"))
    cp = os.path.join(project, a.claims)
    if os.path.exists(cp) and consider(cp, "claims with verbatim quotes"):
        claims_n, claims_rel = len(load_ledger(cp)), rel(project, cp)
    refused_extra = False
    for x in a.extra:
        p = x if os.path.isabs(x) else os.path.join(project, x)
        if not consider(p, "added with --extra", requested=True):
            refused_extra = True

    analyzer_note = ""
    if a.with_analyzer:
        src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyze.py")
        if os.path.exists(src):
            files.append((src, "analysis/analyze.py", "the skill's analyze.py (copied in with --with-analyzer)"))
            analyzer_note = ("`analysis/analyze.py` is the research-paper-assistant tool that produced the evidence "
                             f"(sha256 {sha256(src)[:12]}...), copied in at build time.")
        else:
            excluded.append(("analyze.py", "--with-analyzer: not found next to package.py"))
    else:
        analyzer_note = ("`analyze.py` (the tool that produced the evidence) is not part of the project folder and was "
                         "not packaged. Rebuild with `--with-analyzer` to include it, or install the "
                         "research-paper-assistant skill.")

    title, title_note = detect_title(project, a.title)
    return {"project": project, "files": files, "excluded": excluded, "data": data, "scripts": scripts,
            "evidence_rel": evidence_rel, "ledger_n": ledger_n, "ledger_rel": ledger_rel, "claims_n": claims_n,
            "claims_rel": claims_rel, "title": title, "title_note": title_note, "out": out_abs,
            "analyzer_note": analyzer_note, "refused_extra": refused_extra}


# ---------------------------------------------------------------- commands

def cmd_build(a):
    ctx = collect(a)
    ctx["versions"] = package_versions()
    data_rel = ctx["data"]["rel"] if ctx["data"] else "[data file]"
    ev_abs = os.path.join(ctx["project"], ctx["evidence_rel"]) if ctx["evidence_rel"] else None
    ctx["commands"] = rerun_commands(ev_abs, data_rel)
    ctx["scripts"] = [f"python -X utf8 {s}" if s.endswith(".py") else s for s in ctx["scripts"]
                      if not s.endswith("analyze.py")]

    generated = {}  # rel -> bytes
    if ctx["data"]:
        dict_text = dictionary_csv(ctx["data"]["dictionary"])
        generated["data_dictionary.csv"] = dict_text.encode("utf-8")
        with open(os.path.join(ctx["project"], "data_dictionary.csv"), "w", encoding="utf-8", newline="") as f:
            f.write(dict_text)   # the agent fills 'description' here; a rebuild keeps those descriptions
    generated["CITATION.cff"] = cff_text(ctx["title"]).encode("utf-8")

    checks = [(r, sha256(p)) for p, r, _ in ctx["files"]] + [(r, sha256_bytes(b)) for r, b in generated.items()]
    checks.sort()
    ctx["checksums"] = checks
    ctx["contents"] = [("README.md", "this file")] + [(r, w) for _, r, w in ctx["files"]] + \
                      [("data_dictionary.csv", "variables, inferred types, ranges, missing counts, descriptions")
                       if ctx["data"] else None, ("CITATION.cff", "citation metadata skeleton (fill the brackets)"),
                       ("checksums.sha256", "SHA-256 of every file, sha256sum format")]
    ctx["contents"] = [c for c in ctx["contents"] if c]
    readme = readme_text(ctx).encode("utf-8")
    all_checks = checks + [("README.md", sha256_bytes(readme))]
    sums = "".join(f"{h}  {r}\n" for r, h in sorted(all_checks)).encode("utf-8")

    os.makedirs(os.path.dirname(ctx["out"]) or ".", exist_ok=True)
    with zipfile.ZipFile(ctx["out"], "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.md", readme)
        for r, b in generated.items():
            z.writestr(r, b)
        for p, r, _ in ctx["files"]:
            z.write(p, r)
        z.writestr("checksums.sha256", sums)

    size = os.path.getsize(ctx["out"])
    n_files = len(ctx["files"]) + len(generated) + 2
    d = ctx["data"]
    print(f"package: {ctx['out']} | {n_files} files | {size / 1024:.1f} KB | "
          f"data: {d['rows']} rows x {d['cols']} cols | " if d else
          f"package: {ctx['out']} | {n_files} files | {size / 1024:.1f} KB | data: none | ", end="")
    print(f"scripts: {len(ctx['scripts'])} | rerun commands: {len(ctx['commands'])} | {TODAY}")
    rows = [[r, str(os.path.getsize(p)), sha256(p)[:12], "project"] for p, r, _ in ctx["files"]]
    rows += [[r, str(len(b)), sha256_bytes(b)[:12], "generated"] for r, b in generated.items()]
    rows += [["README.md", str(len(readme)), sha256_bytes(readme)[:12], "generated"],
             ["checksums.sha256", str(len(sums)), sha256_bytes(sums)[:12], "generated"]]
    print(table(sorted(rows), ["file in zip", "bytes", "sha256", "origin"]))
    if ctx["excluded"]:
        print("not packaged:")
        print(table([[p, why] for p, why in ctx["excluded"]], ["path", "reason"]))
    if d:
        empty = sum(1 for r in d["dictionary"] if not r["description"])
        print(f"data dictionary: {len(d['dictionary'])} variables, {empty} without a description. Fill the "
              f"'description' column in {os.path.join(ctx['project'], 'data_dictionary.csv')} and rebuild.")
    print("README placeholders in [brackets] (authors, abstract, OSF link, ethics, license) must be filled before upload.")
    if ctx["refused_extra"]:
        print("RESULT: FAIL (a requested --extra file was refused or missing; see 'not packaged')")
        return 1
    return 0


def cmd_dictionary(a):
    if not os.path.exists(a.data):
        sys.exit(f"data file not found: {a.data}")
    header, body, ragged = read_csv(a.data)
    rows = build_dictionary(header, body, read_descriptions(a.out) if a.out else {})
    print(f"data dictionary: {a.data} | {len(body)} rows x {len(header)} columns | ragged rows: {ragged} | {TODAY}")
    print(dictionary_table(rows))
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="") as f:
            f.write(dictionary_csv(rows))
        print(f"saved to {os.path.abspath(a.out)} (existing descriptions kept)")
    print("Types, ranges and levels are inferred from the values: confirm scale types (nominal, ordinal, "
          "interval) and write the description column by hand.")
    return 0


def cmd_verify(a):
    if not zipfile.is_zipfile(a.zip):
        sys.exit(f"not a zip file: {a.zip}")
    bad, missing, unlisted = [], [], []
    with zipfile.ZipFile(a.zip) as z:
        names = set(z.namelist())
        if "checksums.sha256" not in names:
            print(f"verify: {a.zip} | no checksums.sha256 inside")
            print("RESULT: FAIL (no checksum list: not built by package.py, or tampered)")
            return 1
        listed = {}
        for line in z.read("checksums.sha256").decode("utf-8").splitlines():
            m = re.match(r"^([0-9a-f]{64})\s+\*?(.+)$", line.strip())
            if m:
                listed[m.group(2)] = m.group(1)
        for r, h in listed.items():
            if r not in names:
                missing.append(r)
            elif sha256_bytes(z.read(r)) != h:
                bad.append(r)
        unlisted = sorted(n for n in names - {"checksums.sha256"} - set(listed) if not n.endswith("/"))
    print(f"verify: {a.zip} | {len(listed)} listed files | {len(bad)} changed | {len(missing)} missing | "
          f"{len(unlisted)} unlisted | {TODAY}")
    rows = [[r, "CHANGED: content differs from its checksum"] for r in bad] + \
           [[r, "MISSING: listed but not in the zip"] for r in missing] + \
           [[r, "UNLISTED: in the zip but not in checksums.sha256"] for r in unlisted]
    if rows:
        print(table(rows, ["file", "problem"]))
    if bad or missing or unlisted:
        print("RESULT: FAIL (the package differs from what package.py built; rebuild or investigate)")
        return 1
    print("RESULT: PASS (every file matches checksums.sha256; the README placeholders were not checked)")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="build the reproducibility zip and print its manifest",
                       epilog="example: python -X utf8 package.py build --project . --data analysis/data.csv --out reproducibility.zip")
    b.add_argument("--project", default=".", help="the paper folder (only files inside it are packaged)")
    b.add_argument("--data", help="CSV the analyses ran on (default: analysis/data.csv or the first CSV in analysis/)")
    b.add_argument("--evidence", default="analysis/output.txt")
    b.add_argument("--ledger", default="sources.jsonl")
    b.add_argument("--claims", default="claims.jsonl")
    b.add_argument("--out", default="reproducibility.zip", help="zip path (relative to the project)")
    b.add_argument("--title", help="study title for the README and CITATION.cff")
    b.add_argument("--extra", action="append", default=[], help="another project file to include (repeatable)")
    b.add_argument("--with-analyzer", action="store_true", help="copy the skill's analyze.py into analysis/")

    d = sub.add_parser("dictionary", help="data dictionary only",
                       epilog="example: python -X utf8 package.py dictionary --data analysis/data.csv --out data_dictionary.csv")
    d.add_argument("--data", required=True)
    d.add_argument("--out", help="CSV to write (existing 'description' values are kept)")

    v = sub.add_parser("verify", help="recompute the checksums inside a package",
                       epilog="example: python -X utf8 package.py verify reproducibility.zip")
    v.add_argument("zip")

    a = p.parse_args()
    sys.exit(globals()["cmd_" + a.cmd](a) or 0)


if __name__ == "__main__":
    main()
