# MEDLENS usage examples

These examples exercise the deterministic work completed so far:

```text
extract_lab_report -> flag_results -> deterministic save
```

The current review command does **not** use the selected model to decide workflow
order or write medical considerations. Provider/model configuration is still useful
for testing endpoint resolution now and for the bounded research roles planned in
`docs/MULTI_AGENT_RESEARCH_RUNBOOK.md`.

## One-time local configuration

Copy the example environment file once and edit it with your provider/model choices
and local API keys:

```bash
cp medlens/.env.example .env
$EDITOR .env
```

MEDLENS automatically loads `.env` from the repo root, from `medlens/.env`, or from
the current working directory. Real `.env` files are gitignored, so you do not need
to export `OPENROUTER_API_KEY` every time you run a script.

Defaults are OpenRouter + Nemotron:

```text
MEDLENS_PROVIDER=openrouter
MEDLENS_BASE_URL=https://openrouter.ai/api/v1
MEDLENS_MODEL=nvidia/nemotron-nano-9b-v2:free
```

With that `.env`, this uses OpenRouter Nemotron by default:

```bash
python -m medlens review --no-pick
```

## OpenRouter

Run Qwen via the configured shorthand:

```bash
python -m medlens review --provider openrouter --model qwen --no-pick \
  --out lab_report_review.openrouter-qwen.md
```

Run Nemotron via the configured shorthand:

```bash
python -m medlens review --provider openrouter --model nemotron --no-reasoning \
  --no-pick --out lab_report_review.openrouter-nemotron.md
```

Or use the checked-in helper scripts:

```bash
./examples/openrouter_qwen.sh
./examples/openrouter_nemotron.sh
```

## Ollama

Start Ollama and pull one or both local models:

```bash
ollama serve
ollama pull qwen3.5
ollama pull nemotron-3-nano
```

Run Qwen through Ollama's OpenAI-compatible endpoint:

```bash
python -m medlens review --provider ollama --model qwen --no-pick \
  --out lab_report_review.ollama-qwen.md
```

Run Nemotron through Ollama:

```bash
python -m medlens review --provider ollama --model nemotron --no-pick \
  --out lab_report_review.ollama-nemotron.md
```

Or use the checked-in helper scripts:

```bash
./examples/ollama_qwen.sh
./examples/ollama_nemotron.sh
```

## Endpoint checks

```bash
python -m medlens check --provider openrouter --model qwen
python -m medlens check --provider ollama --model qwen
python -m medlens models --provider openrouter --free --tools
python -m medlens models --provider ollama --tools
```

## Offline deterministic self-test

No API key, model runtime, or network is required:

```bash
python -m medlens selftest --quiet --out /tmp/medlens_flagging_report.md
```
