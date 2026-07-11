# -*- coding: utf-8 -*-
"""Domain logic for MEDLENS — the actual lab work the agent's tools call:

  * generate_synthetic_report  — write a synthetic FBC scan (image + transcript)
  * extract_text / parse_lab_text — OCR a scan and parse it into structured rows
  * flag_results               — DETERMINISTIC high/low/normal (pure Python, no LLM)
  * build_report               — assemble the final Markdown (disclaimer-led)

None of this drives the LLM; the agent (via tools.py) decides when to call it.
"""

import os
import re
import sys
import datetime

from .config import DISCLAIMER


def log(msg):
    print("[medlens] %s" % msg, file=sys.stderr)


HERE = os.path.dirname(os.path.abspath(__file__))
PKG_ROOT = os.path.dirname(HERE)  # the medlens/ project dir
SAMPLE_IMG = os.path.join(PKG_ROOT, "sample_lab_report.png")
SAMPLE_TXT = os.path.join(PKG_ROOT, "sample_lab_report.txt")
DEFAULT_OUT = os.path.join(PKG_ROOT, "lab_report_review.md")


# ============================================================================
# Synthetic sample (FBC/CBC) — fake patient, a few out-of-range values, one row
# with NO printed range, and one unreadable value, so every flag path is exercised.
# ============================================================================

# (test_name, value, unit, reference_range, flag_from_report)
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


def rows_to_markdown_table(rows):
    out = ["| Test | Result | Units | Reference Range | Flag |",
           "| --- | --- | --- | --- | --- |"]
    for name, value, unit, rng, flag in rows:
        out.append("| %s | %s | %s | %s | %s |" % (name, value, unit, rng, flag))
    return "\n".join(out)


def generate_synthetic_report(img_path=SAMPLE_IMG, txt_path=SAMPLE_TXT):
    """Write a synthetic lab-report image + a parallel text transcript. The
    transcript is the OCR-equivalent fallback used when Docling/Surya are absent,
    so the agent is always runnable. Returns (img_path, txt_path)."""
    transcript = "%s\n\n%s\n" % (SAMPLE_HEADER, rows_to_markdown_table(SYNTHETIC_ROWS))
    with open(txt_path, "w", encoding="utf-8") as fh:
        fh.write("# " + DISCLAIMER + "\n\n" + transcript)

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
    except Exception as e:  # image is a convenience; transcript is the canonical input
        log("could not render sample image (%s); transcript still written" % e)
        img_path = None
    return img_path, txt_path


# ============================================================================
# EXTRACT — Docling (+ Surya OCR) with graceful fallback to the text transcript
# ============================================================================

def _docling_to_text(path):
    from docling.document_converter import DocumentConverter  # lazy, heavy
    try:
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import PdfFormatOption, ImageFormatOption
        from docling.datamodel.base_models import InputFormat
        opts = PdfPipelineOptions()
        opts.do_ocr = True
        try:
            from docling.datamodel.pipeline_options import SuryaOcrOptions  # type: ignore
            opts.ocr_options = SuryaOcrOptions()
            log("Docling: using Surya OCR engine")
        except Exception:
            log("Docling: Surya options not in this build; using Docling's default OCR engine")
        # Images need ImageFormatOption (NOT PdfFormatOption); PDFs need PdfFormatOption.
        converter = DocumentConverter(format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=opts),
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=opts)})
    except Exception as e:
        # Don't silently misconfigure — log why we're using the plain converter.
        log("Docling option wiring failed (%s); using default DocumentConverter" % e)
        converter = DocumentConverter()
    return converter.convert(path).document.export_to_markdown()


def _surya_to_text(path):
    from PIL import Image
    from surya.recognition import RecognitionPredictor
    from surya.detection import DetectionPredictor
    preds = RecognitionPredictor()([Image.open(path)], det_predictor=DetectionPredictor())
    lines = []
    for page in preds:
        for line in getattr(page, "text_lines", []) or []:
            if getattr(line, "text", ""):
                lines.append(line.text)
    return "\n".join(lines)


def extract_text(path):
    """Return (text, engine_used) using the best available local OCR, falling
    back to a sibling/sample text transcript so the pipeline always runs."""
    try:
        return _docling_to_text(path), "docling+surya"
    except Exception as e:
        log("Docling extract unavailable/failed: %s" % e)
    try:
        return _surya_to_text(path), "surya-direct"
    except Exception as e:
        log("Surya direct extract unavailable/failed: %s" % e)
    base = os.path.splitext(path)[0] + ".txt"
    for cand in (base, SAMPLE_TXT):
        if os.path.exists(cand):
            log("OCR engines unavailable — falling back to transcript %s" % os.path.basename(cand))
            with open(cand, encoding="utf-8") as fh:
                return fh.read(), "transcript-fallback"
    raise RuntimeError("no OCR engine available and no transcript found for %s" % path)


