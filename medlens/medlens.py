#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEDLENS — a multi-agent medical lab-report assistant (RESEARCH / EDUCATIONAL PROTOTYPE).

================================  READ THIS FIRST  ================================
This is NOT a clinical tool and must never present itself as one.

  * Synthetic data only — it ships a synthetic sample report and never reads,
    requests, or stores real patient data.
  * Decision-support, not diagnosis — the reasoning stage outputs *possibilities
    to discuss with a clinician*, with explicit uncertainty. Never a diagnosis.
  * Human-in-the-loop — every reasoning output is an UNVERIFIED DRAFT for a
    qualified clinician to check.
  * Local-first — prefer local execution so nothing leaves the machine.
==================================================================================

It is a simple, hardwired three-stage pipeline (no tool-choosing, no agent
framework, no classes, no async — just functions run in order):

    Stage 1  EXTRACT  image/PDF  -> structured values        (Docling + Surya OCR)
    Stage 2  FLAG     values     -> high/low/normal flags     (PURE PYTHON, no LLM)
    Stage 3  REASON   abnormals  -> bounded "considerations"  (configurable LLM)

and it writes a Markdown report (lab_report_review.md) that leads with the
disclaimer and is structured so the human-in-the-loop framing is obvious.

Install:  pip install docling surya-ocr requests pillow
          (Docling + Surya run locally. The reasoning stage is vendor-agnostic: it
           talks to any OpenAI-compatible /chat/completions endpoint over plain
           HTTP — no vendor SDK — e.g. a local MedGemma/Meditron via Ollama, or a
           hosted gateway like Groq/Gemini, by swapping --base-url/--model.)

Run:      python medlens.py                 # generate sample + run the full pipeline
          python medlens.py --input scan.png # run on your own (synthetic!) scan
          python medlens.py --base-url http://localhost:11434/v1 --model meditron
