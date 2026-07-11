#!/usr/bin/env bash
set -euo pipefail

# Requires: export OPENROUTER_API_KEY=sk-or-v1-...
python -m medlens review \
  --provider openrouter \
  --model qwen \
  --no-pick \
  --out lab_report_review.openrouter-qwen.md
