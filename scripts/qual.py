#!/usr/bin/env python3
"""qual.py - qualitative pipeline: interview audio -> timestamped transcript -> codebook
-> coded segments -> inter-coder agreement -> themes report with quotes.

The script does the mechanical, checkable work. Reading the interviews, deciding the codes
and interpreting the themes is the researcher's (or the agent's) job. Every quote the script
prints is verbatim from a transcript and carries a [transcript mm:ss] stamp. The script never
invents a quote, a code or a number.

Commands
  transcribe  audio -> transcripts/<name>.json + .md with [mm:ss] stamps (local whisper.cpp, free)
  codebook    init / add / list  (codebook.json: code, definition, inclusion, exclusion, example)
  code        add a coding (transcript, window, code, coder) -> coding.jsonl, quote stored verbatim
  agreement   Cohen's kappa + percent agreement between two coders on segments both coded
  themes      counts per code and transcript, co-occurrence, best quotes, saturation curve -> markdown
  quote       retrieve quotes for one code, with stamps, for the write-up
  selftest    runs the whole pipeline on an Arabic fake transcript with planted errors

Transcription needs whisper.cpp (whisper-cli on PATH, or env WHISPER_CLI = full path to the
binary) and a ggml model in WHISPER_MODEL_DIR (default ~/.cache/whisper; Arabic needs the
multilingual ggml-large-v3-turbo.bin). ffmpeg, if installed, converts the audio to 16 kHz mono
WAV first (needed for m4a). All free and local: no audio leaves the machine.

Examples
  python -X utf8 qual.py transcribe interviews/p01.m4a --lang ar --out transcripts/ --speakers 2
  python -X utf8 qual.py codebook init --out codebook.json
  python -X utf8 qual.py codebook add --code trust --definition "..." --inclusion "..." --exclusion "..."
  python -X utf8 qual.py code add --transcript p01 --start 03:12 --end 03:40 --code trust --coder A
  python -X utf8 qual.py agreement coding.jsonl --coders A B --evidence analysis/output.txt
  python -X utf8 qual.py themes coding.jsonl --codebook codebook.json --out themes.md
  python -X utf8 qual.py quote --code trust --n 5
  python -X utf8 qual.py selftest
"""

import argparse
import datetime as dt
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scholar import table, short, TODAY, ARABIC_RE  # noqa: E402

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

def _model_dir():
    """WHISPER_MODEL_DIR, else the first cache folder that already holds a ggml model."""
    home = os.path.expanduser("~")
    cands = [os.environ.get("WHISPER_MODEL_DIR", ""),
             os.path.join(home, ".cache", "whisper"),
             os.path.join(home, ".cache", "whisper.cpp"),
             os.path.join(home, ".cache", "hyperframes", "whisper", "models")]
    for d in cands:
        if d and glob.glob(os.path.join(d, "ggml-*.bin")):
            return d
    return cands[0] or cands[1]


MODEL_DIR = _model_dir()
MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/"
DEFAULT_MODEL = {"ar": "ggml-large-v3-turbo.bin", "en": "ggml-large-v3-turbo.bin"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".mp4", ".aac", ".wma", ".opus", ".webm"}
# Landis and Koch style bands for kappa (lower bound, name); the agent cites the source through the ledger.
KAPPA_BANDS = [(0.81, "almost perfect"), (0.61, "substantial"), (0.41, "moderate"), (0.21, "fair"), (0.0, "slight")]
# A coding window covers a segment when it overlaps at least this much (seconds) or half the segment:
# a boundary typed as 00:06 must not drag in 0.2 s of the segment that ends at 6.2.
MIN_OVERLAP = 1.0


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------- time helpers

def parse_ts(s):
    """'mm:ss', 'mm:ss.s', 'h:mm:ss', '00:03:12,500' or plain seconds -> float seconds."""
    s = str(s).strip().replace(",", ".")
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return float(s)
    parts = s.split(":")
    if not 2 <= len(parts) <= 3 or not all(re.fullmatch(r"\d+(\.\d+)?", p) for p in parts):
        raise ValueError(f"bad time '{s}': use mm:ss, h:mm:ss or seconds")
    parts = [float(p) for p in parts]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def fmt_ts(sec):
    """Seconds -> mm:ss (minutes are not wrapped at 60, so 75:08 is a valid stamp)."""
    sec = max(0.0, float(sec))
    m, s = divmod(int(round(sec)), 60)
    return f"{m:02d}:{s:02d}"


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


# ---------------------------------------------------------------- transcripts

def load_transcript(path):
    with open(path, encoding="utf-8") as f:
        segs = json.load(f)
    if not isinstance(segs, list):
        die(f"{path}: a transcript is a JSON list of {{start, end, speaker, text}}")
    out = []
    for i, s in enumerate(segs):
        try:
            out.append({"start": float(s["start"]), "end": float(s["end"]),
                        "speaker": s.get("speaker"), "text": str(s.get("text", ""))})
        except (KeyError, TypeError, ValueError):
            die(f"{path}: segment {i} lacks numeric start/end or text")
    return out


def find_transcript(name, folder):
    """'p01', 'p01.json' or a path -> (stem, path)."""
    cands = [name]
    if not name.lower().endswith(".json"):
        cands.append(name + ".json")
    cands += [os.path.join(folder, os.path.basename(c)) for c in list(cands)]
    for c in cands:
        if os.path.isfile(c):
            return os.path.splitext(os.path.basename(c))[0], c
    return None, None


