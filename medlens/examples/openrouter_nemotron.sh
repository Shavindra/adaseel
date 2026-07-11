#!/usr/bin/env bash
set -euo pipefail

# Requires: export OPENROUTER_API_KEY=sk-or-v1-...
# Nemotron is a reasoning-capable model on OpenRouter; --no-reasoning keeps
# diagnostics compact if future model-backed roles are enabled.
python -m medlens review \
  --provider openrouter \
  --model nemotron \
  --no-reasoning \
  --no-pick \
  --out lab_report_review.openrouter-nemotron.md
