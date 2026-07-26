# -*- coding: utf-8 -*-
"""Generic lab-report extraction, parsing, context resolution, and flagging.

The current milestone coordinates bounded classification, extraction, validation,
and flagging agents, then reconciles them against deterministic parsing and range
rules. Report type is metadata, not a hard-coded blood-test domain.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import os
import re
import traceback
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterable

from .config import DISCLAIMER


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
EXAMPLES_ROOT = PROJECT_ROOT / "examples" / "reports"
SAMPLE_IMG = str(EXAMPLES_ROOT / "sample_lab_report.png")
SAMPLE_TXT = str(EXAMPLES_ROOT / "sample_lab_report.txt")
BUNDLED_SAMPLE_TXT = str(HERE / "resources" / "sample_lab_report.txt")
DEFAULT_OUT = "flagging_report.md"

TEXT_SUFFIXES = {".txt", ".md", ".csv", ".tsv"}

# (test_name, value, unit, reference_range, flag_from_report)
SYNTHETIC_ROWS = [
    ("Haemoglobin", "9.8", "g/dL", "13.0-17.0", "L"),
    ("Red Cell Count", "4.1", "10^12/L", "4.5-5.9", "L"),
    ("Haematocrit", "0.31", "L/L", "0.40-0.54", "L"),
    ("Mean Cell Volume", "78", "fL", "80-100", "L"),
    ("White Cell Count", "12.6", "10^9/L", "4.0-11.0", "H"),
    ("Neutrophils", "9.1", "10^9/L", "2.0-7.5", "H"),
    ("Lymphocytes", "2.3", "10^9/L", "1.0-4.0", ""),
    ("Platelets", "178", "10^9/L", "150-400", ""),
    ("C-Reactive Protein", "48", "mg/L", "", ""),
    ("Ferritin", "--", "ug/L", "30-400", ""),
]
SAMPLE_HEADER = (
    "SYNTHETIC SAMPLE — Full Blood Count (FBC)   "
    "Patient: SAMPLE, Test (synthetic, not real)"
)

_EventCallback = Callable[[dict[str, Any]], None]


def _emit(
    callback: _EventCallback | None,
    *,
    action: str,
    status: str,
    reason_codes: list[str] | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    if callback is not None:
        callback(
            {
                "action": action,
                "status": status,
                "reason_codes": list(reason_codes or []),
                "details": details or {},
            }
        )


def rows_to_markdown_table(rows: Iterable[tuple[str, str, str, str, str]]) -> str:
    output = [
        "| Test | Result | Units | Reference Range | Flag |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, value, unit, reference, flag in rows:
        output.append("| %s | %s | %s | %s | %s |" % (name, value, unit, reference, flag))
    return "\n".join(output)


def generate_synthetic_report(
    img_path: str = SAMPLE_IMG,
    txt_path: str = SAMPLE_TXT,
) -> tuple[str | None, str]:
    """Write one synthetic FBC example image and companion transcript."""
    Path(txt_path).parent.mkdir(parents=True, exist_ok=True)
    transcript = "%s\n\n%s\n" % (SAMPLE_HEADER, rows_to_markdown_table(SYNTHETIC_ROWS))
    with open(txt_path, "w", encoding="utf-8") as handle:
        handle.write("# " + DISCLAIMER + "\n\n" + transcript)

    try:
        from PIL import Image, ImageDraw, ImageFont

        font = ImageFont.load_default()
        lines = [
            "SYNTHETIC SAMPLE LAB REPORT  (NOT REAL — EDUCATIONAL PROTOTYPE)",
            "Patient: SAMPLE, Test    DOB: 1900-01-01    MRN: SYN-000000",
            "Specimen: whole blood (EDTA)    Panel: Full Blood Count (FBC)",
            "-" * 78,
            "%-22s %-8s %-9s %-14s %s"
            % ("Test", "Result", "Units", "Ref. Range", "Flag"),
            "-" * 78,
        ]
        for name, value, unit, reference, flag in SYNTHETIC_ROWS:
            lines.append(
                "%-22s %-8s %-9s %-14s %s"
                % (name, value, unit, reference or "(none)", flag)
            )
        lines += ["-" * 78, DISCLAIMER]
        padding, line_height = 16, 16
        image = Image.new("RGB", (640, padding * 2 + line_height * len(lines)), "white")
        draw = ImageDraw.Draw(image)
        for index, line in enumerate(lines):
            draw.text((padding, padding + index * line_height), line, fill="black", font=font)
        Path(img_path).parent.mkdir(parents=True, exist_ok=True)
        image.save(img_path)
    except Exception:
        # The transcript remains a complete offline fixture when Pillow is absent.
        img_path = None
    return img_path, txt_path


def _docling_to_text(path: str) -> str:
    from docling.document_converter import DocumentConverter

    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import ImageFormatOption, PdfFormatOption

        options = PdfPipelineOptions()
        options.do_ocr = True
        try:
            from docling.datamodel.pipeline_options import SuryaOcrOptions  # type: ignore

            options.ocr_options = SuryaOcrOptions()
        except Exception:
            pass
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=options),
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=options),
            }
        )
    except Exception:
        converter = DocumentConverter()
    return converter.convert(path).document.export_to_markdown()


def _surya_to_text(path: str) -> str:
    from PIL import Image
    from surya.detection import DetectionPredictor
    from surya.recognition import RecognitionPredictor

    predictions = RecognitionPredictor()(
        [Image.open(path)], det_predictor=DetectionPredictor()
    )
    lines = []
    for page in predictions:
        for line in getattr(page, "text_lines", []) or []:
            if getattr(line, "text", ""):
                lines.append(line.text)
    return "\n".join(lines)


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8-sig") as handle:
        return handle.read()


def _companion_transcripts(path: str) -> list[str]:
    base = os.path.splitext(path)[0]
    return [base + suffix for suffix in (".txt", ".md", ".csv", ".tsv")]


def extract_text(
    path: str,
    *,
    transcript_path: str | None = None,
    on_event: _EventCallback | None = None,
    debug: bool = False,
) -> tuple[str, str]:
    """Return canonical text and the selected extraction engine.

    Native text and an explicitly supplied transcript are deterministic first-class
    inputs. Image/PDF inputs may use a same-stem transcript; otherwise local OCR is
    attempted. MEDLENS never substitutes its bundled sample transcript for an
    unrelated input.
    """
    source = Path(path)
    if not source.is_file():
        _emit(
            on_event,
            action="input_validation_failed",
            status="failed",
            reason_codes=["input_not_found"],
        )
        raise FileNotFoundError("input report does not exist")

    if source.suffix.lower() in TEXT_SUFFIXES:
        _emit(
            on_event,
            action="text_input_selected",
            status="completed",
            reason_codes=["native_text_input"],
            details={"suffix": source.suffix.lower()},
        )
        return _read_text(str(source)), "native-text"

    if transcript_path is not None:
        transcript = Path(transcript_path)
        if not transcript.is_file():
            _emit(
                on_event,
                action="transcript_validation_failed",
                status="failed",
                reason_codes=["transcript_not_found"],
            )
            raise FileNotFoundError("supplied transcript does not exist")
        _emit(
            on_event,
            action="companion_transcript_selected",
            status="completed",
            reason_codes=["user_supplied_transcript"],
            details={"suffix": transcript.suffix.lower() or "(none)"},
        )
        return _read_text(str(transcript)), "user-supplied-transcript"

    for candidate in _companion_transcripts(str(source)):
        if os.path.isfile(candidate):
            _emit(
                on_event,
                action="companion_transcript_selected",
                status="completed",
                reason_codes=["same_stem_transcript"],
                details={"suffix": Path(candidate).suffix.lower()},
            )
            return _read_text(candidate), "same-stem-transcript"

    for engine_name, extractor in (
        ("docling", _docling_to_text),
        ("surya-direct", _surya_to_text),
    ):
        _emit(
            on_event,
            action="extractor_attempted",
            status="started",
            details={"engine": engine_name},
        )
        try:
            text = extractor(str(source))
        except Exception as error:
            failure_details = {"engine": engine_name, "error_type": type(error).__name__}
            if debug:
                failure_details["error_message"] = str(error)
                failure_details["exception_traceback"] = traceback.format_exc()
            _emit(
                on_event,
                action="extractor_failed",
                status="failed",
                reason_codes=["extractor_unavailable_or_failed"],
                details=failure_details,
            )
            continue
        if text and text.strip():
            _emit(
                on_event,
                action="extractor_completed",
                status="completed",
                reason_codes=["ocr_text_extracted"],
                details={"engine": engine_name, "character_count": len(text)},
            )
            return text, engine_name
        _emit(
            on_event,
            action="extractor_failed",
            status="failed",
            reason_codes=["extractor_returned_empty_text"],
            details={"engine": engine_name},
        )

    raise RuntimeError(
        "no text or companion transcript was available and no local OCR extractor succeeded"
    )


def _normalise_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _header_field(value: str) -> str | None:
    header = _normalise_header(value)
    if not header:
        return None
    if any(term in header for term in ("lower limit", "lower bound", "reference low")):
        return "reference_low"
    if any(term in header for term in ("upper limit", "upper bound", "reference high")):
        return "reference_high"
    if any(term in header for term in ("reference", "ref range", "normal range", "interval")):
        return "reference_range"
    if any(term in header for term in ("reported flag", "abnormal flag")) or header == "flag":
        return "flag_from_report"
    if header in {"unit", "units"} or " unit" in " " + header:
        return "unit"
    if any(term == header or term in header for term in ("test", "analyte", "investigation")):
        return "test_name"
    if any(term == header or term in header for term in ("result", "value", "finding")):
        return "value"
    return None


def _map_columns(cells: list[str]) -> dict[int, str]:
    mapping: dict[int, str] = {}
    used: set[str] = set()
    for index, cell in enumerate(cells):
        field = _header_field(cell)
        if field and field not in used:
            mapping[index] = field
            used.add(field)
    return mapping


def _is_table_separator(cells: list[str]) -> bool:
    return bool(cells) and all(
        not cell or re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells
    )


def _row_from_cells(cells: list[str], mapping: dict[int, str]) -> dict[str, str] | None:
    row = {
        "test_name": "",
        "value": "",
        "unit": "",
        "reference_range": "",
        "flag_from_report": "",
    }
    bounds: dict[str, str] = {}
    for index, field in mapping.items():
        if index >= len(cells):
            continue
        value = cells[index].strip()
        if field in {"reference_low", "reference_high"}:
            bounds[field] = value
        else:
            row[field] = value
    if not row["reference_range"] and bounds.get("reference_low") and bounds.get("reference_high"):
        row["reference_range"] = "%s-%s" % (
            bounds["reference_low"],
            bounds["reference_high"],
        )
    if not row["test_name"]:
        return None
    return row


def _rows_from_markdown(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    mapping: dict[int, str] | None = None
    for line in text.splitlines():
        if line.count("|") < 2:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if _is_table_separator(cells):
            continue
        candidate = _map_columns(cells)
        if "test_name" in candidate.values() and "value" in candidate.values():
            mapping = candidate
            continue
        if mapping:
            row = _row_from_cells(cells, mapping)
            if row:
                rows.append(row)
    return rows


def _rows_from_delimited(text: str) -> tuple[list[dict[str, str]], str | None]:
    for delimiter, label in (("\t", "tsv"), (",", "csv")):
        parsed = list(csv.reader(io.StringIO(text), delimiter=delimiter))
        mapping: dict[int, str] | None = None
        rows: list[dict[str, str]] = []
        for cells in parsed:
            candidate = _map_columns([str(cell) for cell in cells])
            if mapping is None and "test_name" in candidate.values() and "value" in candidate.values():
                mapping = candidate
                continue
            if mapping:
                row = _row_from_cells([str(cell) for cell in cells], mapping)
                if row:
                    rows.append(row)
        if rows:
            return rows, label
    return [], None


_NUMBER_TOKEN = re.compile(r"^[<>]?=?[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_RANGE_TOKEN = re.compile(
    r"^(?:[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*[-–—]\s*"
    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)|[<>]=?\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+))$"
)
_FLAG_TOKEN = re.compile(r"^(H|L|HH|LL|High|Low|N|Normal)$", re.I)


def _rows_from_lines(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    normalized = re.sub(r"(\d)\s*[–—]\s*(\d)", r"\1-\2", text)
    for raw in normalized.splitlines():
        line = raw.strip().lstrip("#").strip()
        if not line or "|" in line:
            continue
        tokens = line.split()
        if len(tokens) < 2:
            continue
        value_index = next(
            (index for index, token in enumerate(tokens) if _NUMBER_TOKEN.fullmatch(token)),
            None,
        )
        if value_index in (None, 0):
            continue
        name = " ".join(tokens[:value_index]).strip()
        value = tokens[value_index]
        unit = reference = reported_flag = ""
        for token in tokens[value_index + 1 :]:
            if _RANGE_TOKEN.fullmatch(token) and not reference:
                reference = token
            elif _FLAG_TOKEN.fullmatch(token) and not reported_flag:
                reported_flag = token.upper()
            elif not unit:
                unit = token
        rows.append(
            {
                "test_name": name,
                "value": value,
                "unit": unit,
                "reference_range": reference,
                "flag_from_report": reported_flag,
            }
        )
    return rows


def parse_lab_text(
    text: str,
    *,
    on_event: _EventCallback | None = None,
) -> list[dict[str, str]]:
    """Parse a generic laboratory result table without assuming a panel type."""
    rows = _rows_from_markdown(text)
    parser = "markdown_table"
    if not rows:
        rows, parser = _rows_from_delimited(text)
    if not rows:
        rows = _rows_from_lines(text)
        parser = "line_parser"
    _emit(
        on_event,
        action="parser_completed",
        status="completed" if rows else "failed",
        reason_codes=["result_rows_parsed"] if rows else ["no_result_rows"],
        details={"parser": parser or "none", "result_count": len(rows)},
    )
    return rows


def _clean_report_type(value: str) -> str:
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value))
    cleaned = re.split(r"\s{2,}|\bPatient\s*:", cleaned, maxsplit=1, flags=re.I)[0]
    cleaned = cleaned.strip(" \t#|:—-")
    return cleaned[:120].strip()


_TYPE_SIGNATURES = [
    (
        "Full Blood Count (FBC/CBC)",
        {"haemoglobin", "white cell count", "platelets"},
        "signature_full_blood_count",
    ),
    (
        "Renal function panel",
        {"creatinine", "urea", "sodium", "potassium"},
        "signature_renal_function",
    ),
    (
        "Liver function panel",
        {"alanine aminotransferase", "alkaline phosphatase", "bilirubin"},
        "signature_liver_function",
    ),
    (
        "Thyroid function panel",
        {"thyroid stimulating hormone", "free t4"},
        "signature_thyroid_function",
    ),
]


def _document_report_label(text: str) -> str:
    patterns = (
        r"(?im)^\s*(?:report\s*type|panel|profile|investigation)\s*:\s*([^\n|]+)",
        r"(?im)^\s*(?:#+\s*)?SYNTHETIC\s+SAMPLE\s*[—-]\s*([^\n|]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            label = _clean_report_type(match.group(1))
            if label:
                return label

    generic = {
        "educational prototype",
        "lab report",
        "laboratory report",
        "results",
        "test results",
    }
    for raw_line in text.splitlines()[:40]:
        line = raw_line.strip()
        if not line or "|" in line:
            continue
        heading = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading:
            label = _clean_report_type(heading.group(1))
            if label and label.lower() not in generic and "not for clinical use" not in label.lower():
                return label
        if re.search(r"\b(panel|profile|screen|assay|analysis)\b", line, re.I):
            label = _clean_report_type(line)
            if label and label.lower() not in generic:
                return label
    return ""


def determine_report_type(
    text: str,
    rows: list[dict[str, Any]],
    *,
    specified_type: str | None = None,
    on_event: _EventCallback | None = None,
) -> dict[str, str]:
    """Resolve report type without forcing the document into a fixed taxonomy."""
    if specified_type is not None:
        label = _clean_report_type(specified_type)
        if not label:
            raise ValueError("report type must contain visible text")
        result = {
            "label": label,
            "source": "user",
            "reason_code": "report_type_user_supplied",
        }
    else:
        label = _document_report_label(text)
        if label:
            result = {
                "label": label,
                "source": "document",
                "reason_code": "report_type_document_label",
            }
        else:
            names = {
                re.sub(r"\s+", " ", str(row.get("test_name", "")).strip().lower())
                for row in rows
            }
            matched = next(
                (
                    (signature_label, reason)
                    for signature_label, required, reason in _TYPE_SIGNATURES
                    if required.issubset(names)
                ),
                None,
            )
            if matched:
                result = {
                    "label": matched[0],
                    "source": "deterministic_signature",
                    "reason_code": matched[1],
                }
            else:
                result = {
                    "label": "Unspecified laboratory report",
                    "source": "unknown",
                    "reason_code": "report_type_not_determined",
                }
    type_rationales = {
        "report_type_user_supplied": "The explicit user-supplied report type takes precedence.",
        "report_type_document_label": "A report or panel label was found in the supplied document text.",
        "signature_full_blood_count": "The parsed test-name set matched the complete deterministic FBC signature.",
        "signature_renal_function": "The parsed test-name set matched the complete deterministic renal signature.",
        "signature_liver_function": "The parsed test-name set matched the complete deterministic liver signature.",
        "signature_thyroid_function": "The parsed test-name set matched the complete deterministic thyroid signature.",
        "report_type_not_determined": "No explicit label or complete deterministic signature was available, so no type was guessed.",
    }
    _emit(
        on_event,
        action="report_type_resolved",
        status="completed",
        reason_codes=[result["reason_code"]],
        details={
            "alternatives_considered": [
                "user_supplied",
                "document_label",
                "deterministic_signature",
                "unresolved",
            ],
            "assumptions": [
                "Report type is context only and does not change result flagging."
            ],
            "decision_id": "report_type",
            "label": result["label"],
            "outcome": result["source"],
            "rationale": type_rationales[result["reason_code"]],
            "source": result["source"],
            "uncertainties": (
                ["The report type remains unresolved."]
                if result["source"] == "unknown"
                else []
            ),
        },
    )
    return result


_DECIMAL = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"


def _parse_value(value: Any) -> Decimal | None:
    text = str(value if value is not None else "").strip().replace(",", "")
    if not re.fullmatch(_DECIMAL, text):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _parse_range(value: Any) -> tuple[Any, ...]:
    text = str(value if value is not None else "").strip()
    if not text:
        return ("none",)
    text = (
        text.replace(",", "")
        .replace("–", "-")
        .replace("—", "-")
        .replace("≤", "<=")
        .replace("≥", ">=")
    )
    interval = re.fullmatch(r"\s*(%s)\s*-\s*(%s)\s*" % (_DECIMAL, _DECIMAL), text)
    if interval:
        try:
            lower = Decimal(interval.group(1))
            upper = Decimal(interval.group(2))
        except InvalidOperation:
            return ("unreadable",)
        if lower > upper:
            return ("unreadable",)
        return ("interval", lower, upper)
    bound = re.fullmatch(r"\s*(<=|<|>=|>)\s*(%s)\s*" % _DECIMAL, text)
    if bound:
        try:
            threshold = Decimal(bound.group(2))
        except InvalidOperation:
            return ("unreadable",)
        return ("upper" if bound.group(1).startswith("<") else "lower", bound.group(1), threshold)
    return ("unreadable",)


def _assess_row(row: dict[str, Any]) -> tuple[str, str, str]:
    raw_value = str(row.get("value") if row.get("value") is not None else "").strip()
    numeric_value = _parse_value(raw_value)
    reference = _parse_range(row.get("reference_range"))
    if numeric_value is None:
        if re.fullmatch(r"[<>]=?\s*%s" % _DECIMAL, raw_value):
            return (
                "cannot_assess — qualified value unsupported",
                "qualified_value_unsupported",
                "not_assessed",
            )
        if raw_value and raw_value not in {"-", "--", "—"}:
            return (
                "cannot_assess — qualitative result unsupported",
                "qualitative_value_unsupported",
                "not_assessed",
            )
        return "unparsed", "value_unreadable", "not_assessed"
    if reference[0] == "none":
        return "cannot_assess — no range provided", "reference_missing", "not_assessed"
    if reference[0] == "unreadable":
        return "cannot_assess — range unsupported", "reference_unreadable", "not_assessed"
    if reference[0] == "interval":
        lower, upper = reference[1], reference[2]
        if numeric_value < lower:
            return "low", "value_below_interval", "deterministic_numeric_range"
        if numeric_value > upper:
            return "high", "value_above_interval", "deterministic_numeric_range"
        return "normal", "value_within_interval", "deterministic_numeric_range"
    if reference[0] == "upper":
        operator, threshold = reference[1], reference[2]
        normal = numeric_value <= threshold if operator == "<=" else numeric_value < threshold
        if normal:
            return "normal", "value_satisfies_upper_limit", "deterministic_numeric_range"
        return "high", "value_exceeds_upper_limit", "deterministic_numeric_range"
    if reference[0] == "lower":
        operator, threshold = reference[1], reference[2]
        normal = numeric_value >= threshold if operator == ">=" else numeric_value > threshold
        if normal:
            return "normal", "value_satisfies_lower_limit", "deterministic_numeric_range"
        return "low", "value_below_lower_limit", "deterministic_numeric_range"
    return "cannot_assess — range unsupported", "reference_unreadable", "not_assessed"


def flag_results(
    rows: list[dict[str, Any]],
    *,
    on_event: _EventCallback | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Assess numeric values only against their own printed reference intervals."""
    rationale_by_reason = {
        "value_below_interval": "The numeric value is below the row's supplied lower bound.",
        "value_above_interval": "The numeric value is above the row's supplied upper bound.",
        "value_within_interval": "The numeric value is inside the row's supplied closed interval.",
        "value_satisfies_upper_limit": "The numeric value satisfies the row's supplied upper-limit comparator.",
        "value_exceeds_upper_limit": "The numeric value fails the row's supplied upper-limit comparator.",
        "value_satisfies_lower_limit": "The numeric value satisfies the row's supplied lower-limit comparator.",
        "value_below_lower_limit": "The numeric value fails the row's supplied lower-limit comparator.",
        "qualified_value_unsupported": "The value contains an inequality qualifier and no censoring rule was applied.",
        "qualitative_value_unsupported": "The result is qualitative, so the numeric range assessor abstained.",
        "value_unreadable": "The result is blank or unreadable, so no numeric decision was possible.",
        "reference_missing": "The row supplies no reference interval, so MEDLENS did not invent one.",
        "reference_unreadable": "The supplied reference interval is not supported by the deterministic numeric grammar.",
    }
    assessed: list[dict[str, Any]] = []
    abnormal: list[dict[str, Any]] = []
    for index, original in enumerate(rows, 1):
        row = dict(original)
        row.setdefault("result_id", "R%04d" % index)
        flag, reason, method = _assess_row(row)
        row["flag"] = flag
        row["flag_reason_code"] = reason
        row["assessment_method"] = method
        assessed.append(row)
        if flag in {"high", "low"}:
            abnormal.append(row)
        _emit(
            on_event,
            action="result_assessed",
            status="completed",
            reason_codes=[reason],
            details={
                "alternatives_considered": [
                    "high",
                    "low",
                    "normal",
                    "cannot_assess",
                    "unparsed",
                ],
                "assessment_method": method,
                "assumptions": (
                    [
                        "The supplied reference interval belongs to this result row.",
                        "No demographic or clinical context is required by the numeric rule.",
                    ]
                    if method == "deterministic_numeric_range"
                    else []
                ),
                "decision_id": "flag:%s" % row["result_id"],
                "flag": flag,
                "outcome": flag,
                "rationale": rationale_by_reason[reason],
                "result_id": row["result_id"],
                "test_name": row.get("test_name", ""),
                "uncertainties": (
                    []
                    if method == "deterministic_numeric_range"
                    else ["No deterministic high/low/normal assessment was made."]
                ),
            },
        )
    return assessed, abnormal