"""

import os
import re
import sys
import json
import argparse
import datetime

import requests  # only hard third-party dep at import time; heavy ones are lazy


# ============================================================================
# Constants & configuration
# ============================================================================

# Printed at the top (and bottom) of every report and to the console. Verbatim,
# non-negotiable — this is what keeps the prototype honestly scoped.
DISCLAIMER = (
    "EDUCATIONAL PROTOTYPE — NOT FOR CLINICAL USE. Not a medical device. "
    "Outputs are unverified and may be wrong. Consult a qualified clinician."
)

# Default LLM endpoint: local-first (Ollama's OpenAI-compatible server). Override
# with flags or env vars so you can point at a local MedGemma/Meditron, or a free
# hosted OpenAI-compatible API (Gemini/Groq/…). The api_key is irrelevant to
# Ollama but required by hosted APIs.
DEFAULT_BASE_URL = os.environ.get("MEDLENS_BASE_URL", "http://localhost:11434/v1")
DEFAULT_MODEL = os.environ.get("MEDLENS_MODEL", "meditron")  # medical model recommended
DEFAULT_API_KEY = os.environ.get("MEDLENS_API_KEY") or os.environ.get("OPENAI_API_KEY") or "ollama"

# Where the synthetic sample + the output report live, relative to this file.
HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE_IMG = os.path.join(HERE, "sample_lab_report.png")
SAMPLE_TXT = os.path.join(HERE, "sample_lab_report.txt")  # OCR-equivalent transcript
DEFAULT_OUT = os.path.join(HERE, "lab_report_review.md")


# ============================================================================
# Synthetic sample generation
# A fake Full Blood Count (FBC/CBC) panel with a few deliberately out-of-range
# values, one row with NO printed reference range, and one unreadable value — so
# the whole pipeline (high/low/normal/cannot_assess/unparsed) is exercised.
# Patient identifiers are obviously fake. NOTHING here is real.
# ============================================================================

# (test_name, value, unit, reference_range, flag_from_report)
# A blank reference_range means the report itself printed no range for that test.
# A non-numeric value ("--") simulates a smudged/unreadable scan field.
SYNTHETIC_ROWS = [
    ("Haemoglobin",        "9.8",  "g/dL",    "13.0-17.0", "L"),
    ("Red Cell Count",     "4.1",  "10^12/L", "4.5-5.9",   "L"),
    ("Haematocrit",        "0.31", "L/L",     "0.40-0.54", "L"),
    ("Mean Cell Volume",   "78",   "fL",      "80-100",    "L"),
    ("White Cell Count",   "12.6", "10^9/L",  "4.0-11.0",  "H"),
    ("Neutrophils",        "9.1",  "10^9/L",  "2.0-7.5",   "H"),
    ("Lymphocytes",        "2.3",  "10^9/L",  "1.0-4.0",   ""),
    ("Platelets",          "178",  "10^9/L",  "150-400",   ""),
    ("C-Reactive Protein", "48",   "mg/L",    "",          ""),   # no range on report
    ("Ferritin",           "--",   "ug/L",    "30-400",    ""),   # unreadable value
]

SAMPLE_HEADER = "SYNTHETIC SAMPLE — Full Blood Count (FBC)   Patient: SAMPLE, Test (synthetic, not real)"


def _rows_to_markdown_table(rows):
    """Render the panel as a Markdown pipe-table. Docling's `export_to_markdown()`
    emits this exact shape for tabular scans, so our parser is identical whether
    the text came from real OCR or from the transcript fallback."""
    out = ["| Test | Result | Units | Reference Range | Flag |",
           "| --- | --- | --- | --- | --- |"]
    for name, value, unit, rng, flag in rows:
        out.append("| %s | %s | %s | %s | %s |" % (name, value, unit, rng, flag))
    return "\n".join(out)


def generate_synthetic_report(img_path=SAMPLE_IMG, txt_path=SAMPLE_TXT):
    """Write a synthetic lab-report image (PNG) and a parallel text transcript.

    The transcript is what a perfect OCR pass would yield; it is used as a
    deterministic fallback when Docling/Surya aren't installed, so the pipeline
    is always testable offline. Returns (img_path, txt_path)."""
    table_md = _rows_to_markdown_table(SYNTHETIC_ROWS)
    transcript = "%s\n\n%s\n" % (SAMPLE_HEADER, table_md)

    # Always write the transcript (canonical, OCR-independent).
    with open(txt_path, "w", encoding="utf-8") as fh:
        fh.write("# " + DISCLAIMER + "\n\n")
        fh.write(transcript)

    # Best-effort: render a simple image "scan" with Pillow. If Pillow is missing
    # we still have the transcript, so this never blocks the run.
    try:
        from PIL import Image, ImageDraw, ImageFont
        font = ImageFont.load_default()
        lines = [
            "SYNTHETIC SAMPLE LAB REPORT  (NOT REAL — EDUCATIONAL PROTOTYPE)",
            "Patient: SAMPLE, Test    DOB: 1900-01-01    MRN: SYN-000000",
            "Specimen: whole blood (EDTA)    Panel: Full Blood Count (FBC)",
            "-" * 78,
            "%-22s %-8s %-9s %-14s %s" % ("Test", "Result", "Units", "Ref. Range", "Flag"),
            "-" * 78,
        ]
        for name, value, unit, rng, flag in SYNTHETIC_ROWS:
            lines.append("%-22s %-8s %-9s %-14s %s" % (name, value, unit, rng or "(none)", flag))
        lines += ["-" * 78, DISCLAIMER]

        pad, lh = 16, 16
        img = Image.new("RGB", (640, pad * 2 + lh * len(lines)), "white")
        draw = ImageDraw.Draw(img)
        for i, line in enumerate(lines):
            draw.text((pad, pad + i * lh), line, fill="black", font=font)
        img.save(img_path)
    except Exception as e:  # pragma: no cover - image is a convenience, not required
        log("could not render sample image (%s); transcript still written" % e)
        img_path = None

    return img_path, txt_path


# ============================================================================
# STAGE 1 — EXTRACT  (image/PDF -> structured values)
# Docling does layout + table structure; Surya is the OCR engine. Both local.
# We degrade gracefully: Docling -> (direct Surya) -> text transcript. Whatever
# produces the text, the SAME table/line parser turns it into structured rows.
# ============================================================================

def _docling_to_text(path, ocr_engine="surya"):
    """Convert an image/PDF to Markdown text with Docling (Surya OCR).

    Surya availability as a Docling OCR engine depends on the installed Docling
    version; we try to select it and fall back to Docling's default OCR if not
    available. Raises on any failure so the caller can try the next strategy."""
    from docling.document_converter import DocumentConverter  # lazy, heavy import

    converter = None
    # Try to wire Surya in explicitly; the exact options class name varies by
    # Docling version, so this is best-effort and clearly isolated.
    try:
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        opts = PdfPipelineOptions()
        opts.do_ocr = True
        # Some Docling builds expose a Surya OCR options class; use it if present.
        try:
            from docling.datamodel.pipeline_options import SuryaOcrOptions  # type: ignore
            opts.ocr_options = SuryaOcrOptions()
            log("Docling: using Surya OCR engine")
        except Exception:
            log("Docling: Surya options not found in this build; using default OCR engine")
        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts),
                            InputFormat.IMAGE: PdfFormatOption(pipeline_options=opts)})
    except Exception:
        # Fall back to a vanilla converter (still OCRs; engine = Docling default).
        converter = DocumentConverter()

    result = converter.convert(path)
    return result.document.export_to_markdown()


def _surya_to_text(path):
    """Direct Surya OCR of an image as a secondary strategy (no Docling layout).
    Best-effort and version-tolerant; raises on failure."""
    from PIL import Image
    from surya.recognition import RecognitionPredictor  # lazy import
    from surya.detection import DetectionPredictor

    image = Image.open(path)
    det = DetectionPredictor()
    rec = RecognitionPredictor()
    preds = rec([image], det_predictor=det)
    # Flatten recognised text lines into newline-joined text.
    lines = []
    for page in preds:
        for line in getattr(page, "text_lines", []) or []:
            txt = getattr(line, "text", "")
            if txt:
                lines.append(txt)
    return "\n".join(lines)


def extract_text(path):
    """Get text from a scan using the best available local OCR strategy.
    Returns (text, engine_used). Falls back to the transcript so the pipeline is
    always runnable; the fallback is reported honestly in engine_used."""
    # Strategy 1: Docling (+ Surya).
    try:
        return _docling_to_text(path), "docling+surya"
    except Exception as e:
        log("Docling extract unavailable/failed: %s" % e)
    # Strategy 2: Surya directly.
    try:
        return _surya_to_text(path), "surya-direct"
    except Exception as e:
        log("Surya direct extract unavailable/failed: %s" % e)
    # Strategy 3: text transcript sitting next to the image (offline fallback).
    base = os.path.splitext(path)[0] + ".txt"
    for cand in (base, SAMPLE_TXT):
        if os.path.exists(cand):
            log("OCR engines unavailable — falling back to text transcript %s" % os.path.basename(cand))
            with open(cand, encoding="utf-8") as fh:
                return fh.read(), "transcript-fallback"
    raise RuntimeError("no OCR engine available and no text transcript found for %s" % path)


# --- parsing the extracted text into structured rows -----------------------

_HEADER_KEYS = {
    "test": "test_name", "analyte": "test_name", "name": "test_name",
    "result": "value", "value": "value",
    "unit": "unit", "units": "unit",
    "reference": "reference_range", "range": "reference_range", "interval": "reference_range",
    "flag": "flag_from_report", "abnormal": "flag_from_report",
}


def _split_table_row(line):
    """Split a Markdown table row '| a | b |' into trimmed cells."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _map_columns(header_cells):
    """Map a header row to our field names by keyword, returning {index: field}."""
    mapping = {}
    for i, cell in enumerate(header_cells):
        low = cell.lower()
        for key, field in _HEADER_KEYS.items():
            if key in low:
                mapping[i] = field
                break
    return mapping