def write_transcript(segs, out_dir, stem, meta=None):
    os.makedirs(out_dir, exist_ok=True)
    jpath = os.path.join(out_dir, stem + ".json")
    with open(jpath, "w", encoding="utf-8", newline="\n") as f:
        json.dump(segs, f, ensure_ascii=False, indent=1)
    mpath = os.path.join(out_dir, stem + ".md")
    arabic = any(ARABIC_RE.search(s["text"]) for s in segs)
    lines = [f"# Transcript: {stem}", ""]
    if meta:
        lines += [f"- audio: {meta.get('audio')}", f"- language: {meta.get('lang')}",
                  f"- model: {meta.get('model')}", f"- duration: {fmt_ts(meta.get('duration') or 0)}",
                  f"- speakers expected: {meta.get('speakers') or 'not set'} (speaker labels are null until "
                  f"the researcher assigns them; whisper.cpp does not diarize mono audio)",
                  f"- transcribed: {meta.get('date')}", ""]
    for s in segs:
        who = f"{s['speaker']}: " if s.get("speaker") else ""
        text = s["text"].strip()
        if arabic and ARABIC_RE.search(text):
            text = "\u2067" + text + "\u2069"          # isolate RTL so the stamp stays on the left
        lines.append(f"[{fmt_ts(s['start'])}] {who}{text}")
    with open(mpath, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    if meta:
        with open(os.path.join(out_dir, stem + ".meta.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
    return jpath, mpath


# ---------------------------------------------------------------- transcribe

def find_whisper(flag):
    for c in [flag, os.environ.get("WHISPER_CLI", ""), os.environ.get("HYPERFRAMES_WHISPER_PATH", ""),
              shutil.which("whisper-cli"), shutil.which("whisper-cli.exe"), shutil.which("whisper-cpp")]:
        if c and os.path.isfile(c):
            return c
    return None


def find_model(flag, lang):
    if flag:
        if os.path.isfile(flag):
            return flag
        p = os.path.join(MODEL_DIR, flag if flag.endswith(".bin") else f"ggml-{flag}.bin")
        return p if os.path.isfile(p) else None
    want = DEFAULT_MODEL.get(lang, "ggml-large-v3-turbo.bin")
    p = os.path.join(MODEL_DIR, want)
    if os.path.isfile(p):
        return p
    if lang != "ar":                                  # any multilingual model will do for English
        others = [m for m in glob.glob(os.path.join(MODEL_DIR, "ggml-*.bin")) if ".en." not in m]
        if others:
            return sorted(others, key=os.path.getsize)[-1]
    return None


def wav_duration(path):
    try:
        with wave.open(path, "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, EOFError, OSError):
        return None


def cmd_transcribe(a):
    src = a.audio
    if not os.path.isfile(src):
        die(f"audio file not found: {src}")
    if os.path.splitext(src)[1].lower() not in AUDIO_EXT:
        die(f"not an audio file I know ({', '.join(sorted(AUDIO_EXT))}): {src}")
    whisper = find_whisper(a.whisper)
    if not whisper:
        die("whisper-cli not found.\n"
            "  1. Get whisper.cpp: Windows: unzip a release (whisper-bin-x64.zip, or the cuBLAS zip for a GPU) from\n"
            "     https://github.com/ggerganov/whisper.cpp/releases; macOS: brew install whisper-cpp; Linux: build it.\n"
            "  2. Put whisper-cli on PATH, or set the env var WHISPER_CLI to the full path of the binary\n"
            "     (or pass --whisper <path>). Restart the shell so the variable is visible.")
    model = find_model(a.model, a.lang)
    if not model:
        want = DEFAULT_MODEL.get(a.lang, "ggml-large-v3-turbo.bin")
        asked = f"--model {a.model} (not a file, not in {MODEL_DIR})" if a.model else os.path.join(MODEL_DIR, want)
        die(f"whisper model not found: {asked}\n"
            f"  Download it (about 1.6 GB, free; -C - resumes a stalled download):\n"
            f"  mkdir -p \"{MODEL_DIR}\" && curl -L -C - -o \"{os.path.join(MODEL_DIR, want)}\" {MODEL_URL}{want}\n"
            f"  Arabic needs a multilingual model (large-v3-turbo); the small.en / base.en models are English only.")
    stem = re.sub(r"[^\w\-]+", "_", os.path.splitext(os.path.basename(src))[0]).strip("_") or "audio"
    out_dir = a.out
    os.makedirs(out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="qual_")
    ffmpeg = shutil.which("ffmpeg")
    wav = os.path.join(tmp, stem + ".16k.wav")
    if ffmpeg:
        r = subprocess.run([ffmpeg, "-y", "-v", "error", "-i", src, "-ac", "1", "-ar", "16000",
                            "-c:a", "pcm_s16le", wav], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            die(f"ffmpeg could not convert {src}:\n{r.stderr.strip()[:800]}")
        print(f"converted with ffmpeg -> 16 kHz mono wav ({wav_duration(wav) or 0:.1f} s)")
    else:
        ext = os.path.splitext(src)[1].lower()
        if ext not in (".wav", ".mp3", ".flac", ".ogg"):
            die(f"ffmpeg is not installed and whisper-cli cannot read {ext} itself.\n"
                f"  Install it (free): winget install Gyan.FFmpeg   then re-run, or convert the file to wav/mp3 first.")
        print("ffmpeg not found: passing the file to whisper-cli as is (it resamples wav/mp3/flac/ogg itself)")
        wav = src
    base = os.path.join(tmp, stem)
    cmd = [whisper, "-m", model, "-l", a.lang, "-oj", "-osrt", "-of", base, "-f", wav]
    if a.threads:
        cmd += ["-t", str(a.threads)]
    if a.prompt:
        cmd += ["--prompt", a.prompt]
    print("running: " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    err = r.stderr or ""
    gpu = "GPU (CUDA)" if "loaded CUDA backend" in err else "CPU (no CUDA backend loaded: slow; see the cuBLAS DLL note in the skill)"
    if r.returncode != 0 or not os.path.isfile(base + ".json"):
        die(f"whisper-cli failed (exit {r.returncode}) on {gpu}:\n{err.strip()[-1200:]}")
    with open(base + ".json", encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    segs = []
    for t in data.get("transcription", []):
        off = t.get("offsets") or {}
        text = (t.get("text") or "").strip()
        if not re.search(r"\w", text):            # whisper emits "." or "..." on silence and tones
            continue
        segs.append({"start": round(off.get("from", 0) / 1000.0, 3), "end": round(off.get("to", 0) / 1000.0, 3),
                     "speaker": None, "text": text})
    meta = {"audio": os.path.abspath(src), "lang": a.lang, "model": os.path.basename(model), "backend": gpu,
            "duration": wav_duration(wav) if wav.lower().endswith(".wav") else None,
            "speakers": a.speakers, "segments": len(segs), "date": TODAY, "whisper": whisper,
            "detected_language": (data.get("result") or {}).get("language")}
    jpath, mpath = write_transcript(segs, out_dir, stem, meta)
    srt = os.path.join(out_dir, stem + ".srt")
    if os.path.isfile(base + ".srt"):
        shutil.copyfile(base + ".srt", srt)
    shutil.rmtree(tmp, ignore_errors=True)
    words = sum(len(s["text"].split()) for s in segs)
    print(f"{len(segs)} segment(s), {words} word(s), backend {gpu}, model {os.path.basename(model)}")
    if not segs:
        print("WARNING: the transcript is empty (silence, noise, or the wrong --lang). Nothing to code. "
              "Whisper can also hallucinate text on silence: check any short transcript against the audio.")
    for s in segs[:5]:
        print(f"  [{fmt_ts(s['start'])}] {short(s['text'], 90)}")
    if len(segs) > 5:
        print(f"  ... ({len(segs) - 5} more)")
    print(f"json: {os.path.abspath(jpath)}\nmd:   {os.path.abspath(mpath)}\nsrt:  {os.path.abspath(srt)}")
    if a.speakers:
        print(f"speakers expected: {a.speakers}. whisper.cpp does not label speakers on mono audio: "
              f"fill the 'speaker' field in the JSON (or prefix lines in the .md) before coding by speaker.")
    print("Review the transcript against the audio before coding: ASR errors become false quotes.")


# ---------------------------------------------------------------- codebook

CODE_FIELDS = ("code", "definition", "inclusion", "exclusion", "example")


def load_codebook(path, required=True):
    if not os.path.isfile(path):
        if required:
            die(f"codebook not found: {path}  (run: qual.py codebook init --out {path})")
        return None
    with open(path, encoding="utf-8") as f:
        cb = json.load(f)
    if "codes" not in cb or not isinstance(cb["codes"], list):
        die(f"{path}: expected {{\"codes\": [...]}}")
    return cb


def save_codebook(path, cb):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cb, f, ensure_ascii=False, indent=1)


def cmd_codebook(a):
    if a.action == "init":
        if os.path.exists(a.out) and not a.force:
            die(f"{a.out} exists; use --force to overwrite")
        cb = {"created": TODAY,
              "template": {"code": "short_label", "definition": "what the code captures (one sentence)",
                           "inclusion": "apply when ...", "exclusion": "do not apply when ... (use <other code> instead)",
                           "example": "a verbatim quote with its [transcript mm:ss] stamp"},
              "codes": []}
        save_codebook(a.out, cb)
        print(f"codebook written: {os.path.abspath(a.out)} (0 codes). Add codes with: qual.py codebook add --code ... --definition ...")
        return
    cb = load_codebook(a.codebook)
    if a.action == "add":
        code = (a.code or "").strip()
        if not code:
            die("--code is required")
        if not a.definition:
            die("--definition is required (a code without a definition cannot be applied consistently)")
        if any(c["code"] == code for c in cb["codes"]):
            die(f"code '{code}' is already in the codebook")
        cb["codes"].append({"code": code, "definition": a.definition.strip(), "inclusion": (a.inclusion or "").strip(),
                            "exclusion": (a.exclusion or "").strip(), "example": (a.example or "").strip(),
                            "added": TODAY})
        save_codebook(a.codebook, cb)
        print(f"added '{code}' ({len(cb['codes'])} codes) -> {os.path.abspath(a.codebook)}")
        return
    rows = [[c["code"], short(c.get("definition", ""), 60), short(c.get("inclusion", ""), 40),
             short(c.get("exclusion", ""), 40)] for c in cb["codes"]]
    print(f"{len(rows)} code(s) in {a.codebook}")
    print(table(rows, ["code", "definition", "inclusion", "exclusion"]))


# ---------------------------------------------------------------- coding

def load_coding(path):
    if not os.path.isfile(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    die(f"{path} line {n}: not valid JSON")
    return out


def cmd_code(a):
    if a.action != "add":
        die("only 'code add' exists; list codings with 'themes' or 'quote'")
    stem, tpath = find_transcript(a.transcript, a.transcripts)
    if not tpath:
        die(f"transcript not found: {a.transcript} (looked in {a.transcripts}/; run 'transcribe' first)")
    segs = load_transcript(tpath)
    if not segs:
        die(f"{tpath} has no segments")
    try:
        start, end = parse_ts(a.start), parse_ts(a.end)
    except ValueError as e:
        die(str(e))
    if end <= start:
        die(f"REFUSED: --end ({fmt_ts(end)}) must be after --start ({fmt_ts(start)})")
    t_end = max(s["end"] for s in segs)
    if start >= t_end or end > t_end + 0.5:
        die(f"REFUSED: window {fmt_ts(start)}-{fmt_ts(end)} is outside the transcript '{stem}' "
            f"(it ends at {fmt_ts(t_end)})")
    hit = []
    for i, s in enumerate(segs):
        ov = overlap(start, end, s["start"], s["end"])
        if ov > 0 and (ov >= MIN_OVERLAP or ov >= 0.5 * (s["end"] - s["start"])):
            hit.append(i)
    if not hit:
        die(f"REFUSED: no transcript segment is covered by {fmt_ts(start)}-{fmt_ts(end)} in '{stem}' "
            f"(a window must cover at least {MIN_OVERLAP:.0f} s or half of a segment)")
    cb = load_codebook(a.codebook)
    code = a.code.strip()
    if not any(c["code"] == code for c in cb["codes"]):
        near = [c["code"] for c in cb["codes"] if c["code"].casefold() == code.casefold()]
        hint = f" (did you mean '{near[0]}'? codes are case-sensitive)" if near else ""
        die(f"REFUSED: code '{code}' is not in the codebook {a.codebook}{hint}. "
            f"Add it first: qual.py codebook add --code \"{code}\" --definition \"...\"")
    quote = " ".join(segs[i]["text"].strip() for i in hit)
    entries = load_coding(a.coding)
    dup = [e for e in entries if e.get("transcript") == stem and e.get("code") == code and e.get("coder") == a.coder
           and overlap(start, end, e["start"], e["end"]) > 0]
    if dup and not a.force:
        die(f"REFUSED: coder {a.coder} already applied '{code}' to an overlapping window in '{stem}' "
            f"({fmt_ts(dup[0]['start'])}-{fmt_ts(dup[0]['end'])}); use --force to add anyway")
    entry = {"id": f"c{len(entries) + 1:04d}", "transcript": stem, "start": round(start, 3), "end": round(end, 3),
             "segments": hit, "seg_start": segs[hit[0]]["start"], "seg_end": segs[hit[-1]]["end"],
             "speaker": segs[hit[0]].get("speaker"), "code": code, "coder": a.coder.strip(),
             "quote": quote, "note": (a.note or "").strip(), "added": dt.datetime.now().isoformat(timespec="seconds")}
    with open(a.coding, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"coded {entry['id']}: [{stem} {fmt_ts(start)}-{fmt_ts(end)}] '{code}' by {entry['coder']} "
          f"(segments {hit[0]}-{hit[-1]}, {len(quote.split())} words)")
    print(f"quote: {short(quote, 160)}")
    print(f"-> {os.path.abspath(a.coding)}")


# ---------------------------------------------------------------- agreement

def segment_labels(entries, coder):
    """(transcript, segment index) -> code with the largest overlap for this coder."""
    best = {}
    for e in entries:
        if e.get("coder") != coder:
            continue
        for i in e.get("segments", []):
            key = (e["transcript"], i)
            # The coding window is the unit; a segment fully inside one window gets that window's code.
            # Several codes on one segment by one coder: keep the earliest added (stable, documented).
            best.setdefault(key, e["code"])
    return best


def cohen_kappa(pairs):
    """pairs = [(label_a, label_b)]. Returns (kappa or None, po, pe, reason)."""
    n = len(pairs)
    if n == 0:
        return None, None, None, "no segment coded by both coders"
    po = sum(1 for x, y in pairs if x == y) / n
    ca, cb = Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    pe = sum(ca[c] * cb.get(c, 0) for c in ca) / (n * n)
    if abs(1 - pe) < 1e-12:
        return None, po, pe, "expected agreement is 1 (both coders used one single code everywhere), kappa undefined"
    return (po - pe) / (1 - pe), po, pe, ""


def kappa_band(k):
    if k < 0:
        return "poor (below chance)"
    for lo, name in KAPPA_BANDS:
        if k >= lo - 1e-9:
            return name
    return "slight"


def cmd_agreement(a):
    entries = load_coding(a.coding)
    if not entries:
        die(f"no codings in {a.coding}")
    A, B = a.coders
    la, lb = segment_labels(entries, A), segment_labels(entries, B)
    if not la or not lb:
        missing = [c for c, l in ((A, la), (B, lb)) if not l]
        die(f"RESULT: FAIL (coder {', '.join(missing)} has no codings in {a.coding}; coders present: "
            f"{', '.join(sorted({e.get('coder', '') for e in entries}))})")
    common = sorted(set(la) & set(lb))
    pairs = [(la[k], lb[k]) for k in common]
    k, po, pe, why = cohen_kappa(pairs)
    print(f"agreement between {A} and {B}: {len(common)} segment(s) coded by both "
          f"({len(la)} by {A}, {len(lb)} by {B}, overlap by shared transcript segments)")
    ev = [f"qual.agreement.{A}_{B}.n_segments = {len(common)}"]
    if k is None:
        print(f"kappa: not computable ({why})")
        if po is not None:
            print(f"percent agreement: {po * 100:.1f}%")
            ev.append(f"qual.agreement.{A}_{B}.agreement_pct = {po * 100:.1f}")
        ev.append(f"# qual.agreement.{A}_{B}.kappa not computable: {why}")
        print("\n".join(ev))
        if a.evidence:
            append_evidence(a.evidence, ev)
        print("RESULT: FAIL (kappa not computable)")
        sys.exit(1)
    band = kappa_band(k)
    codes = sorted({c for p in pairs for c in p})
    rows = []
    for c in codes:
        tp = sum(1 for x, y in pairs if x == c and y == c)
        na, nb = sum(1 for x, _ in pairs if x == c), sum(1 for _, y in pairs if y == c)
        rows.append([c, str(na), str(nb), str(tp)])
    print(table(rows, ["code", f"{A} segments", f"{B} segments", "both"]))
    dis = [(k_, x, y) for k_, (x, y) in zip(common, pairs) if x != y]
    if dis:
        print(f"\n{len(dis)} disagreement(s) to discuss (transcript, segment: {A} vs {B}):")
        for (t, i), x, y in dis[:a.show]:
            print(f"  {t} seg {i}: {x} vs {y}")
        if len(dis) > a.show:
            print(f"  ... {len(dis) - a.show} more")
    print(f"\nCohen's kappa = {k:.3f} ({band}), percent agreement = {po * 100:.1f}%, expected by chance = {pe * 100:.1f}%")
    print("Bands: <0 poor, 0-0.20 slight, 0.21-0.40 fair, 0.41-0.60 moderate, 0.61-0.80 substantial, 0.81-1 almost perfect "
          "(Landis and Koch style bands; add the source to the ledger before citing it).")
    ev += [f"qual.agreement.{A}_{B}.kappa = {k:.3f}", f"qual.agreement.{A}_{B}.agreement_pct = {po * 100:.1f}",
           f"qual.agreement.{A}_{B}.n_codes = {len(codes)}",
           f"# APA: Inter-coder agreement between {A} and {B} on {len(common)} segments was {po * 100:.1f}% "
           f"(Cohen's kappa = {k:.2f}, {band})."]
    print("\n" + "\n".join(ev))
    if a.evidence:
        append_evidence(a.evidence, ev)
    print("Not checked: whether both coders read the whole transcript (uncoded segments are not units); "
          "unitising agreement (whether coders chose the same windows) is not part of kappa.")
    print(f"RESULT: PASS (kappa {k:.3f}, {band})")


def append_evidence(path, lines):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(f"# qual.py agreement {TODAY}\n" + "\n".join(lines) + "\n")
    print(f"evidence appended -> {os.path.abspath(path)}")


# ---------------------------------------------------------------- themes & quotes

def stamp(e):
    return f"[{e['transcript']} {fmt_ts(e['start'])}-{fmt_ts(e['end'])}]"


def best_quotes(entries, n):
    """Heuristic ranking: quotes two coders agreed on first, then spread across transcripts, then length.
    The researcher picks the final quote; this is a shortlist."""
    by_key = defaultdict(list)
    for e in entries:
        by_key[(e["transcript"], tuple(e.get("segments", [])))].append(e)
    cands = []
    for group in by_key.values():
        coders = {g.get("coder") for g in group}
        e = group[0]
        cands.append((len(coders), len(e["quote"].split()), e))
    cands.sort(key=lambda x: (-x[0], -x[1]))
    out, seen_t = [], Counter()
    for _, _, e in cands:                              # first pass: one per transcript
        if seen_t[e["transcript"]] == 0 and len(out) < n:
            out.append(e)
            seen_t[e["transcript"]] += 1
    for _, _, e in cands:
        if len(out) >= n:
            break
        if e not in out:
            out.append(e)
    return out


def md_quote(e):
    q = e["quote"].strip()
    if ARABIC_RE.search(q):
        q = "\u2067" + q + "\u2069"
    return f"> {q}  \n> {stamp(e)}, coder {e.get('coder', '?')}" + (f", note: {e['note']}" if e.get("note") else "")


def cmd_themes(a):
    entries = load_coding(a.coding)
    if not entries:
        die(f"no codings in {a.coding}")
    cb = load_codebook(a.codebook, required=False) if a.codebook else None
    defs = {c["code"]: c for c in (cb or {}).get("codes", [])}
    codes = sorted({e["code"] for e in entries})
    transcripts = sorted({e["transcript"] for e in entries})
    coders = sorted({e.get("coder", "") for e in entries})
    unknown = [c for c in codes if defs and c not in defs]
    # order of transcripts for the saturation curve: --order, else first coding time
    first_seen = {}
    for e in sorted(entries, key=lambda x: x.get("added", "")):
        first_seen.setdefault(e["transcript"], e.get("added", ""))
    if a.order:
        wanted = [t.strip() for t in a.order.split(",")]
        order = [t for t in wanted if t in transcripts] + [t for t in transcripts if t not in wanted]
    else:
        order = sorted(transcripts, key=lambda t: first_seen.get(t, ""))
    n_cod = Counter(e["code"] for e in entries)
    per_t = defaultdict(Counter)
    for e in entries:
        per_t[e["code"]][e["transcript"]] += 1
    lines = [f"# Themes report", "", f"- source: {os.path.abspath(a.coding)} ({len(entries)} codings, "
             f"{len(codes)} codes, {len(transcripts)} transcripts, coders: {', '.join(coders)})",
             f"- generated: {TODAY} by qual.py. Counts are codings, not people; quotes are verbatim with stamps.", ""]
    if unknown:
        lines.append(f"- WARNING: codes not in the codebook: {', '.join(unknown)}")
        lines.append("")
    lines += ["## Code frequencies", ""]
    rows = [[c, str(n_cod[c]), str(len(per_t[c])), short(defs.get(c, {}).get("definition", ""), 70)] for c in codes]
    lines += [table(rows, ["code", "codings", "transcripts", "definition"]), ""]
    lines += ["## Code by transcript", ""]
    rows = [[c] + [str(per_t[c].get(t, 0)) for t in order] for c in codes]
    lines += [table(rows, ["code"] + order), ""]
    # co-occurrence: two different codes on overlapping windows in the same transcript (any coder)
    co = Counter()
    for i, x in enumerate(entries):
        for y in entries[i + 1:]:
            if x["transcript"] == y["transcript"] and x["code"] != y["code"] and \
                    overlap(x["start"], x["end"], y["start"], y["end"]) > 0:
                co[tuple(sorted((x["code"], y["code"])))] += 1
    lines += ["## Co-occurrence (two codes on overlapping windows, same transcript, any coder)", ""]
    if co:
        rows = [[p[0], p[1], str(n)] for p, n in co.most_common()]
        lines += [table(rows, ["code A", "code B", "overlaps"]), ""]
    else:
        lines += ["none", ""]
    lines += ["## Saturation curve (new codes per transcript, in coding order)", ""]
    seen, rows, cum = set(), [], 0
    for t in order:
        here = {e["code"] for e in entries if e["transcript"] == t}
        new = sorted(here - seen)
        seen |= here
        cum = len(seen)
        rows.append([t, str(len(here)), str(len(new)), str(cum), ", ".join(new)])
    lines += [table(rows, ["transcript", "codes used", "new codes", "cumulative", "which new"]), ""]
    tail = [int(r[2]) for r in rows[-2:]]
    if len(rows) < 3:
        lines.append(f"- Only {len(rows)} transcript(s): too few to judge saturation.")
    elif sum(tail) == 0:
        lines.append(f"- No new code appeared in the last {len(tail)} transcripts: a saturation signal, "
                     f"not proof of it (judge by meaning, not count).")
    else:
        lines.append("- New codes still appeared in the last transcripts: saturation is NOT shown yet.")
    lines.append("")
    lines += ["## Quotes per code (shortlist, heuristic: coder agreement, spread, length; pick the final ones yourself)", ""]
    for c in codes:
        lines.append(f"### {c}" + (f": {defs[c]['definition']}" if c in defs else ""))
        lines.append("")
        for e in best_quotes([e for e in entries if e["code"] == c], a.n):
            lines += [md_quote(e), ""]
    lines += ["## Not checked", "",
              "- Whether a code's meaning drifted between transcripts (re-read the codebook against late quotes).",
              "- Speaker attribution: speaker fields are null unless the researcher filled them.",
              "- Transcription accuracy: every quote must be checked against the audio before it is published.", ""]
    text = "\n".join(lines)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"{len(entries)} codings, {len(codes)} codes, {len(transcripts)} transcripts -> {os.path.abspath(a.out)}")
        print(table([[c, str(n_cod[c]), str(len(per_t[c]))] for c in codes], ["code", "codings", "transcripts"]))
    else:
        print(text)


def cmd_quote(a):
    entries = [e for e in load_coding(a.coding) if e["code"] == a.code]
    if a.transcript:
        entries = [e for e in entries if e["transcript"] == a.transcript]
    if not entries:
        die(f"no quotes coded '{a.code}' in {a.coding}" + (f" for transcript {a.transcript}" if a.transcript else "")
            + " (NOT FOUND: do not paraphrase one from memory)")
    picked = best_quotes(entries, a.n)
    print(f"{len(picked)} of {len(entries)} quote(s) for '{a.code}' (verbatim, with stamps):\n")
    for e in picked:
        print(md_quote(e))
        print()


# ---------------------------------------------------------------- selftest

AR_SEGMENTS = [
    (0.0, 6.2, "في البداية ما كنت أثق بالتطبيق، حسيت إنه معلوماتي رح تنتشر."),
    (6.2, 12.9, "بس لما شفت إنه المستشفى هو اللي يدير النظام صار عندي اطمئنان أكثر."),
    (12.9, 19.0, "الصعوبة الأساسية كانت إنه الواجهة كلها بالإنجليزي وأمي ما بتعرف تقرأها."),
    (19.0, 25.5, "طلبت من أختي تساعدني، يعني العائلة هي اللي حلت المشكلة مش التطبيق."),
    (25.5, 31.0, "التذكير بالموعد كان أهم شي، نسيت مرتين قبل ما أستخدمه."),
    (31.0, 36.4, "لو في نسخة عربية كاملة كنت استخدمته من أول يوم."),
]
EN_SEGMENTS = [
    (0.0, 5.0, "At first I did not trust the app with my records."),
    (5.0, 10.0, "The reminders were the only reason I kept it."),
    (10.0, 15.0, "My daughter had to set it up for me, the text was too small."),
    (15.0, 20.0, "Once the clinic explained who sees the data I relaxed."),
]


def run(args, **kw):
    cmd = [sys.executable, "-X", "utf8", os.path.abspath(__file__)] + [str(x) for x in args]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def cmd_selftest(a):
    root = tempfile.mkdtemp(prefix="qual_selftest_")
    tdir = os.path.join(root, "transcripts")
    write_transcript([{"start": s, "end": e, "speaker": None, "text": t} for s, e, t in AR_SEGMENTS], tdir, "p01_ar")
    write_transcript([{"start": s, "end": e, "speaker": None, "text": t} for s, e, t in EN_SEGMENTS], tdir, "p02_en")
    back = load_transcript(os.path.join(tdir, "p01_ar.json"))
    checks = [("Arabic transcript round-trips byte for byte", [b["text"] for b in back] == [t for _, _, t in AR_SEGMENTS])]
    md = open(os.path.join(tdir, "p01_ar.md"), encoding="utf-8").read()
    checks.append(("md has [mm:ss] stamps and Arabic", "[00:06]" in md and "اطمئنان" in md))
    cb, cod = os.path.join(root, "codebook.json"), os.path.join(root, "coding.jsonl")
    checks.append(("codebook init", run(["codebook", "init", "--out", cb]).returncode == 0))
    for code, d in [("trust", "trust or distrust in who holds the data"), ("language", "Arabic/English interface barrier"),
                    ("family", "a relative does the task"), ("reminders", "appointment reminders as value")]:
        checks.append((f"codebook add {code}", run(["codebook", "add", "--codebook", cb, "--code", code, "--definition", d]).returncode == 0))
    base = ["code", "add", "--transcripts", tdir, "--codebook", cb, "--coding", cod]
    # Coder A and B on 4 shared segments of p01_ar: labels A = trust,trust,language,language ; B = trust,language,language,language
    plan = [("A", "00:00", "00:06", "trust"), ("A", "00:06", "00:12", "trust"), ("A", "00:13", "00:19", "language"),
            ("A", "00:19", "00:25", "language"), ("A", "00:25", "00:31", "reminders"),
            ("B", "00:00", "00:06", "trust"), ("B", "00:06", "00:12", "language"), ("B", "00:13", "00:19", "language"),
            ("B", "00:19", "00:25", "language"), ("B", "00:31", "00:36", "language"),
            ("A", "00:00", "00:05", "trust", "p02_en"), ("A", "00:10", "00:15", "family", "p02_en")]
    for p in plan:
        t = p[4] if len(p) > 4 else "p01_ar"
        r = run(base + ["--transcript", t, "--start", p[1], "--end", p[2], "--code", p[3], "--coder", p[0]])
        checks.append((f"code add {p[0]} {t} {p[1]}-{p[2]} {p[3]}", r.returncode == 0))
    e1 = load_coding(cod)
    checks.append(("quote stored verbatim from the Arabic transcript", e1[0]["quote"] == AR_SEGMENTS[0][2]))
    # negative controls
    r = run(base + ["--transcript", "p01_ar", "--start", "40:00", "--end", "41:00", "--code", "trust", "--coder", "A"])
    checks.append(("NEGATIVE: window outside the transcript is refused", r.returncode == 1 and "REFUSED" in r.stderr and "outside" in r.stderr))
    r = run(base + ["--transcript", "p01_ar", "--start", "00:00", "--end", "00:05", "--code", "ghost", "--coder", "A"])
    checks.append(("NEGATIVE: code not in the codebook is refused", r.returncode == 1 and "not in the codebook" in r.stderr))
    r = run(base + ["--transcript", "p01_ar", "--start", "00:10", "--end", "00:05", "--code", "trust", "--coder", "A"])
    checks.append(("NEGATIVE: end before start is refused", r.returncode == 1 and "REFUSED" in r.stderr))
    checks.append(("coding.jsonl unchanged after refusals", len(load_coding(cod)) == len(plan)))
    # agreement: expected po = 3/4, pe = 0.5, kappa = 0.5
    r = run(["agreement", cod, "--coders", "A", "B"])
    checks.append(("agreement A-B runs", r.returncode == 0))
    checks.append(("kappa = 0.500 and 75.0% on 4 shared segments (hand-computed)",
                   "qual.agreement.A_B.kappa = 0.500" in r.stdout and "agreement_pct = 75.0" in r.stdout
                   and "n_segments = 4" in r.stdout))
    r = run(["agreement", cod, "--coders", "A", "C"])
    checks.append(("NEGATIVE: unknown coder C fails clearly", r.returncode == 1 and "has no codings" in r.stderr))
    # kappa with no overlapping segments: coder D codes only p02_en, coder B only p01_ar
    run(base + ["--transcript", "p02_en", "--start", "00:05", "--end", "00:10", "--code", "reminders", "--coder", "D"])
    r = run(["agreement", cod, "--coders", "B", "D"])
    checks.append(("NEGATIVE: no overlapping segments -> 'not computable'", r.returncode == 1 and "not computable" in r.stdout))
    out = os.path.join(root, "themes.md")
    r = run(["themes", cod, "--codebook", cb, "--out", out])
    rep = open(out, encoding="utf-8").read() if os.path.isfile(out) else ""
    checks.append(("themes report written", r.returncode == 0 and "## Saturation curve" in rep and "[p01_ar 00:00-00:06]" in rep))
    checks.append(("themes report carries the Arabic quote", AR_SEGMENTS[2][2] in rep))
    r = run(["quote", "--coding", cod, "--code", "language", "--n", "2"])
    checks.append(("quote returns stamped Arabic quotes", r.returncode == 0 and "[p01_ar" in r.stdout and "الواجهة" in r.stdout))
    r = run(["quote", "--coding", cod, "--code", "nothing"])
    checks.append(("NEGATIVE: quote for an unused code says NOT FOUND", r.returncode == 1 and "NOT FOUND" in r.stderr))
    if a.audio:
        r = run(["transcribe", a.audio, "--lang", a.lang, "--out", os.path.join(root, "tr")])
        checks.append((f"transcribe {os.path.basename(a.audio)} end to end", r.returncode == 0 and "json:" in r.stdout))
        print(r.stdout.strip()[-600:])
    else:
        print("transcribe not exercised (pass --audio file.wav --lang ar|en to include it)")
    rows = [["PASS" if ok else "FAIL", name] for name, ok in checks]
    print(table(rows, ["result", "check"]))
    failed = [n for n, ok in checks if not ok]
    print(f"files: {root}")
    if failed:
        print(f"RESULT: FAIL ({len(failed)} of {len(checks)} checks failed)")
        sys.exit(1)
    print(f"RESULT: PASS ({len(checks)} checks)")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("transcribe", help="audio -> transcripts/<name>.json + .md (local whisper.cpp)",
                       epilog="example: qual.py transcribe p01.m4a --lang ar --out transcripts/ --speakers 2")
    p.add_argument("audio")
    p.add_argument("--lang", required=True, choices=["ar", "en", "auto"])
    p.add_argument("--out", default="transcripts")
    p.add_argument("--speakers", type=int, help="expected number of speakers (recorded in meta; labels stay null)")
    p.add_argument("--model", help="model path or name (default: ggml-large-v3-turbo.bin in the hyperframes cache)")
    p.add_argument("--whisper", help="path to the whisper-cli binary (default: env WHISPER_CLI, then PATH)")
    p.add_argument("--threads", type=int)
    p.add_argument("--prompt", help="initial prompt (names, terms, dialect hint) to steer spelling")
    p.set_defaults(fn=cmd_transcribe)

    p = sub.add_parser("codebook", help="init / add / list the codebook",
                       epilog="example: qual.py codebook add --code trust --definition \"...\" --inclusion \"...\"")
    p.add_argument("action", choices=["init", "add", "list"])
    p.add_argument("--out", default="codebook.json", help="init: where to write")
    p.add_argument("--codebook", default="codebook.json")
    p.add_argument("--force", action="store_true")
    for f in CODE_FIELDS:
        p.add_argument("--" + f)
    p.set_defaults(fn=cmd_codebook)

    p = sub.add_parser("code", help="code add: apply a code to a time window of a transcript",
                       epilog="example: qual.py code add --transcript p01 --start 03:12 --end 03:40 --code trust --coder A")
    p.add_argument("action", choices=["add"])
    p.add_argument("--transcript", required=True, help="name (p01), file name or path of the transcript JSON")
    p.add_argument("--transcripts", default="transcripts", help="folder with transcript JSON files")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--code", required=True)
    p.add_argument("--coder", required=True)
    p.add_argument("--note")
    p.add_argument("--codebook", default="codebook.json")
    p.add_argument("--coding", default="coding.jsonl")
    p.add_argument("--force", action="store_true", help="allow a second identical code on an overlapping window")
    p.set_defaults(fn=cmd_code)

    p = sub.add_parser("agreement", help="Cohen's kappa and percent agreement between two coders",
                       epilog="example: qual.py agreement coding.jsonl --coders A B --evidence analysis/output.txt")
    p.add_argument("coding", nargs="?", default="coding.jsonl")
    p.add_argument("--coders", nargs=2, required=True, metavar=("A", "B"))
    p.add_argument("--evidence", help="append the qual.* evidence lines to this file")
    p.add_argument("--show", type=int, default=20, help="disagreements to list")
    p.set_defaults(fn=cmd_agreement)

    p = sub.add_parser("themes", help="counts, co-occurrence, best quotes, saturation -> markdown",
                       epilog="example: qual.py themes coding.jsonl --codebook codebook.json --out themes.md")
    p.add_argument("coding", nargs="?", default="coding.jsonl")
    p.add_argument("--codebook")
    p.add_argument("--out", help="write the markdown report here (default: print)")
    p.add_argument("--n", type=int, default=3, help="quotes per code")
    p.add_argument("--order", help="comma-separated transcript order for the saturation curve")
    p.set_defaults(fn=cmd_themes)

    p = sub.add_parser("quote", help="quotes for one code with [transcript mm:ss] stamps",
                       epilog="example: qual.py quote --code trust --n 5")
    p.add_argument("--code", required=True)
    p.add_argument("--n", type=int, default=5)
    p.add_argument("--coding", default="coding.jsonl")
    p.add_argument("--transcript")
    p.set_defaults(fn=cmd_quote)

    p = sub.add_parser("selftest", help="pipeline test on an Arabic fake transcript with planted errors",
                       epilog="example: qual.py selftest --audio clip.wav --lang ar")
    p.add_argument("--audio", help="optional real audio to run transcribe end to end")
    p.add_argument("--lang", default="ar")
    p.set_defaults(fn=cmd_selftest)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
