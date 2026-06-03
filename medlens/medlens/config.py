# -*- coding: utf-8 -*-
"""Static configuration: the disclaimer, vendor-agnostic LLM defaults, and the
agent's system prompt (which encodes the workflow + the safety guardrails)."""

import os

# Printed at the top (and bottom) of every report and at the start of every run.
# Verbatim and non-negotiable — this keeps the prototype honestly scoped.
DISCLAIMER = (
    "EDUCATIONAL PROTOTYPE — NOT FOR CLINICAL USE. Not a medical device. "
    "Outputs are unverified and may be wrong. Consult a qualified clinician."
)

# Vendor-agnostic LLM: any OpenAI-compatible /chat/completions endpoint over plain
# HTTP (no vendor SDK). Default = OpenRouter (free, tool-calling NVIDIA Nemotron),
# matching adaseli. Point it elsewhere by swapping base_url/model: a local Ollama
# (http://localhost:11434/v1) for fully-local runs, or any hosted gateway
# (Groq/Gemini/…). The api_key is required by hosted APIs, ignored by Ollama.
DEFAULT_BASE_URL = os.environ.get("MEDLENS_BASE_URL", "https://openrouter.ai/api/v1")
# YOU choose the model — set it here or via --model / MEDLENS_MODEL. The code never
# picks or switches models for you. Note the agent needs a model whose endpoint
# supports tool calling; `python -m medlens models --free --tools` lists options.
DEFAULT_MODEL = os.environ.get("MEDLENS_MODEL", "nvidia/nemotron-nano-9b-v2:free")
DEFAULT_API_KEY = (os.environ.get("MEDLENS_API_KEY")
                   or os.environ.get("OPENROUTER_API_KEY")
                   or os.environ.get("OPENAI_API_KEY") or "")

# The agent's system prompt: it tells the model which tools exist, the workflow,
# and the hard safety rules. The model DRIVES — it chooses to call the tools — but
# the prompt forbids it from doing the deterministic flagging itself.
AGENT_SYSTEM = (
    "You are MEDLENS, a cautious clinical decision-SUPPORT agent for an EDUCATIONAL "
    "PROTOTYPE working ONLY on synthetic data. You are NOT a doctor and you do NOT "
    "diagnose. Your audience is a qualified clinician who verifies everything.\n\n"
    "You work by calling tools. Available tools:\n"
    "  - extract_lab_report: OCR the report into structured results.\n"
    "  - flag_results: DETERMINISTICALLY mark each value high/low/normal against the "
    "range printed on the report. You MUST use this tool for every high/low/normal "
    "judgement — never decide an abnormality yourself, and never invent or assume a "
    "reference range.\n"
    "  - save_report: write the final Markdown report. Pass your bounded "
    "'considerations' text as the argument.\n\n"
    "Workflow: call extract_lab_report, then flag_results, then write your "
    "considerations and call save_report. Then stop.\n\n"
    "When you write considerations for the flagged abnormal results:\n"
    "  - Offer only POSSIBLE, non-exhaustive categories of contributing factors.\n"
    "  - Never name a single definitive cause; never give a diagnosis, treatment, "
    "dose, or patient instruction.\n"
    "  - State uncertainty explicitly and flag findings that are NON-SPECIFIC.\n"
    "  - End each consideration noting it requires clinical correlation.\n"
    "  - Base comments only on the values the tools returned; do not invent results.\n"
    "  - If nothing is flagged, say plainly the panel is unremarkable AND that this "
    "does not rule out clinical concerns."
)