def parse_lab_text(text):
    """Turn extracted text into a list of result dicts:
        {test_name, value, unit, reference_range, flag_from_report}
    Prefers a Markdown table (what Docling emits); falls back to a tolerant
    per-line regex. Fields that can't be read are marked 'unparsed' rather than
    guessed."""
    rows = []

    # --- table path: lines containing pipes, with a recognisable header ---
    table_lines = [ln for ln in text.splitlines() if ln.count("|") >= 2]
    header_map = None
    for ln in table_lines:
        cells = _split_table_row(ln)
        if set(cells) <= {"", "---", ":---", "---:", ":---:"}:
            continue  # separator row
        m = _map_columns(cells)
        if header_map is None and "test_name" in m.values() and "value" in m.values():
            header_map = m
            continue
        if header_map is not None:
            row = {"test_name": "unparsed", "value": "unparsed", "unit": "",
                   "reference_range": "", "flag_from_report": ""}
            for idx, field in header_map.items():
                if idx < len(cells):
                    row[field] = cells[idx]
            if row["test_name"] and row["test_name"] != "unparsed":
                rows.append(row)
    if rows:
        return rows

    # --- fallback path: tolerant per-line parse (messy OCR without a table) ---
    # Collapse "13.0 - 17.0" into "13.0-17.0" so ranges are single tokens.
    norm = re.sub(r"(\d)\s*[-–—]\s*(\d)", r"\1-\2", text)
    num_re = re.compile(r"^[<>]?=?\d[\d.,]*$")
    range_re = re.compile(r"^(\d+(?:\.\d+)?-\d+(?:\.\d+)?|[<>]=?\d+(?:\.\d+)?)$")
    flag_re = re.compile(r"^(H|L|HH|LL|High|Low|N)$", re.I)

    for raw in norm.splitlines():
        line = raw.strip().lstrip("#").strip()
        if not line or "|" in line:
            continue
        toks = line.split()
        if len(toks) < 2:
            continue
        # Find the first numeric-looking token; everything before it is the name.
        vidx = next((i for i, t in enumerate(toks) if num_re.match(t)), None)
        if vidx is None or vidx == 0:
            continue  # no value -> not a result line (e.g. a title)
        name = " ".join(toks[:vidx])
        value = toks[vidx]
        rest = toks[vidx + 1:]
        unit = rng = flag = ""
        for t in rest:
            if range_re.match(t) and not rng:
                rng = t
            elif flag_re.match(t) and not flag:
                flag = t.upper()
            elif not unit:
                unit = t
        rows.append({"test_name": name, "value": value, "unit": unit,
                     "reference_range": rng, "flag_from_report": flag})
    return rows


