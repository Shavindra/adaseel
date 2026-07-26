# -*- coding: utf-8 -*-
"""Load and hash immutable MEDLENS skill packages."""

from __future__ import annotations

import hashlib
import importlib.resources
import json
from typing import Any

from ..contracts import AGENT_ROLES, ROLE_CONTRACTS


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def load_skill(role: str) -> dict[str, Any]:
    """Load one known role's versioned skill from package resources."""
    if role not in AGENT_ROLES:
        raise ValueError("unknown MEDLENS agent role: %s" % role)
    root = importlib.resources.files("medlens.skills").joinpath(role).joinpath("v1")
    metadata = json.loads(root.joinpath("skill.json").read_text(encoding="utf-8"))
    system_prompt = root.joinpath("system.md").read_text(encoding="utf-8").replace(
        "\r\n", "\n"
    )
    examples = json.loads(root.joinpath("examples.json").read_text(encoding="utf-8"))
    expected_contract, expected_output = ROLE_CONTRACTS[role]
    errors = []
    if metadata.get("role") != role:
        errors.append("skill_role_mismatch")
    if metadata.get("output_contract") != expected_contract:
        errors.append("skill_contract_mismatch")
    if metadata.get("output_name") != expected_output:
        errors.append("skill_output_name_mismatch")
    if not isinstance(examples, list) or not examples:
        errors.append("skill_examples_missing")
    if errors:
        raise ValueError("invalid skill %s: %s" % (role, ", ".join(errors)))
    hashed = "\n".join(
        (
            _canonical_json(metadata),
            system_prompt,
            _canonical_json(examples),
        )
    ).encode("utf-8")
    return {
        "examples": examples,
        "metadata": metadata,
        "role": role,
        "sha256": hashlib.sha256(hashed).hexdigest(),
        "skill_id": metadata["skill_id"],
        "system_prompt": system_prompt,
    }
