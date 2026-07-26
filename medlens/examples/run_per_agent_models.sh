#!/usr/bin/env bash
set -euo pipefail

python -m medlens review \
  --input examples/reports/renal_profile.csv \
  --provider ollama \
  --model qwen \
  --agent-model report_classification=qwen3.5 \
  --agent-model result_extraction=qwen3.5 \
  --agent-model result_validation=qwen3.5 \
  --agent-model result_flagging=qwen3.5 \
  --no-pick \
  --runs-dir runs \
  "$@"