# ============================================================================
# STAGE 2 — FLAG  (deterministic anomaly detection — NO LLM)
# Comparing a number to a printed range is arithmetic. An LLM here would only
# invent ranges, so this stage is pure Python and fully deterministic.
# ============================================================================

def _parse_value(s):
    """Parse a numeric result. Returns float or None if unreadable."""
    if s is None:
        return None
    m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*$", str(s).replace(",", ""))
    return float(m.group(1)) if m else None


def _parse_range(s):
    """Parse a printed reference range into a comparable form.

    Returns one of:
        ("interval", lo, hi)   for "13.0-17.0"
        ("lt", x)              for "<5" / "≤5"   (normal is below x)
        ("gt", x)              for ">40" / "≥40" (normal is above x)
        ("none", )             no range printed
        ("unreadable", )       a range was printed but couldn't be parsed
    """
    if s is None or str(s).strip() == "":
        return ("none",)
    txt = str(s).strip().replace("–", "-").replace("—", "-").replace("≤", "<=").replace("≥", ">=")
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)$", txt)
    if m:
        return ("interval", float(m.group(1)), float(m.group(2)))
    m = re.match(r"^<=?\s*([0-9]+(?:\.[0-9]+)?)$", txt)
    if m:
        return ("lt", float(m.group(1)))
    m = re.match(r"^>=?\s*([0-9]+(?:\.[0-9]+)?)$", txt)
    if m:
        return ("gt", float(m.group(1)))
    return ("unreadable",)


