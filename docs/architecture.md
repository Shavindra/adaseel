# adaseli — architecture

A four-agent pipeline for exhaustive, falsifiable single-gene research over public
biological databases. The LLM does not run a hardwired script — it **drives** the work
by selecting tools, and the safety-critical parts (the tools themselves, the coverage
tables, the reproducibility diff) are deterministic Python.

---

## 1. High-level flow

```mermaid
flowchart TB
    cmd["python -m adaseli research GENE [-q QUESTION]"]
    cmd --> ORC[orchestrator.run_pipeline]

    subgraph ORIG["Original pipeline (3 agents)"]
        direction LR
        A1["Agent 1 · SEARCH<br/>tool-calling loop<br/>(exhaustive retrieval)"]
        A2["Agent 2 · ANALYSIS<br/>synthesise raw evidence<br/>(no tools)"]
        A3["Agent 3 · REPORT<br/>write report + answer<br/>(no tools)"]
        A1 -->|collected: tool to result| A2
        A2 -->|structured findings| A3
    end

    ORC --> A1
    A3 --> R1[/"{gene}_report.md<br/>+ deterministic<br/>coverage table"/]

    subgraph REV["Agent 4 · REVIEW (optional, default on)"]
        direction TB
        IR["Independent re-run<br/>SEARCH to ANALYSIS to REPORT<br/>(fresh tool + API calls)"]
        CR["Critique pass<br/>Popperian falsifiability audit<br/>vs the ORIGINAL report"]
        IR --> CR
    end

    A3 -.->|review enabled| IR
    R1 -.->|read as input| CR
    CR --> R2[/"{gene}_report_review.md<br/>verdict · reproducibility ·<br/>claim-by-claim audit ·<br/>loopholes · coverage diff ·<br/>independent report appendix"/]

    style R1 fill:#e6f3ff,stroke:#3b82f6
    style R2 fill:#fff1e6,stroke:#f97316
```

The original report is **saved and never modified** before the reviewer runs.

---

## 2. Inside the SEARCH agent — the tool-calling loop

The same loop also powers the reviewer's independent re-run.

```mermaid
flowchart LR
    USER["task: 'Research GENE in ORG'<br/>+ tool schemas"] --> LOOP

    subgraph LOOP["agents/loop.run_tool_loop"]
        direction TB
        STEP["one model turn<br/>providers.llm_step"]
        PARSE{tool_calls<br/>returned?}
        DISP[run_tool dispatcher]
        APPEND["append assistant msg<br/>+ tool results to history"]
        STOP[stop: model is done]
        STEP --> PARSE
        PARSE -->|yes| DISP
        DISP --> APPEND --> STEP
        PARSE -->|no| STOP
    end

    STEP -.->|"turn 1: tool_choice=lookup_uniprot<br/>(forced canonical entry point)<br/>turn N: tool_choice=auto"| PROV

    subgraph PROV["Provider layer<br/>(normalized step shape)"]
        direction TB
        P1[Anthropic Messages]
        P2["Ollama /api/chat"]
        P3[OpenRouter<br/>OpenAI-compatible]
        P4[fake offline]
    end

    subgraph TOOLS["Tool layer (9 tools)"]
        direction TB
        CTX[("shared ctx cache<br/>accession, sequence,<br/>orthodb_group")]
        TD[run_tool dispatcher]
        T1[lookup_uniprot]
        T2[lookup_alphafold]
        T3["compute_hydrophobicity<br/>(LOCAL: Kyte-Doolittle)"]
        T4[search_string]
        T5[lookup_kegg]
        T6[search_geo]
        T7[search_pubmed]
        T8[search_europepmc]
        T9[lookup_orthologs]
        TD <--> CTX
        TD --> T1 & T2 & T3 & T4 & T5 & T6 & T7 & T8 & T9
    end

    DISP --> TD
    T1 --> API1[UniProt REST]
    T2 --> API2[AlphaFold DB]
    T4 --> API4[STRING]
    T5 --> API5[KEGG REST]
    T6 --> API6[NCBI E-utilities]
    T7 --> API7[NCBI E-utilities]
    T8 --> API8[Europe PMC]
    T9 --> API9[OrthoDB]

    LOOP --> COLL[/"collected:<br/>tool to last result"/]
    COLL --> COV["build_coverage_note<br/>(deterministic Python<br/>table appended to report)"]

    style CTX fill:#fef3c7,stroke:#d97706
    style COV fill:#dcfce7,stroke:#16a34a
    style T3 fill:#e0e7ff,stroke:#6366f1
```

