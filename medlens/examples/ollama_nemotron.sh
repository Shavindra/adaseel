#!/usr/bin/env bash
set -euo pipefail

# Requires local Ollama:
#   ollama serve
#   ollama pull nemotron-3-nano
python -m medlens review \
  --provider ollama \
  --model nemotron \
  --no-pick \
  --out lab_report_review.ollama-nemotron.md