def flag_results(rows):
    """Attach a deterministic `flag` to each result. Returns (rows, abnormal).

    Flags: 'high' | 'low' | 'normal' | 'unparsed' |
           'cannot_assess — no range provided' | 'cannot_assess — range unreadable'
    Crucially: a missing range is NEVER replaced with a guessed one.
    """
    abnormal = []
    for r in rows:
        value = _parse_value(r.get("value"))
        rng = _parse_range(r.get("reference_range"))

        if value is None:
            r["flag"] = "unparsed"
        elif rng[0] == "none":
            r["flag"] = "cannot_assess — no range provided"
        elif rng[0] == "unreadable":
            r["flag"] = "cannot_assess — range unreadable"
        elif rng[0] == "interval":
            lo, hi = rng[1], rng[2]
            r["flag"] = "low" if value < lo else "high" if value > hi else "normal"
        elif rng[0] == "lt":
            r["flag"] = "normal" if value < rng[1] else "high"
        elif rng[0] == "gt":
            r["flag"] = "normal" if value > rng[1] else "low"
        else:
            r["flag"] = "cannot_assess — range unreadable"

        if r["flag"] in ("high", "low"):
            abnormal.append(r)
    return rows, abnormal


# ============================================================================
# STAGE 3 — REASON  (the medical LLM — bounded, decision-support only)
# Input is ONLY the flagged abnormals (plus normals as context). The system
# prompt hard-constrains the model to possibilities + uncertainty, never a
# diagnosis. On any failure we emit an honest placeholder — never fabricated
# medical content.
# ============================================================================

REASON_SYSTEM = (
    "You are a cautious clinical decision-SUPPORT assistant for an EDUCATIONAL "
    "PROTOTYPE. You are NOT a doctor and you do NOT diagnose. Your audience is a "
    "qualified clinician who will verify everything you write.\n\n"
    "Hard rules:\n"
    "  - Offer only POSSIBLE, non-exhaustive categories of contributing factors for "
    "each flagged result. Never name a single definitive cause.\n"
    "  - State uncertainty explicitly and note when a finding is NON-SPECIFIC.\n"
    "  - Never give a diagnosis, treatment, dose, or instruction to the patient.\n"
    "  - End every consideration with a reminder that it requires clinical correlation.\n"
    "  - Base comments only on the values provided; do not invent results or ranges.\n"
    "  - If there are no flagged abnormalities, say plainly that the panel is "
    "unremarkable AND that this does not rule out clinical concerns."
)


def _build_reason_prompt(abnormal, normals):
    """Compose the user message: abnormals to reason about + normals as context."""
    def fmt(r):
        return "- %s: %s %s (ref %s) -> %s" % (
            r.get("test_name"), r.get("value"), r.get("unit", ""),
            r.get("reference_range") or "none", r.get("flag"))

    parts = ["FLAGGED ABNORMAL RESULTS (reason about these):"]
    parts += [fmt(r) for r in abnormal] or ["(none)"]
    parts.append("\nNORMAL / CONTEXT RESULTS (for context only):")
    parts += [fmt(r) for r in normals] or ["(none)"]
    parts.append(
        "\nFor EACH flagged abnormal result, list a few POSSIBLE categories of "
        "contributing factors a clinician might consider. Tag each with an "
        "uncertainty level (low/medium/high) and note if it is non-specific. Do "
        "not diagnose. If nothing is flagged, give the 'unremarkable' statement.")
    return "\n".join(parts)


