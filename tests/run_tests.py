#!/usr/bin/env python3
"""Run every module's selftest and the planted-error regression.

  python -X utf8 tests/run_tests.py          offline (selftests + regression on the fixtures)
  python -X utf8 tests/run_tests.py --live   also checks a real and a fake DOI against Crossref

Exit code 1 when any check fails. Output of failing checks is kept in tests/_out/.
"""

import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "scripts")
FX = os.path.join(ROOT, "tests", "fixtures")
OUT = os.path.join(ROOT, "tests", "_out")
PY = [sys.executable, "-X", "utf8"]

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def run(args, cwd):
    t = time.time()
    p = subprocess.run(PY + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=900)
    return p.returncode, (p.stdout or "") + (p.stderr or ""), round(time.time() - t, 1)


def main():
    live = "--live" in sys.argv
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(FX, OUT)
    sc = os.path.join(S, "scholar.py")
    an = os.path.join(S, "analyze.py")

    # Evidence file from the fixture data, the way a real project produces it.
    ev_lines = []
    for cmd in (["describe", "gpa", "sleep"], ["freq", "gender"], ["corr", "sleep", "gpa"],
                ["regress", "gpa", "sleep", "stress"], ["ttest", "gpa", "--by", "gender"],
                ["anova", "gpa", "--by", "faculty"], ["alpha", "q1", "q2", "q3", "q4"]):
        code, out, _ = run([an, "data.csv"] + cmd, OUT)
        if code:
            print("analyze.py failed:", out[-500:])
            sys.exit(1)
        ev_lines.append(out)
    with open(os.path.join(OUT, "out.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(ev_lines))
    with open(os.path.join(OUT, "template.md"), "w", encoding="utf-8") as f:
        f.write("## Results\nN = [ ], M = [ ], SD = [ ]. r([df]) = [ ], p = [ ] (Table 1).\n")

    checks = [
        ("numbers: clean results PASS", [sc, "numbers", "results_clean.md", "--evidence", "out.txt"], 0, "RESULT: PASS"),
        ("numbers: planted F, p and df FAIL", [sc, "numbers", "results_planted.md", "--evidence", "out.txt"], 1, "3 unsupported"),
        ("numbers: template mode PASS", [sc, "numbers", "template.md"], 0, "RESULT: PASS"),
        ("audit: planted fake citations FAIL", [sc, "audit", "paper.md"], 1, "3 fail"),
        ("audit: clean manuscript PASS", [sc, "audit", "clean.md"], 0, "RESULT: PASS"),
    ]
    for mod in ("autopsy", "similarity", "evidence", "effects", "deliverables", "instruments", "gapmap", "comap",
                "snowball", "journalfit", "qual", "reviews", "analyze_sem"):
        checks.append((f"{mod}.py selftest", [os.path.join(S, mod + ".py"), "selftest"], 0, "RESULT: PASS"))
    if live:
        checks.append(("verify: fake DOI is NOT-FOUND (live)", [sc, "verify", "10.9999/fake.doi.1"], 1, "NOT-FOUND"))
        checks.append(("verify: real DOI found (live)", [sc, "verify", "10.1016/j.chb.2010.03.024"], 0, "found"))

    rows, failed = [], 0
    for name, args, want_code, want_text in checks:
        code, out, secs = run(args, OUT)
        ok = (code == want_code) and (want_text in out)
        if not ok:
            failed += 1
            with open(os.path.join(OUT, name.split(":")[0].replace(" ", "_").replace(".py", "") + ".log"), "w",
                      encoding="utf-8") as f:
                f.write(out)
        rows.append((name, "PASS" if ok else "FAIL", f"{secs}s"))
        print(f"{'PASS' if ok else 'FAIL'}  {name} ({secs}s)")
    print(f"\nRESULT: {'FAIL' if failed else 'PASS'} ({len(rows) - failed}/{len(rows)} checks)"
          + (f"; logs of failing checks in {OUT}" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
