# -*- coding: utf-8 -*-
"""Durable run tracing for the deterministic MEDLENS stages.

Normal traces explain control flow and decisions without duplicating source payloads
or exact values. Explicit ``DEBUG=true`` traces additionally store full observable
stage inputs/outputs after recursive secret redaction. Hidden model reasoning is
never stored in either mode.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Callable


RUN_SCHEMA_VERSION = "medlens.run.v1"
TRACE_SCHEMA_VERSION = "medlens.trace.v1"

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_FORBIDDEN_DETAIL_KEYS = {
    "api_key",
    "authorization",
    "credentials",
    "exact_value",
    "input_path",
    "ocr_text",
    "patient",
    "prompt",
    "raw",
    "reasoning",
    "source_path",
    "transcript_path",
}
_SECRET_KEY_NAMES = {
    "api_key",
    "authorization",
    "cookie",
    "credentials",
    "password",
    "secret",
    "set-cookie",
    "token",
}
_HIDDEN_REASONING_KEYS = {
    "chain_of_thought",
    "reasoning",
    "reasoning_content",
    "thinking",
}
_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
    re.compile(r"\bsk-(?:or-v1-)?[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bgsk_[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
)


def utc_now() -> dt.datetime:
    """Return a timezone-aware UTC timestamp."""
    return dt.datetime.now(dt.timezone.utc)


def iso_utc(value: dt.datetime) -> str:
    """Serialize a timestamp as canonical UTC with a ``Z`` suffix."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def make_run_id(now: dt.datetime | None = None) -> str:
    """Create a sortable run identifier with collision-resistant random suffix."""
    stamp = (now or utc_now()).astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return "%s-%s" % (stamp, os.urandom(4).hex())


def validate_run_id(run_id: str) -> str:
    """Validate a user-supplied run ID so it cannot escape the runs directory."""
    candidate = str(run_id or "").strip()
    if not _RUN_ID_RE.fullmatch(candidate):
        raise ValueError("run id must be 1-80 letters, digits, dots, underscores, or hyphens")
    return candidate


def debug_enabled(environment: dict[str, str] | None = None) -> bool:
    """Return whether the explicitly requested local diagnostic mode is enabled."""
    values = environment if environment is not None else os.environ
    return str(values.get("DEBUG", "")).strip().lower() in {"1", "true", "yes", "on"}


def canonical_json(value: Any, *, pretty: bool = True) -> str:
    """Serialize JSON deterministically with UTF-8-safe output and trailing newline."""
    if pretty:
        rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    else:
        rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return rendered + "\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_text(path: str | os.PathLike[str], text: str) -> str:
    """Atomically replace ``path`` and return the written content hash."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".%s." % destination.name, dir=str(destination.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, destination)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return sha256_bytes(text.encode("utf-8"))


def write_json(path: str | os.PathLike[str], value: Any) -> str:
    return atomic_write_text(path, canonical_json(value))


def describe_file(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Return non-identifying input metadata suitable for the run trace."""
    source = Path(path)
    stat = source.stat()
    return {
        "sha256": sha256_file(source),
        "size_bytes": stat.st_size,
        "suffix": source.suffix.lower() or "(none)",
    }


def _validate_details(details: dict[str, Any]) -> None:
    for key in details:
        normalized = str(key).strip().lower()
        if normalized in _FORBIDDEN_DETAIL_KEYS:
            raise ValueError("trace detail key %r is forbidden" % key)


def _redact_string(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted


def redact_for_log(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact credentials and omit hidden reasoning content.

    Explicit, bounded rationale fields are preserved. Provider-specific hidden
    reasoning fields are represented by length/hash metadata only.
    """
    normalized_key = str(key or "").strip().lower()
    if normalized_key in _HIDDEN_REASONING_KEYS:
        rendered = value if isinstance(value, str) else canonical_json(value, pretty=False).rstrip()
        return {
            "character_count": len(rendered),
            "content_omitted": True,
            "sha256": sha256_bytes(rendered.encode("utf-8")),
        }
    if normalized_key in _SECRET_KEY_NAMES or normalized_key.endswith(
        (
            "_api_key",
            "_authorization",
            "_cookie",
            "_credentials",
            "_password",
            "_private_key",
            "_secret",
            "_secret_key",
            "_token",
        )
    ):
        return "[REDACTED_SECRET]"
    if isinstance(value, dict):
        return {str(item_key): redact_for_log(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, list):
        return [redact_for_log(item) for item in value]
    if isinstance(value, tuple):
        return [redact_for_log(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_string(repr(value))


class TraceWriter:
    """Append-only JSONL event writer with stable sequence and reason codes."""

    def __init__(
        self,
        run_dir: str | os.PathLike[str],
        run_id: str,
        clock: Callable[[], dt.datetime] = utc_now,
        debug: bool = False,
    ) -> None:
        self.run_dir = Path(run_dir)
        self.run_id = run_id
        self.clock = clock
        self.path = self.run_dir / "events.jsonl"
        self.debug = debug
        self._sequence = 0
        self._handle = open(self.path, "x", encoding="utf-8", newline="\n")
        self._closed = False

    def emit(
        self,
        *,
        stage: str,
        action: str,
        status: str,
        reason_codes: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("cannot emit to a closed trace")
        supplied_details = details or {}
        if not self.debug:
            _validate_details(supplied_details)
        safe_details = redact_for_log(supplied_details)
        self._sequence += 1
        event = {
            "action": action,
            "details": safe_details,
            "diagnostic_mode": self.debug,
            "event_id": "E%04d" % self._sequence,
            "reason_codes": list(reason_codes or []),
            "run_id": self.run_id,
            "schema_version": TRACE_SCHEMA_VERSION,
            "sequence": self._sequence,
            "stage": stage,
            "status": status,
            "timestamp": iso_utc(self.clock()),
        }
        self._handle.write(canonical_json(event, pretty=False))
        self._handle.flush()
        os.fsync(self._handle.fileno())
        return event

    def close(self) -> None:
        if not self._closed:
            self._handle.close()
            self._closed = True

    def __enter__(self) -> "TraceWriter":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def artifact_record(
    path: str | os.PathLike[str],
    *,
    run_dir: str | os.PathLike[str],
    kind: str,
    media_type: str,
) -> dict[str, Any]:
    """Describe an output artefact without persisting an absolute filesystem path."""
    artefact = Path(path)
    root = Path(run_dir)
    try:
        display_path = str(artefact.resolve().relative_to(root.resolve()))
        external = False
    except ValueError:
        display_path = artefact.name
        external = True
    return {
        "external": external,
        "kind": kind,
        "media_type": media_type,
        "path": display_path,
        "sha256": sha256_file(artefact),
        "size_bytes": artefact.stat().st_size,
    }