def _escape_markdown(value: Any) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value if value is not None else ""))
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")


def _results_table_md(rows: list[dict[str, Any]]) -> str:
    output = [
        "| ID | Test | Value | Unit | Reference range | Reported flag | Deterministic flag | Reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        output.append(
            "| %s | %s | %s | %s | %s | %s | %s | `%s` |"
            % (
                _escape_markdown(row.get("result_id", "")),
                _escape_markdown(row.get("test_name", "")),
                _escape_markdown(row.get("value", "")),
                _escape_markdown(row.get("unit", "")),
                _escape_markdown(row.get("reference_range") or "—"),
                _escape_markdown(row.get("flag_from_report") or "—"),
                _escape_markdown(row.get("flag", "")),
                _escape_markdown(row.get("flag_reason_code", "")),
            )
        )
    return "\n".join(output)


def build_flagging_report(
    rows: list[dict[str, Any]],
    abnormal: list[dict[str, Any]],
    *,
    report_context: dict[str, str],
    engine: str,
    run_id: str,
    trace_ref: str,
    limitations: list[str] | None = None,
    generated_at: str | None = None,
    debug_mode: bool = False,
    agent_invocations: list[dict[str, Any]] | None = None,
    handoffs: list[dict[str, Any]] | None = None,
) -> str:
    """Render the optional human-readable multi-agent flagging output."""
    timestamp = generated_at or dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    unparsed = [row["result_id"] for row in rows if row.get("flag") == "unparsed"]
    not_assessed = [
        row["result_id"] for row in rows if str(row.get("flag", "")).startswith("cannot_assess")
    ]
    content = [
        "> **%s**" % DISCLAIMER,
        "",
        "# Lab report flagging results",
        "",
        "- **Run:** `%s`" % _escape_markdown(run_id),
        "- **Report type:** %s (`%s`)"
        % (
            _escape_markdown(report_context.get("label", "Unspecified laboratory report")),
            _escape_markdown(report_context.get("source", "unknown")),
        ),
        "- **Extraction source:** %s" % _escape_markdown(engine),
        "- **Generated:** %s" % _escape_markdown(timestamp),
        "- **Pipeline stop:** accepted flagging after bounded multi-agent execution; "
        "no evidence research or medical interpretation ran",
        "",
        "## Extracted and assessed results",
        "",
        "_Reference ranges are taken only from the supplied report/transcript._",
        "",
        _results_table_md(rows),
        "",
        "## Deterministically flagged results",
        "",
    ]
    if abnormal:
        for row in abnormal:
            content.append(
                "- **%s** (`%s`) — **%s**; reason `%s`."
                % (
                    _escape_markdown(row.get("test_name", "")),
                    _escape_markdown(row.get("result_id", "")),
                    _escape_markdown(str(row.get("flag", "")).upper()),
                    _escape_markdown(row.get("flag_reason_code", "")),
                )
            )
    else:
        content.append(
            "**No numeric result was outside its supplied reference interval.** "
            "This statement does not interpret clinical significance."
        )
    content += [
        "",
        "## Multi-agent execution",
        "",
        "Every role is constrained by a versioned structured contract; deterministic "
        "checks remained authoritative when an agent failed or disagreed.",
        "",
        "| Role | Provider | Model | Skill | Final status |",
        "| --- | --- | --- | --- | --- |",
    ]
    latest_by_role: dict[str, dict[str, Any]] = {}
    for invocation in agent_invocations or []:
        latest_by_role[invocation.get("role", "")] = invocation
    for role in (
        "report_classification",
        "result_extraction",
        "result_validation",
        "result_flagging",
    ):
        invocation = latest_by_role.get(role, {})
        content.append(
            "| %s | %s | %s | `%s` | %s |"
            % (
                _escape_markdown(role),
                _escape_markdown(invocation.get("provider") or "unavailable"),
                _escape_markdown(invocation.get("model") or "unavailable"),
                _escape_markdown(invocation.get("skill_id") or "not run"),
                _escape_markdown(invocation.get("status") or "not run"),
            )
        )
    content += [
        "",
        "- Structured hand-offs recorded: %d." % len(handoffs or []),
        "- Agent artefacts that failed validation or disagreed with deterministic "
        "checks were retained in the audit files but did not alter canonical results.",
        "",
        "## Limitations and traceability",
        "",
        "- Unreadable values: %s." % (", ".join(unparsed) if unparsed else "none"),
        "- Results not assessed because the reference interval was absent or unsupported: %s."
        % (", ".join(not_assessed) if not_assessed else "none"),
        "- Report-provided flags are preserved for comparison but never control the deterministic flag.",
    ]
    for limitation in limitations or []:
        content.append("- %s" % _escape_markdown(limitation))
    content += [
        "- Detailed action and decision trace: `%s`." % _escape_markdown(trace_ref),
        (
            "- DEBUG=true trace includes full observable stage inputs/outputs after "
            "secret redaction; hidden chain-of-thought remains omitted."
            if debug_mode
            else "- The trace records agent invocations, skills, models, hand-offs, "
            "explicit rationales, reason codes, timings, counts, and hashes; it excludes "
            "OCR text, exact values, identifiers, secrets, and hidden chain-of-thought."
        ),
        "",
        "---",
        "_%s_" % DISCLAIMER,
    ]
    return "\n".join(content) + "\n"