_HEADER_KEYS = {
    "test": "test_name", "analyte": "test_name", "name": "test_name",
    "result": "value", "value": "value",
    "unit": "unit", "units": "unit",
    "reference": "reference_range", "range": "reference_range", "interval": "reference_range",
    "flag": "flag_from_report", "abnormal": "flag_from_report",
}


def _split_table_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _map_columns(header_cells):
    mapping = {}
    for i, cell in enumerate(header_cells):
        low = cell.lower()
        for key, field in _HEADER_KEYS.items():
            if key in low:
                mapping[i] = field
                break
    return mapping


def parse_lab_text(text):
    """Turn extracted text into result dicts
    {test_name, value, unit, reference_range, flag_from_report}. Prefers a
    Markdown table (Docling's output shape); falls back to a tolerant line parse.
    Unreadable fields are marked 'unparsed', never guessed."""
    rows = []
    table_lines = [ln for ln in text.splitlines() if ln.count("|") >= 2]
    header_map = None
    for ln in table_lines:
        cells = _split_table_row(ln)
        if set(cells) <= {"", "---", ":---", "---:", ":---:"}:
            continue
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
        vidx = next((i for i, t in enumerate(toks) if num_re.match(t)), None)
        if not vidx:
            continue
        name = " ".join(toks[:vidx])
        value = toks[vidx]
        unit = rng = flag = ""
        for t in toks[vidx + 1:]:
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
# FLAG — deterministic, pure Python. Exposed to the agent as a tool so the model
# never does the arithmetic (or invents a range) itself.
# ============================================================================

def _parse_value(s):
    if s is None:
        return None
    m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*$", str(s).replace(",", ""))
    return float(m.group(1)) if m else None


def _parse_range(s):
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
    """Attach a deterministic `flag` to each result and return (rows, abnormal).
    A missing range becomes 'cannot_assess — no range provided'; it is NEVER
    replaced with a guessed range."""
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
# REPORT — Markdown assembly (disclaimer-led; reasoning marked unverified draft)
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


def build_report(rows, abnormal, considerations, source, engine, model_label, limitations=None):
    """Assemble the final Markdown from deterministic rows, flags, and metadata."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    unparsed = [r["test_name"] for r in rows if r.get("flag") == "unparsed"]
    no_range = [r["test_name"] for r in rows if str(r.get("flag", "")).startswith("cannot_assess")]
    extra_limitations = [str(item).strip() for item in (limitations or []) if str(item).strip()]

    md = ["> **%s**" % DISCLAIMER, "",
          "# Lab report review (DRAFT — for clinician verification)", "",
          "- **Source:** %s  |  **OCR engine:** %s  |  **Reasoning model:** %s"
          % (os.path.basename(str(source)), engine, model_label),
          "- **Generated:** %s" % ts,
          "- **Status:** UNVERIFIED. Every item below must be checked by a qualified clinician.", "",
          "## 1. Extracted results",
          "_Reference ranges are taken from the report itself, exactly as printed._", "",
          _results_table_md(rows), "",
          "## 2. Flagged abnormalities (deterministic — no AI)"]
    if abnormal:
        md.append("Computed by arithmetic against the printed ranges:")
        md.append("")
        for r in abnormal:
            md.append("- **%s** = %s %s — **%s** (reference %s)" % (
                r.get("test_name"), r.get("value"), r.get("unit", ""),
                r.get("flag").upper(), r.get("reference_range")))
    else:
        md.append("**None flagged.** No values fell outside their printed ranges. This does "
                  "**not** rule out clinical concerns.")
    md += ["", "## 3. Possible considerations (for clinician review)",
           "> The following is an **unverified, AI-generated draft** of *possibilities to "
           "discuss with a clinician* — not a diagnosis, not exhaustive, and possibly wrong. "
           "A qualified clinician must verify or discard each point.", "",
           considerations.strip() if considerations and considerations.strip() else "_No evidence-backed considerations produced._",
           "", "## 4. Limitations & coverage",
           "- **Could not be parsed (value unreadable):** %s" % (", ".join(unparsed) if unparsed else "none"),
           "- **No reference range on report (not assessed):** %s" % (", ".join(no_range) if no_range else "none"),
           "- Reference ranges were used **as printed**; none were guessed or substituted."]
    for limitation in extra_limitations:
        md.append("- %s" % limitation)
    md += ["- The considerations section is empty unless evidence-backed research agents "
           "produce validated claims. Educational prototype, not a medical device, and may be wrong.", "",
           "---", "_%s_" % DISCLAIMER]
    return "\n".join(md) + "\n"