Key mechanics:

- **Forced first call.** Turn 1 uses `tool_choice="lookup_uniprot"` so the canonical entry tool always runs (it primes the accession + sequence the others reuse). Subsequent turns are `tool_choice="auto"` so the model can stop when its research is done. Reasoning models don't burn tokens "deciding" the first step.
- **Shared ctx cache.** Tool args like `sequence` and `uniprot_accession` are optional in the schema. The dispatcher fills them from `ctx` (populated by `lookup_uniprot`). A small model never has to copy a 300-aa sequence back through a tool call.
- **Tools never raise.** Every tool returns either real data or `{"error": "..."}`. The agent treats errors as findings (record + move on), not as crashes.

---

## 3. The 4th agent (REVIEW) — independent replication + falsifiability

```mermaid
flowchart LR
    OR1[/Original report/] --> R[REVIEW agent]
    OR2[/Original analysis/] --> R
    OR3[/Original collected<br/>tool results/] --> R

    R --> RR["INDEPENDENT re-run<br/>(re-uses run_search, run_analysis, run_report<br/>with a fresh ctx and message history)"]
    RR --> IND_C[/Independent collected/]
    RR --> IND_A[/Independent analysis/]
    RR --> IND_R[/Independent report/]

    OR3 --> CD["coverage_diff<br/>(deterministic Python:<br/>per-source agree / DIVERGENT)"]
    IND_C --> CD

    OR1 & OR2 & IND_A & CD --> CRITIQUE["critique pass<br/>REVIEW_SYSTEM + REVIEW_TASK<br/>(no tools; pure synthesis)"]

    CRITIQUE --> OUT[/"{gene}_report_review.md<br/>verdict · reproducibility ·<br/>claim-by-claim falsifiability ·<br/>loopholes · what would change<br/>the conclusion · confidence audit ·<br/>+ coverage diff + appendix"/]

    style CD fill:#dcfce7,stroke:#16a34a
    style OUT fill:#fff1e6,stroke:#f97316
```

What the critique looks for (encoded in `REVIEW_SYSTEM`):

- annotation transferred from low-identity orthologs (homology ≠ same function)
- STRING edges sourced from text-mining / co-expression rather than experiment
- expression (GEO) correlation being read as function or causation
- "absence of evidence" reported as "evidence of absence"
- over-interpretation of a single predictor (GRAVY, predicted TM count, AlphaFold pLDDT)
- small-model summarisation errors or unsupported logical leaps in the prose
- divergences between the original and the independent run (flagged as red flags)

For every substantive claim it asks: *what would falsify this? does the evidence actually rule that out? where's the weakest link?* The deterministic coverage diff is the trust anchor — the model cannot fake reproducibility.

---

## 4. Architectural principles (the "method")