def reason_about(abnormal, normals, base_url, model, api_key):
    """Call the configurable model over plain HTTP. Returns (text, used_model).

    Vendor-agnostic: this speaks the OpenAI-compatible /chat/completions wire
    format with `requests` (no vendor SDK), so it works with a local Ollama (/v1)
    or any hosted gateway (Groq/Gemini/…) just by swapping --base-url/--model. On
    any error we return a clearly-labelled placeholder and used_model=False — we
    never make up medical content to fill the gap."""
    messages = [{"role": "system", "content": REASON_SYSTEM},
                {"role": "user", "content": _build_reason_prompt(abnormal, normals)}]
    url = base_url.rstrip("/") + "/chat/completions"
    body = {"model": model, "messages": messages, "temperature": 0.2}
    headers = {"Authorization": "Bearer %s" % api_key, "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=180)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        return text, True
    except Exception as e:
        log("reasoning model unavailable (%s)" % e)
        note = ("> _Automated reasoning was not produced (no model reachable at "
                "`%s`, model `%s`)._\n>\n> Configure a local model (e.g. MedGemma/"
                "Meditron via Ollama) or an OpenAI-compatible endpoint and re-run. "
                "No medical content is shown here rather than risk fabricating it.\n\n"
                % (base_url, model))
        # Still enumerate WHAT would be reasoned about, without any medical claims.
        if abnormal:
            note += "Results that would be sent for clinician-reviewed reasoning:\n"
            for r in abnormal:
                note += "- %s: %s %s (ref %s) — flagged **%s**\n" % (
                    r.get("test_name"), r.get("value"), r.get("unit", ""),
                    r.get("reference_range") or "none", r.get("flag"))
        else:
            note += ("No abnormalities were flagged; this does not rule out clinical "
                     "concerns.\n")
        return note, False


# ============================================================================
# Report assembly + console output
# ============================================================================

def _results_table_md(rows):
    out = ["| Test | Value | Unit | Reference range | Report flag | Deterministic flag |",
           "| --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        out.append("| %s | %s | %s | %s | %s | %s |" % (
            r.get("test_name", ""), r.get("value", ""), r.get("unit", ""),
            r.get("reference_range") or "—", r.get("flag_from_report") or "—",
            r.get("flag", "")))
    return "\n".join(out)


