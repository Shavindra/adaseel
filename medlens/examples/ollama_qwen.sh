#!/usr/bin/env bash
set -euo pipefail

# Requires local Ollama:
#   ollama serve
#   ollama pull qwen3.5
python -m medlens review \
  --provider ollama \
  --model qwen \
  --no-pick \
  --out lab_report_review.ollama-qwen.md