| # | Principle | Where it lives |
|---|---|---|
| 1 | **Agents drive, tools are deterministic.** The LLM picks tools; the tools themselves are plain Python that hit public REST APIs (or compute locally). | `tools/registry.py` (dispatcher), `tools/*.py` (one per source) |
| 2 | **Forced canonical entry point.** Turn 1 = `tool_choice="lookup_uniprot"`; reasoning effort isn't wasted choosing the obvious first step. | `agents/loop.py` |
| 3 | **Shared ctx cache.** Derived values (accession, sequence, orthodb group) round-trip through Python, not through the model's tool args. | `tools/registry.py:run_tool` |
| 4 | **Fail-soft tools.** Every tool returns `{...}` or `{"error": "..."}`. Errors are findings, not exceptions. | `http.py`, every `tools/*.py` |
| 5 | **Deterministic coverage tables.** Coverage is computed by Python from the actual `collected` dict — the model cannot claim coverage it didn't get. | `agents/loop.build_coverage_note`, `agents/review.coverage_diff` |
| 6 | **Vendor-agnostic providers.** One normalized step shape (`{text, tool_calls, raw, error?}`) across Anthropic, Ollama (native tools), OpenRouter (OpenAI-compatible). One agent, four backends. | `providers/*.py` |
| 7 | **Independent reviewer with cross-check.** The 4th agent re-runs the whole pipeline fresh, then critiques. Reproducibility is verified by Python diffing collected results, not by the model's word. | `agents/review.py` |
| 8 | **Original report is immutable.** The reviewer writes a separate file; nothing is rewritten in place. | `agents/orchestrator.py` |
| 9 | **Honest about its own limits.** The reviewer states explicitly that its independent run queries the *same* public sources — so it tests reproducibility + reasoning, not source bias. | `config.REVIEW_SYSTEM` |
| 10 | **Pluggable models per role.** `--model` / `--report-model` / `--review-model` let the search/analysis loop run a cheap model while the writer or critic use a stronger one. | `cli.py`, `agents/orchestrator.py` |

---

## 5. Data flow (what gets written where)

```mermaid
flowchart LR
    USER[gene + question] --> ORC[orchestrator]
    ORC --> S[SEARCH] --> COLLECTED1[(collected v1)]
    COLLECTED1 --> AN[ANALYSIS] --> ANALYSIS1[analysis v1]
    ANALYSIS1 --> REP[REPORT]
    COLLECTED1 --> REP
    REP --> COV1[coverage table v1<br/>deterministic]
    REP --> R1[/"{gene}_report.md"/]
    COV1 --> R1

    R1 -.-> REVIEW[REVIEW]
    ANALYSIS1 -.-> REVIEW
    COLLECTED1 -.-> REVIEW

    REVIEW --> S2[SEARCH '] --> COLLECTED2[(collected v2)]
    COLLECTED2 --> AN2[ANALYSIS '] --> ANALYSIS2[analysis v2]
    ANALYSIS2 --> REP2[REPORT '] --> IR1[/independent report/]
    COLLECTED2 --> REP2
    COLLECTED1 & COLLECTED2 --> DIFF[coverage_diff<br/>deterministic]
    DIFF --> CRIT[critique]
    R1 & ANALYSIS1 & ANALYSIS2 --> CRIT
    CRIT --> R2[/"{gene}_report_review.md"/]
    DIFF --> R2
    IR1 --> R2

    style R1 fill:#e6f3ff,stroke:#3b82f6
    style R2 fill:#fff1e6,stroke:#f97316
    style COV1 fill:#dcfce7,stroke:#16a34a
    style DIFF fill:#dcfce7,stroke:#16a34a
```

---

## 6. File map (where each piece lives)

```
adaseli/
  cli.py                 typer CLI: research / check / models / selftest
  config.py              org defaults, model defaults, the 4 agent prompts
  http.py                one shared, fail-soft HTTP helper (timeouts, JSON, errors)
  feedback.py            rich spinner + stage/section banners + coverage tables
  agents/
    orchestrator.py      run_pipeline: search -> analysis -> report -> (review)
    search.py            Agent 1: drives run_tool_loop with SEARCH_SYSTEM
    analysis.py          Agent 2: run_completion (no tools) with ANALYSIS_SYSTEM
    report.py            Agent 3: run_completion (no tools) with REPORT_SYSTEM
    review.py            Agent 4: independent re-run + coverage_diff + critique
    loop.py              run_tool_loop, run_completion, build_coverage_note, format_evidence
  tools/
    registry.py          tool schemas + dispatcher + shared ctx cache + summariser
    sequence.py          UniProt, AlphaFold, compute_hydrophobicity (local)
    network.py           STRING, KEGG
    expression.py        NCBI GEO
    literature.py        PubMed, Europe PMC
    orthology.py         OrthoDB
  providers/
    anthropic_provider.py    Anthropic Messages API over plain HTTP (no SDK)
    ollama_provider.py       Ollama native /api/chat
    openrouter_provider.py   OpenRouter (OpenAI-compatible /chat/completions)
    fake.py                  offline provider for `selftest` (no network/key)
```