def build_report(rows, abnormal, reasoning, used_model, source, engine, model_label):
    """Assemble the final Markdown report. Disclaimer leads and closes it, and the
    reasoning is wrapped as an explicit unverified draft for clinician review."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Coverage details for the limitations section.
    unparsed = [r["test_name"] for r in rows if r.get("flag") == "unparsed"]
    no_range = [r["test_name"] for r in rows if str(r.get("flag", "")).startswith("cannot_assess")]

    md = []
    md.append("> **%s**" % DISCLAIMER)
    md.append("")
    md.append("# Lab report review (DRAFT — for clinician verification)")
    md.append("")
    md.append("- **Source:** %s  |  **OCR engine:** %s  |  **Reasoning model:** %s"
              % (os.path.basename(str(source)), engine, model_label if used_model else "none (placeholder)"))
    md.append("- **Generated:** %s" % ts)
    md.append("- **Status:** UNVERIFIED. Every item below must be checked by a qualified clinician.")
    md.append("")

    # 2. Extracted results
    md.append("## 1. Extracted results")
    md.append("_Reference ranges are taken from the report itself, exactly as printed._")
    md.append("")
    md.append(_results_table_md(rows))
    md.append("")

    # 3. Flagged abnormalities (deterministic, no LLM)
    md.append("## 2. Flagged abnormalities (deterministic — no AI)")
    if abnormal:
        md.append("These were computed by simple arithmetic against the printed ranges:")
        md.append("")
        for r in abnormal:
            md.append("- **%s** = %s %s — **%s** (reference %s)" % (
                r.get("test_name"), r.get("value"), r.get("unit", ""),
                r.get("flag").upper(), r.get("reference_range")))
    else:
        md.append("**None flagged.** No values fell outside their printed reference ranges. "
                  "This does **not** rule out clinical concerns.")
    md.append("")

    # 4. Possible considerations (the bounded LLM draft)
    md.append("## 3. Possible considerations (for clinician review)")
    md.append("> The following is an **unverified, AI-generated draft** of *possibilities to "
              "discuss with a clinician* — not a diagnosis, not exhaustive, and possibly wrong. "
              "A qualified clinician must verify or discard each point.")
    md.append("")
    md.append(reasoning if reasoning.strip() else "_No reasoning produced._")
    md.append("")

    # 5. Limitations & coverage
    md.append("## 4. Limitations & coverage")
    md.append("- **Could not be parsed (value unreadable):** %s"
              % (", ".join(unparsed) if unparsed else "none"))
    md.append("- **No reference range on report (not assessed):** %s"
              % (", ".join(no_range) if no_range else "none"))
    md.append("- Reference ranges were used **as printed on the report**; none were guessed or "
              "substituted.")
    md.append("- The considerations section is **AI-generated and unverified**. This tool is an "
              "educational prototype, not a medical device, and may be wrong.")
    md.append("")
    md.append("---")
    md.append("_%s_" % DISCLAIMER)
    return "\n".join(md) + "\n"


def log(msg):
    """Tiny stderr logger so progress/errors are visible without polluting stdout."""
    print("[medlens] %s" % msg, file=sys.stderr)


def banner(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


# ============================================================================
# Orchestration — hardwired sequential pipeline: extract -> flag -> reason
# ============================================================================

def run_pipeline(input_path, base_url, model, api_key, out_path):
    """Run the three stages in order, printing each, and save the report."""
    # The disclaimer is the very first thing the user sees, every run.
    banner(DISCLAIMER)

    # --- Stage 1: EXTRACT ---
    banner("STAGE 1 — EXTRACT (OCR -> structured values)")
    try:
        text, engine = extract_text(input_path)
    except Exception as e:
        log("extraction failed: %s" % e)
        print("Could not extract any text from %s. Aborting." % input_path)
        return None
    rows = parse_lab_text(text)
    print("OCR engine: %s    parsed %d result row(s)" % (engine, len(rows)))
    print(_results_table_md(rows))

    # --- Stage 2: FLAG (pure python) ---
    banner("STAGE 2 — FLAG (deterministic, no LLM)")
    rows, abnormal = flag_results(rows)
    for r in rows:
        print("  %-22s %-6s %-9s ref %-12s -> %s" % (
            r.get("test_name"), r.get("value"), r.get("unit", ""),
            r.get("reference_range") or "(none)", r.get("flag")))
    print("\nAbnormal (out-of-range): %s"
          % (", ".join("%s=%s(%s)" % (r["test_name"], r["value"], r["flag"]) for r in abnormal)
             or "none flagged"))

    # --- Stage 3: REASON (bounded LLM) ---
    banner("STAGE 3 — REASON (bounded considerations for clinician review)")
    normals = [r for r in rows if r.get("flag") == "normal"]
    reasoning, used_model = reason_about(abnormal, normals, base_url, model, api_key)
    print(reasoning)

    # --- Save report ---
    report = build_report(rows, abnormal, reasoning, used_model,
                          source=input_path, engine=engine, model_label=model)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(report)
    banner("SAVED: %s" % out_path)
    print("Report written (leads with the disclaimer; reasoning marked as an unverified draft).")
    return out_path


def main():
    p = argparse.ArgumentParser(
        description="MEDLENS — educational multi-agent lab-report assistant (NOT clinical).")
    p.add_argument("--input", default=None,
                   help="path to a (synthetic!) lab-report image/PDF; default: generate a sample")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL,
                   help="OpenAI-compatible base URL (default: local Ollama %s)" % DEFAULT_BASE_URL)
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="model id for the reasoning stage (default: %s)" % DEFAULT_MODEL)
    p.add_argument("--api-key", default=DEFAULT_API_KEY,
                   help="API key for the endpoint (ignored by Ollama)")
    p.add_argument("--out", default=DEFAULT_OUT, help="output report path")
    p.add_argument("--regenerate-sample", action="store_true",
                   help="(re)generate the synthetic sample image/transcript and exit")
    args = p.parse_args()

    if args.regenerate_sample:
        img, txt = generate_synthetic_report()
        print("wrote synthetic sample: %s  +  %s" % (img, txt))
        return

    # If no input given, generate (once) and use the synthetic sample.
    input_path = args.input
    if not input_path:
        if not os.path.exists(SAMPLE_IMG) and not os.path.exists(SAMPLE_TXT):
            generate_synthetic_report()
        input_path = SAMPLE_IMG if os.path.exists(SAMPLE_IMG) else SAMPLE_TXT
        log("no --input given; using synthetic sample %s" % os.path.basename(input_path))

    run_pipeline(input_path, args.base_url, args.model, args.api_key, args.out)


if __name__ == "__main__":
    main()
