---
name: adaseli-v2-runbook
overview: Staged v2 redesign preserving the `adaseli research` CLI while replacing model-controlled retrieval and prose handoffs with validated entity resolution, deterministic evidence collection, typed claim provenance, bounded LLM review, and reproducible artifacts. Targets exploratory and publication-support research; clinical/diagnostic use remains explicitly unsupported.
todos:
  - id: p0-baseline-governance
    content: >-
      PR 1 — Add legally redistributable offline fixtures for TP53, LGALS1/GAL1,
      slr1634, sparse/noncoding genes, and cross-taxon symbol collisions; encode
      current failures as regression tests; add Apache-2.0 licensing, OSS policy
      files, source-term documentation, pytest/ruff/mypy, and Python 3.10–3.13
      offline CI. Done when CI needs no network or provider key and every known
      identity, coverage, and citation failure has a deterministic test.
    status: pending
  - id: p1-core-contracts
    content: >-
      PR 2 — Add versioned Pydantic v2 models for ResolvedEntity, EvidenceRecord,
      Claim, evidence edges, provider traces, source plans, and RunManifest;
      export JSON schemas and deterministic content-hash helpers. Done when all
      contracts round-trip, reject unknown/invalid states, and produce stable
      hashes for semantically identical normalized data.
    status: pending
  - id: p1-artifact-store
    content: >-
      PR 3 — Implement immutable per-run artifact directories, atomic JSON/raw
      writes, run locking, redaction, output hashes, software/model/prompt/source
      metadata, and a legacy report convenience copy. Done when interrupted writes
      cannot appear valid, canonical runs cannot be overwritten, and a saved run
      can be inspected without network access.
    status: pending
  - id: p2-entity-resolution
    content: >-
      PR 4 — Build taxon-first NCBI Gene, UniProt, Ensembl, and human HGNC entity
      resolution; derive organism-specific source IDs; rank canonical records;
      expose ambiguity candidates; remove taxon-free fallback; validate deprecated
      organism overrides. Done when the curated set has zero silent cross-taxon
      resolutions and ambiguous/mismatched input stops before API research or LLM use.
    status: pending
  - id: p3-source-protocol
    content: >-
      PR 5 — Define SourceAdapter, SourceQuery, SourceResult, capabilities,
      source metadata, rate policy, and entry-point registration; retain the old
      tool registry as a compatibility facade. Done when a third-party source can
      register without editing core dispatch and all statuses distinguish success,
      empty, partial, error, and justified skipped.
    status: pending
  - id: p3-retrieval-engine
    content: >-
      PR 6 — Generate deterministic source plans from the resolved entity, execute
      applicable adapters concurrently with per-host limits/retries, persist raw
      responses before parsing, sort normalized records, and append rather than
      overwrite repeated queries. Done when complete source accounting is identical
      with LLMs disabled and every planned source has an explicit terminal status.
    status: pending
  - id: p4-core-source-adapters
    content: >-
      PR 7 — Migrate UniProt, AlphaFold, hydrophobicity, and KEGG to typed v2
      adapters with exact taxon/accession checks, model/version provenance,
      prediction-versus-experiment labels, and granular empty/error states. Done
      when pLDDT and GRAVY cannot be rendered as proof of function or solubility
      and all normalized fields point back to raw payload locations.
    status: pending
  - id: p4-evidence-source-adapters
    content: >-
      PR 8 — Migrate STRING, GEO, PubMed, Europe PMC, and OrthoDB with validated
      species IDs, edge evidence channels, dataset-mention semantics, exact query
      tiers, citation deduplication, abstract spans, and orthology-transfer limits.
      Done when keyword-only GEO hits cannot support expression claims and STRING
      scores cannot imply physical interaction without experimental evidence.
    status: pending
  - id: p5-provider-protocol
    content: >-
      PR 9 — Replace provider-name branching with ProviderAdapter, capability
      declarations, core request/response/usage types, plugin registration, and
      complete_structured native-schema or bounded JSON-repair paths for Anthropic,
      Ollama, and OpenRouter. Done when core pipeline state contains no provider-native
      messages and provider failures/capabilities are explicit.
    status: pending
  - id: p5-provider-conformance
    content: >-
      PR 10 — Add shared offline conformance tests for valid/malformed structured
      output, refusals, truncation, timeouts, retries, usage normalization, unsupported
      capabilities, and secret redaction; keep live smoke tests opt-in. Done when all
      built-in providers pass the same keyless fixture suite.
    status: pending
  - id: p6-prompts-evidence-pack
    content: >-
      PR 11 — Move prompts into versioned hashed files; build bounded evidence packs
      from the immutable ledger; delimit source text as untrusted input; disable tools
      during synthesis; enforce an evidence-ID allowlist. Done when truncation is
      recorded, prompts are reproducibly identified, and source text cannot alter the
      research plan or artifact store.
    status: pending
  - id: p6-claim-synthesis
    content: >-
      PR 12 — Implement ClaimSynthesisAgent returning ClaimBundle JSON only plus
      validators for evidence existence, organism/isoform scope, numeric consistency,
      duplicates, and incompatible predicates. Done when publication mode rejects
      every uncited factual claim and exploratory hypotheses require explicit type,
      observations, alternatives, and falsifiers.
    status: pending
  - id: p7-verifier-critic
    content: >-
      PR 13 — Implement per-claim evidence entailment verification and a typed
      scientific critic for conflicts, source limitations, alternative explanations,
      missing controls, and falsifiers; deterministic checks remain authoritative.
      Done when reviewers cannot introduce or cite evidence absent from the frozen
      ledger and same-model review is labeled second-pass, not independent.
    status: pending
  - id: p7-review-modes
    content: >-
      PR 14 — Split review into frozen-evidence audit, fresh-retrieval reproduce,
      and frozen-ledger multi-provider compare; compare identities, queries, record
      IDs, hashes, timestamps, and drift causes rather than coarse source status.
      Done when current --review has a documented compatibility mapping and no
      same-pipeline rerun is described as scientific replication.
    status: pending
  - id: p8-report-renderer
    content: >-
      PR 15 — Build a deterministic renderer for reports and reviews containing
      claim/evidence citations, identity rationale, methods, provenance, conflicts,
      uncertainty, negative findings, limitations, model involvement, and reproduction
      instructions. Done when rendering from the same typed artifacts is byte-identical
      and every factual sentence resolves to accepted claim/evidence IDs.
    status: pending
  - id: p8-cli-cutover
    content: >-
      PR 16 — Refactor CLI around ResearchConfig; preserve safe research/check/models/
      selftest usage; add publication/exploratory modes, run inspection/resume,
      entity selection, offline mode, and audit/reproduce/compare commands; validate
      or deprecate unsafe flags. Done when legacy compatibility is tested, unsafe
      ambiguity exits non-zero, and full run inspection works offline.
    status: pending
  - id: p9-evaluation-release
    content: >-
      PR 17 — Build a human-annotated scientific evaluation harness and frozen-ledger
      provider matrix; enforce identity, source-accounting, citation, numeric,
      entailment, conformance, determinism, and documentation gates; publish benchmark
      results and staged alpha/beta/RC artifacts. Done only when every release gate in
      Phase 9 passes and clinical/diagnostic use remains explicitly unsupported.
    status: pending
isProject: false
---

# Adaseli v2 implementation runbook

## 1. Review verdict and design constraints

Current strengths worth preserving:
- Small dependency footprint; plain-Python source adapters.
- Fail-soft HTTP behavior in [`adaseli/http.py`](adaseli/http.py).
- Provider normalization intent in [`adaseli/providers/__init__.py`](adaseli/providers/__init__.py).
- Machine-generated coverage summaries in [`adaseli/agents/loop.py`](adaseli/agents/loop.py).
- Separate review artifact in [`adaseli/agents/review.py`](adaseli/agents/review.py).
- Existing `research`, `check`, `models`, and `selftest` CLI surface in [`adaseli/cli.py`](adaseli/cli.py).

Blocking scientific risks:
- Retrieval completeness depends on a model stopping correctly: only UniProt is forced; all later tools are optional model choices in [`adaseli/agents/loop.py`](adaseli/agents/loop.py). Example reports show repeated `not queried` sources despite the “exhaustive” prompt.
- Entity resolution can silently cross species because [`adaseli/tools/sequence.py`](adaseli/tools/sequence.py) drops the taxon in its second fallback and accepts the first result. Independent organism flags in [`adaseli/cli.py`](adaseli/cli.py) can also describe inconsistent organisms.
- GEO and literature tools silently broaden searches by dropping organism restrictions in [`adaseli/tools/expression.py`](adaseli/tools/expression.py) and [`adaseli/tools/literature.py`](adaseli/tools/literature.py). A keyword hit is then easy to misread as gene-level expression or functional evidence.
- Prose analysis and prose report handoffs in [`adaseli/agents/analysis.py`](adaseli/agents/analysis.py) and [`adaseli/agents/report.py`](adaseli/agents/report.py) have no atomic claim schema, evidence pointers, or enforceable citation coverage.
- The reviewer in [`adaseli/agents/review.py`](adaseli/agents/review.py) repeats the same workflow, sources, prompts, and usually provider. It measures scheduling/API variability, not independent scientific replication. Its own prose can introduce unsupported claims.
- “Provider agnostic” is partial: dispatch is a provider-name `if` chain, Ollama ignores required tool choice, core history retains provider-native messages, and there is no structured-output capability contract or conformance suite.
- Runs lack immutable raw evidence, source query details, timestamps, model parameters, prompt hashes, software revision, and content hashes. Markdown alone cannot reproduce or audit a result.
- Repository lacks automated tests, CI, license, contributing guide, citation metadata, security policy, and documented source terms.

Non-negotiable constraints:
- Scientific identity and evidence collection must not depend on an LLM.
- Every report claim must resolve to one or more immutable evidence records or be explicitly labeled a hypothesis.
- No clinical/diagnostic claims. Publication-support means traceable assistance, not autonomous scientific validation.
- Preserve the current CLI shape where safe; reject unsafe ambiguous input rather than preserving unsafe behavior.
- Do not add agents until deterministic foundations pass acceptance gates.

## 2. Target architecture

```mermaid
flowchart LR
    Cli[CLIInput] --> Resolve[DeterministicEntityResolver]
    Resolve -->|"validated stable IDs"| Plan[DeterministicSourcePlan]
    Resolve -->|"ambiguous or mismatched"| Stop[StopWithCandidates]
    Plan --> Fetch[ConcurrentSourceAdapters]
    Fetch --> Ledger[ImmutableEvidenceLedger]
    Ledger --> Synthesize[ClaimSynthesisAgent]
    Synthesize --> Claims[TypedClaimGraph]
    Claims --> Verify[EvidenceVerifierAgent]
    Ledger --> Verify
    Verify --> Critic[ScientificCriticAgent]
    Ledger --> Critic
    Critic --> Render[DeterministicRenderer]
    Render --> Report[ReportWithClaimCitations]
    Ledger --> Manifest[RunManifestAndHashes]
    Claims --> Manifest
    Report --> Manifest
```

LLM roles after redesign:
- `ClaimSynthesisAgent`: proposes atomic claims from a frozen evidence bundle; JSON only.
- `EvidenceVerifierAgent`: classifies each claim/evidence edge as supported, contradicted, contextual, or insufficient; JSON only.
- `ScientificCriticAgent`: identifies conflicts, missing controls, alternative explanations, and falsifiers from the same frozen evidence; JSON only.
- No LLM search scheduler. No free-form report writer. Markdown rendering is deterministic.

## 3. Canonical data contracts

Add [`adaseli/core/models.py`](adaseli/core/models.py) using Pydantic v2 and JSON-schema export. Raise the Python floor from 3.8 to 3.10 in [`pyproject.toml`](pyproject.toml), because Python 3.8 is end-of-life and typed unions/path handling simplify the v2 contracts.

`ResolvedEntity`:
- `input_query`, `canonical_symbol`, `display_name`, `entity_type`.
- `taxon_id`, `organism_name`, `organism_rank`.
- Stable IDs: NCBI Gene, Ensembl, HGNC when human, UniProt accession, reviewed/unreviewed status, canonical isoform.
- `synonyms`, `resolver_sources`, ranked `candidates`.
- `resolution_status`: `resolved`, `ambiguous`, `not_found`, `conflict`.
- `identity_checks`: exact taxon match, exact/alias symbol match, cross-source agreement.

`EvidenceRecord`:
- Stable `evidence_id` derived from source, record ID, normalized payload hash, and schema version.
- `source`, `source_record_id`, `entity_id`, `adapter_version`.
- Exact endpoint/query/parameters, retrieval timestamp, HTTP status, ETag/Last-Modified when present.
- `status`: `success`, `empty`, `partial`, `error`, `skipped`; never collapse these states.
- Raw payload path/hash plus normalized typed payload.
- Evidence class: curated annotation, experimental, computational prediction, correlative, text-mined, literature abstract, heuristic.
- Source release/version, license/redistribution note, warnings, parser errors.

`Claim`:
- Atomic `claim_id`, statement, subject, predicate, object, organism/isoform scope.
- `claim_type`: identity, function, structure, interaction, expression, pathway, orthology, literature synthesis, hypothesis.
- Evidence edges containing `evidence_id`, JSON Pointer or quoted source span, and relation: `supports`, `contradicts`, `context`, `insufficient`.
- Inference type: direct curated assertion, experimental result, computational prediction, correlation, text mining, annotation transfer, LLM synthesis.
- Confidence dimensions: identity certainty, evidence strength, source agreement, verifier result, overall label, and plain-language reasons. Avoid an unexplained single numeric score.
- `limitations`, `alternative_explanations`, `falsifiers`, `status`.

`RunManifest`:
- Schema/run IDs, UTC timestamps, parent run ID, CLI arguments, research mode.
- Package version, git commit and dirty flag, Python/platform.
- Provider/model per role, model parameters, capability snapshot, request IDs, usage, latency.
- Prompt name/version/hash; do not store hidden chain-of-thought.
- Source adapter versions, evidence hashes, output hashes, failures, warnings.
- Reproduction instructions and clinical-use disclaimer.

Canonical run layout:
```text
output/runs/<run-id>/
  manifest.json
  entity.json
  source-plan.json
  raw/<source>/<record>.*
  evidence/<evidence-id>.json
  claims.json
  verification.json
  critique.json
  report.md
  review.md
```

Run directories are immutable. The existing `{gene}_report.md` remains a convenience copy during migration and is marked non-canonical in its footer.

## 4. Ordered implementation phases

### Phase 0 — Freeze failure cases and establish governance

PR 1: baseline fixtures and project policy.
- Add `tests/fixtures/` with minimal, legally redistributable or synthetic responses for: human TP53, human LGALS1/GAL1 alias ambiguity, cyanobacterial `slr1634`, a sparse gene, a non-protein-coding gene, and a symbol shared across taxa.
- Add regression tests proving current failure modes: cross-taxon fallback, inconsistent organism tuple, missing tool coverage, empty-vs-data confusion, and uncited report claims.
- Add Apache-2.0 [`LICENSE`](LICENSE), [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md), [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), and [`CITATION.cff`](CITATION.cff).
- Add [`docs/scope-and-limitations.md`](docs/scope-and-limitations.md): exploratory/publication-support only; no clinical, diagnostic, treatment, or patient-specific use.
- Add [`docs/data-sources.md`](docs/data-sources.md) documenting terms, attribution, rate limits, and redistribution constraints for every source.
- Add `pytest`, `pytest-cov`, `ruff`, and `mypy` as development dependencies; add offline CI for Python 3.10–3.13.

Gate:
- CI runs without provider keys or network.
- Each known failure has a deterministic failing/xfail regression test before behavior changes.
- License and source-redistribution policy are explicit.

### Phase 1 — Typed models and immutable artifact store

PR 2: core contracts.
- Add [`adaseli/core/models.py`](adaseli/core/models.py), [`adaseli/core/errors.py`](adaseli/core/errors.py), and [`adaseli/core/hashing.py`](adaseli/core/hashing.py).
- Add schema version constants and generated schemas under `schemas/v2/`.
- Model status/error values explicitly; preserve partial successes and warnings.

PR 3: artifact persistence.
- Add [`adaseli/core/artifacts.py`](adaseli/core/artifacts.py) with atomic writes, content hashing, deterministic JSON ordering, run locking, and immutable-run enforcement.
- Add [`adaseli/core/manifest.py`](adaseli/core/manifest.py) to capture software, provider, prompt, source, and output metadata.
- Redact API keys and authorization headers before persistence/logging.

Gate:
- Round-trip schema tests pass.
- Identical normalized evidence produces identical hashes.
- Interrupted writes cannot leave a valid-looking partial artifact.
- Existing report paths are still written only as compatibility copies.

### Phase 2 — Deterministic entity resolution

PR 4: organism and entity resolver.
- Add [`adaseli/entities/models.py`](adaseli/entities/models.py), [`adaseli/entities/resolver.py`](adaseli/entities/resolver.py), and resolver adapters for NCBI Gene, UniProt, Ensembl, and HGNC for human genes.
- Resolve taxon first, then gene within taxon. Never retry without taxon silently.
- Rank reviewed canonical records above unreviewed isoforms, but retain all candidates and rationale.
- Validate returned taxon, symbol/alias, stable IDs, protein sequence organism, and cross-source agreement.
- Stop on ambiguity. Add CLI selectors such as `--entity-id` or `--uniprot-accession`; never let an LLM choose.
- Replace independent organism defaults with a taxon-centered config. Derive STRING species and KEGG organism mappings. Keep old `--string-species` and `--kegg-org` as deprecated validated overrides.
- Keep [`adaseli/tools/sequence.py`](adaseli/tools/sequence.py) as a compatibility wrapper until the v2 cutover; remove its cross-taxon fallback immediately.

Gate:
- Zero cross-taxon resolutions across the fixture set.
- TP53 resolves to the requested human entity; LGALS1/GAL1 produces a documented alias decision rather than mixing galectin and galactokinase.
- Conflicting organism flags fail before any research API or LLM call.
- Resolution rationale is fully represented in `entity.json`.

### Phase 3 — Source protocol and deterministic scheduler

PR 5: source adapter API.
- Add [`adaseli/sources/base.py`](adaseli/sources/base.py) with `SourceAdapter`, `SourceQuery`, `SourceResult`, declared capabilities, host rate policy, and source metadata.
- Add [`adaseli/sources/registry.py`](adaseli/sources/registry.py) using a registry/entry-point mechanism instead of a name `if` chain.
- Support third-party adapters through `adaseli.sources` package entry points.

PR 6: deterministic retrieval engine.
- Add [`adaseli/pipeline/retrieval.py`](adaseli/pipeline/retrieval.py) and [`adaseli/pipeline/source_plan.py`](adaseli/pipeline/source_plan.py).
- Build the required source plan from entity type and stable IDs, not model output.
- Execute independent sources concurrently after identity resolution; enforce per-host concurrency, timeout, retry, and backoff policies.
- Persist raw response before normalization. Sort normalized records deterministically.
- Always record `skipped` with a machine-readable reason when a source is inapplicable.
- Replace “last result per tool” with append-only evidence records; repeated queries must not overwrite earlier results.

Gate:
- Every applicable source is attempted exactly according to the plan, independent of provider/model.
- Coverage is computed from source-plan plus evidence statuses, including partial and empty results.
- Retrieval output is identical with LLMs disabled.

### Phase 4 — Correct source semantics

PR 7: identity, sequence, structure, and pathway adapters.
- Split [`adaseli/tools/sequence.py`](adaseli/tools/sequence.py) and [`adaseli/tools/network.py`](adaseli/tools/network.py) into typed v2 adapters while retaining wrappers.
- UniProt: exact taxon verification, canonical/reviewed ranking, isoform provenance.
- AlphaFold: validated accession only; record model version and explain that pLDDT measures local prediction confidence, not experimental validity, solubility, or function.
- Hydrophobicity: label GRAVY and TM-window output as heuristics; prohibit deterministic renderer phrases such as “confirms soluble.”
- KEGG: use validated mapped identifier; distinguish missing mapping, no entry, no pathway, HTTP error, and licensing restrictions.

PR 8: interaction, expression, literature, and orthology adapters.
- STRING: query validated IDs/species; retain evidence channels per edge, combined/channel scores, enrichment FDR, and source caveats.
- GEO: label keyword-search output as `dataset_mention`. Do not treat it as gene expression evidence unless the adapter extracts gene-level measurements and sample context.
- PubMed/Europe PMC: quote symbols, include controlled aliases, retain every query tier, forbid silent organism-free fallback, deduplicate PMID/DOI, and capture exact supporting abstract spans.
- OrthoDB: validate group identity/taxonomic level; distinguish no group from API/parser failure; record identity/similarity when available before annotation transfer.
- Add optional PDBe/PDB experimental structure adapter after core sources are stable.

Gate:
- Source-specific parser fixtures cover success, empty, partial, malformed, rate-limited, and changed-schema responses.
- Every normalized field is traceable to raw payload via JSON Pointer or source span.
- No keyword-only GEO record can support an expression/function claim.
- No STRING aggregate score can be described as a physical interaction without an experimental evidence channel.

### Phase 5 — Capability-based provider layer

PR 9: provider protocol.
- Add [`adaseli/providers/base.py`](adaseli/providers/base.py) with `ProviderAdapter`, `ModelRequest`, `ModelResponse`, `Usage`, and `ProviderCapabilities`.
- Capabilities include native JSON schema, JSON mode, tool calling, forced tool choice, seed, usage reporting, context window, and request-ID support.
- Replace the provider-name branch in [`adaseli/providers/__init__.py`](adaseli/providers/__init__.py) with a registry and `adaseli.providers` plugin entry points.
- Adapt Anthropic, Ollama, and OpenRouter behind the same core message/content types. Provider-native payloads stay inside adapter traces, not pipeline state.
- Implement `complete_structured(schema, request)`: native schema when supported; otherwise JSON-constrained prompt, validation, and bounded repair. Failure remains failure after the configured repair limit.
- Keep secrets environment-only. Add sanitized provider trace artifacts containing request metadata, response text/JSON, usage, and latency, never hidden reasoning.

PR 10: conformance suite.
- Add shared contract tests run against fake fixtures for all providers.
- Test schema adherence, malformed JSON, refusal, truncation, timeout, retry, usage normalization, unsupported capabilities, and deterministic error mapping.
- Add opt-in live smoke tests excluded from normal CI.

Gate:
- All built-in providers pass the same offline conformance suite.
- Core pipeline contains no provider-name conditionals.
- Retrieval and report structure are provider-independent.

### Phase 6 — Claim graph and bounded synthesis

PR 11: prompts and evidence packaging.
- Move prompts from [`adaseli/config.py`](adaseli/config.py) to versioned files under `adaseli/prompts/`; hash each prompt in the manifest.
- Add [`adaseli/pipeline/evidence_pack.py`](adaseli/pipeline/evidence_pack.py) to select bounded evidence without discarding the immutable raw ledger.
- Treat all source text as untrusted data: delimit records, disable tools during synthesis, and only accept referenced evidence IDs from the provided allowlist.

PR 12: synthesis agent.
- Add [`adaseli/agents/claim_synthesizer.py`](adaseli/agents/claim_synthesizer.py).
- Require a `ClaimBundle` JSON response; reject prose or unknown evidence IDs.
- In publication mode, reject any factual claim without a supporting evidence edge.
- In exploratory mode, permit hypotheses only when explicitly typed as `hypothesis`, with supporting observations, alternatives, and falsifiers.
- Add deterministic validators for citation existence, organism/isoform scope, numeric-value consistency, duplicate claims, and incompatible predicates.

Gate:
- Every accepted claim has valid evidence pointers.
- Unsupported factual claims fail the run rather than appearing in Markdown.
- Re-running rendering from the same `claims.json` yields byte-identical Markdown.

### Phase 7 — Verification and scientifically honest review

PR 13: evidence verifier and critic.
- Add [`adaseli/agents/evidence_verifier.py`](adaseli/agents/evidence_verifier.py) to evaluate one atomic claim against only its cited evidence.
- Add [`adaseli/agents/scientific_critic.py`](adaseli/agents/scientific_critic.py) for conflicts, alternative explanations, source limitations, missing controls, and falsifiers.
- Deterministic checks always run; an LLM verifier augments them but cannot override identity or citation failures.
- Support a distinct review provider/model. Label review “independent model review” only when provider/model differs; otherwise label it “second-pass review.”

PR 14: split review modes.
- Replace current overloaded review semantics with:
  - `audit`: frozen-evidence claim/citation review.
  - `reproduce`: fresh source retrieval, comparing identity, queries, record IDs, content hashes, and timestamps.
  - `compare`: same frozen ledger synthesized by multiple provider/model pairs for robustness evaluation.
- Keep `--review` as a deprecated alias for `audit` during migration.
- Update [`adaseli/agents/review.py`](adaseli/agents/review.py) to a compatibility wrapper; do not call a same-pipeline rerun “independent replication.”

Gate:
- Reviewer cannot cite evidence absent from the ledger.
- Retrieval differences distinguish data drift, parser changes, source failures, and plan differences.
- Review prose is rendered from typed findings; no free-form appendix can introduce new scientific claims.

### Phase 8 — Deterministic report renderer and CLI migration

PR 15: renderer.
- Add [`adaseli/reporting/renderer.py`](adaseli/reporting/renderer.py) and section templates under `adaseli/reporting/templates/`.
- Render each factual sentence with claim IDs and evidence links, e.g. `[C004; E-uniprot-…]`.
- Include identity resolution, methods, source/query provenance, evidence type, conflicts, uncertainty, negative/empty findings, limitations, coverage, model involvement, and reproduction instructions.
- Generate a concise main report plus machine-readable artifacts; avoid hiding provenance in a giant appendix.

PR 16: CLI cutover.
- Refactor [`adaseli/cli.py`](adaseli/cli.py) around a typed `ResearchConfig`.
- Preserve `adaseli research GENE`, `--provider`, `--model`, `--out`, and organism options with validation/deprecation messages.
- Add `--mode publication|exploratory`, `--run-dir`, `--resume`, `--entity-id`, role-specific provider/model options, `--offline`, and `--engine v2|legacy` during preview.
- Map `--report-model` to synthesis model with a warning; map `--review-model` to verifier/critic model.
- Add `adaseli inspect <run-id>`, `adaseli audit <run-id>`, `adaseli reproduce <run-id>`, and `adaseli compare <run-id> ...`.
- Make v2 default only after evaluation gates pass; retain legacy for one documented release, then remove it in the next major release.

Gate:
- Existing safe CLI invocations still work.
- Unsafe ambiguous identity or inconsistent organism configuration exits non-zero with actionable candidates.
- A run can be rendered, audited, and inspected fully offline from its artifacts.

### Phase 9 — Evaluation, release, and maintenance

PR 17: scientific evaluation harness.
- Add `evals/cases.yaml`, `evals/annotations/`, and [`adaseli/evals/runner.py`](adaseli/evals/runner.py).
- Curate cases across species, aliases, isoforms, sparse genes, famous genes, absent proteins, and contradictory sources.
- Human annotations score identity, evidence relevance, claim support, citation correctness, uncertainty labeling, and overclaim severity.
- Run provider comparisons only on frozen ledgers so provider quality is not confounded with retrieval differences.

Required release gates:
- 100% correct taxon/entity resolution on the curated identity set; zero silent cross-taxon fallbacks.
- 100% planned-source accounting: every source is success, empty, partial, error, or justified skipped.
- Zero accepted factual claims with missing/invalid evidence IDs.
- Zero numeric claims that differ from cited normalized evidence.
- At least 95% human-rated claim entailment precision in publication mode; every remaining error reviewed before release.
- 100% built-in provider conformance on offline fixtures.
- Offline end-to-end fixture run deterministic except explicitly volatile manifest fields.
- Documentation accurately labels AlphaFold, STRING, GEO, orthology transfer, and literature evidence limitations.

Release sequence:
- `2.0.0a1`: schemas, resolver, artifact store, source planner; no promise of report compatibility.
- `2.0.0b1`: provider protocol, claim graph, audit, deterministic renderer.
- `2.0.0rc1`: frozen benchmark results published under `docs/evaluation/`; v2 default.
- `2.0.0`: stable schemas, migration guide, source/provider plugin docs, archived example runs with manifests.

## 5. Operational and reproducibility rules

- Cache public responses by canonical request plus source headers; preserve retrieval time and content hash. Cache use must be explicit in the manifest.
- Respect per-host rate limits and identify the client with a real project URL/contact, replacing the localhost User-Agent in [`adaseli/config.py`](adaseli/config.py).
- Never persist secrets, auth headers, or provider chain-of-thought.
- Use UTC timestamps, deterministic sorting, stable JSON serialization, and atomic writes.
- Pin CI/dev tooling; publish supported dependency ranges for the library. Generate an SBOM and provenance attestation for releases.
- Scheduled live-source tests report drift but do not block ordinary pull requests. Parser fixture tests remain the blocking gate.
- Treat abstracts and database text as prompt-injection-capable untrusted input. Synthesis agents have no tools and cannot alter the source plan or ledger.
- Do not ingest patient data. Document that public gene research queries are not a privacy control for clinical workflows.

## 6. Migration map

- [`adaseli/agents/loop.py`](adaseli/agents/loop.py): legacy only; deterministic retrieval moves to `pipeline/retrieval.py`.
- [`adaseli/agents/search.py`](adaseli/agents/search.py): retire after v2 source planner stabilizes.
- [`adaseli/agents/analysis.py`](adaseli/agents/analysis.py): replace with typed claim synthesis.
- [`adaseli/agents/report.py`](adaseli/agents/report.py): replace with deterministic renderer.
- [`adaseli/agents/review.py`](adaseli/agents/review.py): compatibility wrapper for `audit`/`reproduce` during migration.
- [`adaseli/tools/registry.py`](adaseli/tools/registry.py): compatibility facade over source registry; remove model tool schemas from the core research path.
- Existing `tools/*.py`: migrate adapter-by-adapter; retain thin deprecated functions for one release.
- Existing `providers/*.py`: retain HTTP implementations but conform them to `ProviderAdapter`.
- Existing Markdown examples: move to `examples/runs/` only when accompanied by complete manifests and a warning that they are illustrative, not validated scientific references.

## 7. Review strategy per PR

For each PR:
1. Add or update offline fixtures before behavior changes.
2. Implement one contract or adapter family only.
3. Run `ruff check`, `mypy`, unit tests, schema round trips, and relevant golden tests.
4. Review generated artifact diffs, not only terminal success.
5. Require a scientific-semantics review for source interpretation or report wording changes.
6. Merge only when the phase gate is met; do not bypass a failed identity, provenance, or citation gate to progress downstream.

First implementation slice should be Phases 0–2. It removes the highest-risk failure—wrong biological identity—before investing in additional agents or report polish.

## 8. TODO execution map

The plan TODO list is intentionally PR-sized. Execute in this dependency order:

1. `p0-baseline-governance` — Phase 0, PR 1.
2. `p1-core-contracts` — Phase 1, PR 2.
3. `p1-artifact-store` — Phase 1, PR 3; depends on core contracts.
4. `p2-entity-resolution` — Phase 2, PR 4; depends on contracts and artifact persistence.
5. `p3-source-protocol` — Phase 3, PR 5.
6. `p3-retrieval-engine` — Phase 3, PR 6; depends on entity resolution and source protocol.
7. `p4-core-source-adapters` — Phase 4, PR 7.
8. `p4-evidence-source-adapters` — Phase 4, PR 8; may run after PR 7 starts, but both require source protocol.
9. `p5-provider-protocol` — Phase 5, PR 9; can begin after core contracts stabilize.
10. `p5-provider-conformance` — Phase 5, PR 10; blocks all LLM-agent work.
11. `p6-prompts-evidence-pack` — Phase 6, PR 11; depends on immutable evidence and provider contracts.
12. `p6-claim-synthesis` — Phase 6, PR 12.
13. `p7-verifier-critic` — Phase 7, PR 13.
14. `p7-review-modes` — Phase 7, PR 14.
15. `p8-report-renderer` — Phase 8, PR 15; depends on accepted claim/review schemas.
16. `p8-cli-cutover` — Phase 8, PR 16; keeps v2 behind an engine flag until evaluation passes.
17. `p9-evaluation-release` — Phase 9, PR 17; makes v2 default only after all release gates pass.

Each TODO's frontmatter description contains its deliverables and definition of done. The corresponding phase section above contains file-level steps, migration rules, tests, and acceptance gates.

## 9. Lower-model execution protocol

Use this section as mandatory implementation guidance, not optional commentary.

### Per-task workflow

For each TODO:
1. Read only the files named by that work packet plus their direct imports.
2. Add tests/fixtures first. Confirm the new test fails for the expected reason.
3. Implement only the named task. Do not begin downstream architecture early.
4. Preserve legacy public functions with thin wrappers where requested.
5. Run the task-specific tests, then the full offline quality command.
6. Inspect generated JSON/Markdown fixtures. Passing tests alone is insufficient.
7. Update docs and schema snapshots in the same task when a public contract changes.
8. Do not commit, push, or alter unrelated files unless explicitly requested.

### Global implementation rules

- Python target: 3.10–3.13. Use `from __future__ import annotations`.
- Pydantic target: v2. Set `model_config = ConfigDict(extra="forbid")` on persisted models.
- Timestamps: timezone-aware UTC ISO 8601 with `Z`.
- JSON: UTF-8, sorted keys, two-space indent, trailing newline, no NaN/Infinity.
- IDs: core assigns IDs. Never trust model-generated final IDs.
- Hash: SHA-256 over canonical normalized JSON or raw bytes. Never hash pretty Markdown as evidence identity.
- Enums: subclass `str, Enum`; Python 3.10 has no `StrEnum`.
- HTTP: all source traffic passes through one client. No adapter calls `requests` directly after PR 6.
- Secrets: env only. Strip query/header secrets before logs and artifacts.
- Errors: typed errors at boundaries; no broad `except Exception` unless converting an unknown adapter failure into a persisted `error` result with traceback logged.
- Ordering: source order, record order, claim order, and report order must be deterministic.
- Scientific text: never convert prediction, correlation, text mining, or keyword matching into experimental fact.
- LLM input: do not send full protein sequences unless a future task explicitly needs sequence reasoning. Send stable IDs, sequence hash/length, computed features, and bounded evidence excerpts.
- LLM output: structured data only. No chain-of-thought request or persistence.
- Clinical safety: no `clinical` mode, patient data field, diagnosis, treatment recommendation, pathogenicity classification, or “clinically validated” wording.
- Tests: ordinary CI is offline. Live source/provider tests use explicit markers and never block pull requests.

### Full offline quality command

Configure these commands in project tooling; every completed TODO must pass all commands available at that point:

```bash
ruff check adaseli tests
ruff format --check adaseli tests
mypy adaseli
pytest -m "not live" --cov=adaseli --cov-report=term-missing
python -m adaseli selftest --quiet
```

Add a single `make check` or equivalent script only if the project wants a task runner; do not introduce one solely to wrap five commands.

### Dependency boundaries

- `adaseli/core/` imports no agents, providers, source implementations, CLI, or reporting.
- `adaseli/entities/` may import core and source-neutral HTTP primitives; it imports no LLM provider.
- `adaseli/sources/` imports core and HTTP; it imports no agents or reporting.
- `adaseli/providers/` imports core request/trace models; it imports no biological source.
- `adaseli/agents/` consumes typed evidence and provider interfaces; it performs no HTTP source retrieval.
- `adaseli/reporting/` consumes persisted typed artifacts; it performs no source/provider calls.
- `adaseli/cli.py` wires components; scientific rules must live below CLI.

## 10. Detailed implementation work packets

### TODO `p0-baseline-governance` — PR 1

Goal: create a safe baseline before changing behavior.

Files to add:
- `tests/conftest.py`
- `tests/fixtures/uniprot/`, `tests/fixtures/ncbi/`, `tests/fixtures/alphafold/`, `tests/fixtures/string/`, `tests/fixtures/geo/`, `tests/fixtures/literature/`, `tests/fixtures/orthodb/`
- `tests/test_current_regressions.py`
- `tests/test_http.py`
- `tests/test_coverage.py`
- `.github/workflows/ci.yml`
- `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CITATION.cff`
- `docs/scope-and-limitations.md`, `docs/data-sources.md`, `docs/privacy.md`

Files to modify:
- [`pyproject.toml`](pyproject.toml)
- [`README.md`](README.md)
- [`adaseli/config.py`](adaseli/config.py)

Implementation steps:
1. Set `requires-python = ">=3.10"` and add classifiers, license expression, authors, repository/issues/docs URLs.
2. Add a `dev` optional dependency group containing pytest, pytest-cov, ruff, mypy, and requests-mock.
3. Configure Ruff and mypy in `pyproject.toml`; begin with checks that current code can satisfy without a cleanup refactor.
4. Build minimal fixtures. Keep only fields needed by parsers. Use synthetic payloads where source redistribution is unclear, especially KEGG.
5. Add regression tests for:
   - taxon-free UniProt fallback selecting another species;
   - human organism name combined with default cyanobacterial taxon/STRING/KEGG values;
   - search stopping after UniProt despite unqueried tools;
   - source returning an empty list being displayed as generic “data returned”;
   - report prose containing factual claims with no evidence identifier;
   - review marking status-only divergence as scientific replication.
6. Mark behavior-regression tests `xfail(strict=True, reason="v1 known defect")`; later PRs remove `xfail` one defect at a time.
7. Make `selftest` genuinely offline by monkeypatching/injecting source responses or by keeping it on the legacy fake path with no network calls. Add a test that fails if `requests` is invoked.
8. Replace the localhost User-Agent with a real repository URL and documented contact mechanism. Keep contact configurable.
9. Document exactly which source data and sequence-derived data can be sent to cloud models; recommend local providers when data policy requires it.
10. CI matrix: Python 3.10, 3.11, 3.12, 3.13 on Ubuntu. Run install, lint, type check, offline tests, and selftest. Add macOS only after core CI is stable.

Acceptance:
- `pytest -m "not live"` completes with zero network calls.
- CI has no secrets and passes from a clean clone.
- Package metadata validates with `python -m build` and `twine check dist/*` if build tools are installed.
- README no longer promises clinical suitability or guaranteed exhaustiveness from the legacy engine.

Do not implement:
- New v2 runtime models, entity resolver, provider redesign, or source adapters.

### TODO `p1-core-contracts` — PR 2

Goal: establish persisted contracts before building behavior.

Files to add:
- `adaseli/core/__init__.py`
- `adaseli/core/models.py`
- `adaseli/core/enums.py`
- `adaseli/core/errors.py`
- `adaseli/core/hashing.py`
- `adaseli/core/time.py`
- `tests/core/test_models.py`
- `tests/core/test_hashing.py`
- `schemas/v2/*.schema.json`

Required enums:

```python
class RunMode(str, Enum):
    publication = "publication"
    exploratory = "exploratory"

class RunStatus(str, Enum):
    running = "running"
    complete = "complete"
    partial = "partial"
    failed = "failed"

class EvidenceStatus(str, Enum):
    success = "success"
    empty = "empty"
    partial = "partial"
    error = "error"
    skipped = "skipped"

class EvidenceClass(str, Enum):
    curated_annotation = "curated_annotation"
    experimental = "experimental"
    computational_prediction = "computational_prediction"
    heuristic = "heuristic"
    correlative = "correlative"
    text_mined = "text_mined"
    dataset_mention = "dataset_mention"
    literature_abstract = "literature_abstract"

class EvidenceRelation(str, Enum):
    supports = "supports"
    contradicts = "contradicts"
    context = "context"
    insufficient = "insufficient"
```

Required models and minimum fields:
- `OrganismRef`: `taxon_id`, `scientific_name`, aliases, mapping provenance.
- `EntityCandidate`: source IDs, symbol/name, organism, entity type, reviewed/canonical flags, match reasons, deterministic rank tuple.
- `ResolvedEntity`: original query, chosen candidate, all candidates, resolution status, identity checks.
- `SourceQuery`: source, operation, endpoint, sanitized parameters, required/optional reason, request fingerprint.
- `RawArtifactRef`: path, media type, byte count, SHA-256.
- `NormalizedPointer`: evidence ID plus JSON Pointer or quoted text span.
- `EvidenceRecord`: fields defined in Section 3; payload must be a discriminated typed model or a JSON object with a declared `payload_schema`.
- `ClaimEvidenceEdge`: evidence ID, pointer/span, relation, explanation.
- `ProposedClaim`: model-returned atomic claim without final ID or final confidence.
- `Claim`: final ID, scope, type, evidence edges, inference type, verifier status, limitations/falsifiers.
- `ProviderTrace`: role, provider, model, sanitized parameters, prompt hash, request ID, usage, latency, output artifact, error.
- `RunManifest`: full run metadata and artifact index.

Implementation details:
1. Persist schema version on every top-level artifact.
2. Validate all paths as relative POSIX paths; no absolute paths in portable manifests.
3. Canonical hashing excludes volatile fields only through an explicit model method, never by deleting arbitrary keys in the generic hash helper.
4. `canonical_json_bytes(value)` must serialize sorted keys, UTF-8, compact separators, and forbid NaN.
5. Generate JSON-schema snapshots from models in a test; fail when model changes are not accompanied by schema snapshot updates.
6. Keep confidence multidimensional. Do not define a single float as the authoritative scientific confidence.

Acceptance tests:
- Unknown persisted keys fail validation.
- Invalid status combinations fail, e.g. `success` without normalized payload or `error` without error details.
- Same semantic model produces same hash regardless of dictionary insertion order.
- One changed normalized value changes hash.
- Schema snapshots are deterministic.

Do not implement:
- File writes, HTTP, entity selection, LLM calls, or Markdown.

### TODO `p1-artifact-store` — PR 3

Goal: persist every run as an immutable, auditable bundle.

Files to add:
- `adaseli/core/artifacts.py`
- `adaseli/core/manifest.py`
- `adaseli/core/redaction.py`
- `tests/core/test_artifacts.py`
- `tests/core/test_manifest.py`

Public API:

```python
class ArtifactStore:
    @classmethod
    def create(cls, root: Path, config: ResearchConfig) -> "ArtifactStore": ...
    @classmethod
    def open(cls, run_dir: Path) -> "ArtifactStore": ...
    def write_bytes(self, relative_path: str, data: bytes, media_type: str) -> RawArtifactRef: ...
    def write_model(self, relative_path: str, model: BaseModel) -> RawArtifactRef: ...
    def read_model(self, relative_path: str, model_type: type[T]) -> T: ...
    def append_trace(self, trace: ProviderTrace) -> None: ...
    def finalize(self, status: RunStatus) -> RunManifest: ...
```

Implementation steps:
1. Generate run IDs as `YYYYMMDDTHHMMSSZ-<8 random hex>`; collision-check directory creation.
2. Create a `RUNNING` marker with exclusive creation. Finalization removes it only after all hashes and manifest are written.
3. Write to a sibling temporary file, `fsync`, then atomic replace. Reject existing canonical artifact paths.
4. Normalize and reject `..`, absolute paths, symlink escapes, and writes outside the run directory.
5. Persist raw source bytes before parser execution.
6. Maintain an in-memory artifact index during the run; generate final manifest from actual files and hashes, not expected names.
7. Redact keys matching authorization, API key, token, cookie, and provider-specific secret names recursively.
8. Record git revision/dirtiness when available. Failure to invoke git must become `unknown`, not fail a run.
9. Compatibility report copy is written after canonical finalization and is not included as canonical evidence.
10. `ArtifactStore.open` validates manifest, file existence, byte size, and hash before returning.

Acceptance tests:
- Crash before finalization leaves `RUNNING` and no complete manifest.
- Opening a modified artifact fails integrity validation.
- Existing run cannot be overwritten.
- Redaction removes secrets from nested headers/query structures.
- Path traversal and symlink escape attempts fail.

### TODO `p2-entity-resolution` — PR 4

Goal: guarantee correct gene/protein and species before research begins.

Files to add:
- `adaseli/entities/__init__.py`
- `adaseli/entities/models.py`
- `adaseli/entities/resolver.py`
- `adaseli/entities/organisms.py`
- `adaseli/entities/adapters/ncbi_gene.py`
- `adaseli/entities/adapters/uniprot.py`
- `adaseli/entities/adapters/ensembl.py`
- `adaseli/entities/adapters/hgnc.py`
- `tests/entities/`

Files to modify:
- [`adaseli/cli.py`](adaseli/cli.py)
- [`adaseli/tools/sequence.py`](adaseli/tools/sequence.py)

Resolver API:

```python
class EntityResolver:
    def resolve(
        self,
        query: str,
        taxon_id: str,
        *,
        explicit_entity_id: str | None = None,
        explicit_uniprot: str | None = None,
    ) -> ResolvedEntity: ...
```

Algorithm:
1. Resolve/validate taxon ID and canonical organism name first.
2. Detect stable-ID input types before treating input as a symbol.
3. Query NCBI Gene with exact symbol plus taxon. Query HGNC only for taxon 9606. Query Ensembl cross-references. Query UniProt with exact gene and exact organism.
4. Never issue a global symbol query as a hidden fallback.
5. Combine candidates only when stable IDs or explicit cross-references connect them.
6. Rank deterministically:
   - exact taxon required;
   - explicit stable-ID match;
   - exact approved symbol;
   - documented alias;
   - curated/reviewed record;
   - canonical protein/isoform;
   - stable source priority.
7. If the top candidates remain tied, sources disagree on organism/entity, or the symbol is an alias for multiple biological concepts, return `ambiguous`/`conflict`.
8. Require `--entity-id` or `--uniprot-accession` to choose among ambiguous candidates. Persist the user selection and candidate list.
9. Derive STRING species from validated taxonomy. Resolve KEGG organism code through a versioned mapping/query; do not accept mismatched manual values.
10. Validate the returned UniProt organism taxon against the resolved gene taxon before making it available downstream.

Specific regressions:
- Human `LGALS1` should resolve to human LGALS1 and human canonical protein candidates.
- Human input alias `GAL1` must surface that it is an LGALS1 alias and must not silently select fungal galactokinase.
- `GAL1` with a fungal taxon may resolve fungal galactokinase.
- Human TP53 may retain multiple isoforms, but the canonical reviewed protein must be distinguishable from unreviewed isoforms.
- `slr1634` must remain in the requested cyanobacterial taxon.

CLI behavior:
- Make `--taxon` the stable organism anchor.
- `--organism-name` becomes validation/display input, not an independent authority.
- Keep `--string-species` and `--kegg-org` temporarily; reject conflicts and emit deprecation warnings.
- Exit before any research adapter/provider call on unresolved identity.

Acceptance:
- Remove relevant `xfail` markers from PR 1.
- Assert provider fake receives zero calls for ambiguity/failure cases.
- Assert raw resolver responses, candidate ranking, and selection rationale exist in the run bundle.

### TODO `p3-source-protocol` — PR 5

Goal: make biological sources typed and externally extensible.

Files to add:
- `adaseli/sources/__init__.py`
- `adaseli/sources/base.py`
- `adaseli/sources/registry.py`
- `adaseli/sources/metadata.py`
- `tests/sources/test_registry.py`
- `tests/sources/test_contract.py`

Protocol:

```python
class SourceAdapter(Protocol):
    name: str
    version: str
    metadata: SourceMetadata

    def supports(self, entity: ResolvedEntity) -> bool: ...
    def plan(self, entity: ResolvedEntity, mode: RunMode) -> list[SourceQuery]: ...
    def fetch(self, query: SourceQuery, client: HttpClient) -> RawSourceResult: ...
    def normalize(
        self,
        query: SourceQuery,
        raw: RawSourceResult,
        raw_ref: RawArtifactRef,
    ) -> list[EvidenceRecord]: ...
```

Required behavior:
1. `SourceMetadata` contains homepage, citation, terms URL, redistribution note, rate guidance, evidence classes, and maintainer.
2. Registry rejects duplicate names and incompatible adapter versions.
3. Built-ins register explicitly. Third parties register via `importlib.metadata.entry_points(group="adaseli.sources")`.
4. Discovery errors identify the plugin and do not silently suppress a requested source.
5. `plan` is pure and deterministic.
6. `supports=False` becomes `skipped` with reason. It is not an error.
7. `normalize` never performs network access.
8. Raw source result carries status, headers, media type, body bytes, sanitized URL, elapsed time, and attempt count.
9. Keep existing `tools/registry.py` functions as deprecated wrappers targeting built-in adapters; v2 does not expose tool schemas to an LLM.

Acceptance:
- A test plugin registers without modifying core registry code.
- Source plan order is stable regardless of plugin discovery order.
- Contract tests reject an adapter that returns records with the wrong source/query fingerprint.

### TODO `p3-retrieval-engine` — PR 6

Goal: collect evidence completely without LLM scheduling.

Files to add:
- `adaseli/http_client.py`
- `adaseli/pipeline/__init__.py`
- `adaseli/pipeline/source_plan.py`
- `adaseli/pipeline/retrieval.py`
- `adaseli/pipeline/config.py`
- `tests/pipeline/test_source_plan.py`
- `tests/pipeline/test_retrieval.py`
- `tests/test_http_client.py`

Core APIs:

```python
def build_source_plan(
    entity: ResolvedEntity,
    adapters: Sequence[SourceAdapter],
    mode: RunMode,
) -> SourcePlan: ...

def retrieve(
    plan: SourcePlan,
    registry: SourceRegistry,
    store: ArtifactStore,
    client: HttpClient,
    *,
    max_workers: int,
) -> EvidenceLedger: ...
```

Implementation steps:
1. Replace module-level HTTP helper internals with an injectable `HttpClient`, while keeping `http_get` as a compatibility wrapper.
2. Request fingerprint = HTTP method + canonical URL + sorted sanitized parameters + accepted media type. Exclude auth.
3. Cache raw responses by fingerprint with response timestamp, ETag, Last-Modified, and hash. Record cache hit/miss in evidence.
4. Add `--refresh` later; client API must support bypassing cache now.
5. Use `ThreadPoolExecutor`, because existing adapters are synchronous `requests` code. Use per-host bounded semaphores and a global worker cap.
6. Retry idempotent transient failures only: connection errors, timeout, 429 honoring `Retry-After`, and selected 5xx. Use bounded exponential backoff plus jitter recorded in trace.
7. Do not retry deterministic 4xx except 408/429.
8. Write raw bytes immediately after successful HTTP response and before normalization.
9. Convert parser failure into `EvidenceStatus.error` linked to the raw artifact. Preserve traceback in logs, concise typed error in manifest.
10. Merge worker results in canonical source-plan order, never completion order.
11. A run becomes `partial` when required source queries error; empty valid responses do not make the run failed.
12. Required source errors must be prominent but may still permit a report based on available evidence. Entity resolution failure remains fatal.

Acceptance:
- Fake providers are absent from retrieval tests.
- Two runs over identical fixtures produce identical source plan/evidence ordering and hashes.
- Concurrency reduces wall time in a controlled delayed-fixture test without changing order.
- Every planned query has one terminal result.

### TODO `p4-core-source-adapters` — PR 7

Goal: migrate identity-adjacent sources with scientifically correct semantics.

Files to add:
- `adaseli/sources/uniprot.py`
- `adaseli/sources/alphafold.py`
- `adaseli/sources/hydrophobicity.py`
- `adaseli/sources/kegg.py`
- `adaseli/sources/payloads/sequence.py`
- `tests/sources/test_uniprot.py`
- `tests/sources/test_alphafold.py`
- `tests/sources/test_hydrophobicity.py`
- `tests/sources/test_kegg.py`

UniProt:
- Query only validated taxon and identifiers.
- Normalize reviewed status, canonical/isoform status, sequence, sequence hash, GO evidence codes when available, feature coordinates, function comments, and cross-references.
- Preserve source record ID and release/last-updated metadata.
- If returned taxon differs, emit `error`/identity conflict; never continue as success.

AlphaFold:
- Accept only validated UniProt accession.
- Record model version, URLs, mean pLDDT if API supplies it, PAE availability, and retrieval date.
- Evidence class is computational prediction.
- Attach mandatory caveat: pLDDT estimates local model confidence and does not establish experimental structure, function, interaction, localization, or solubility.

Hydrophobicity:
- Make this a local source adapter whose query references a sequence evidence ID/hash.
- Preserve algorithm name, scale, window, threshold, code version, input sequence hash, GRAVY, and candidate ranges.
- Unknown residues must be reported, not silently scored zero.
- Overlapping windows should merge into explicit candidate regions using tested coordinate rules.
- Evidence class is heuristic. Renderer may say “heuristic predicts,” never “is membrane” or “is soluble.”

KEGG:
- Require a validated KEGG organism/gene mapping.
- Distinguish no mapping, no entry, entry with no KO/pathway, HTTP failure, and parse failure.
- Preserve raw flat-file lines and normalized KO/pathway IDs.
- Do not commit source payloads if terms disallow redistribution; use synthetic fixtures and document this.

Acceptance:
- All adapter output validates as `EvidenceRecord`.
- Numeric outputs match fixtures exactly.
- Mandatory caveats are data fields consumed by renderer, not prompt-only instructions.

### TODO `p4-evidence-source-adapters` — PR 8

Goal: migrate evidence-heavy sources without overstating what they show.

Files to add:
- `adaseli/sources/stringdb.py`
- `adaseli/sources/geo.py`
- `adaseli/sources/pubmed.py`
- `adaseli/sources/europe_pmc.py`
- `adaseli/sources/orthodb.py`
- `adaseli/sources/payloads/*.py`
- corresponding `tests/sources/test_*.py`

STRING:
- Resolve STRING identifier/species before network query.
- Use an endpoint that exposes per-channel scores where available.
- Normalize partner stable ID/name, combined score, neighborhood/fusion/co-occurrence/coexpression/experimental/database/text-mining scores, directionality if any, and enrichment FDR.
- A physical interaction claim requires a qualifying experimental/database evidence edge; combined/text-mining score alone is association evidence.

GEO:
- Preserve exact Entrez query, dataset accession/title/type/organism/sample count.
- Default output is `dataset_mention`, not expression evidence.
- Never silently retry without organism. If broader exploratory query is requested later, make it a separate planned query labeled `broad_discovery`.
- Only create gene-expression evidence when gene-level values, sample groups, platform/probe mapping, and comparison context are actually parsed.

PubMed:
- Build deterministic query tiers from approved symbol and validated aliases.
- Quote ambiguous symbols. Include organism/taxon terms.
- Never silently drop organism. Record zero-result exact query honestly.
- Normalize PMID, DOI, title, journal, year, publication type, retraction/correction status when available, abstract text/span, and query tier.

Europe PMC:
- Apply same query-tier policy.
- Normalize source ID, PMID/PMCID/DOI, preprint status, version, abstract span, publication type.
- Deduplicate with PubMed by PMID, then DOI; preserve both source records and one canonical citation identity.

OrthoDB:
- Query using validated source cross-reference when possible.
- Preserve group ID, taxonomic level, member stable IDs, species, and any supplied orthology confidence/identity.
- Annotation transfer claim must carry orthology distance/identity evidence when available and remain `annotation_transfer`, not direct function.

Acceptance:
- Tests cover success, empty, partial, malformed schema, 429, and stale/changed fields.
- Every literature claim can cite a PMID/DOI/source ID and exact abstract span.
- Retracted publication fixtures are flagged and excluded from positive support by default.

### TODO `p5-provider-protocol` — PR 9

Goal: isolate provider quirks and guarantee structured output behavior.

Files to add:
- `adaseli/providers/base.py`
- `adaseli/providers/registry.py`
- `adaseli/providers/structured.py`
- `adaseli/providers/tracing.py`
- `tests/providers/test_registry.py`
- `tests/providers/test_structured.py`

Core types:

```python
class ProviderCapabilities(BaseModel):
    native_json_schema: bool
    json_mode: bool
    tool_calling: bool
    forced_tool_choice: bool
    seed: bool
    usage: bool
    request_id: bool
    max_context_tokens: int | None

class ProviderAdapter(Protocol):
    name: str
    def capabilities(self, model: str) -> ProviderCapabilities: ...
    def complete(self, request: ModelRequest) -> ModelResponse: ...
    def complete_structured(
        self,
        request: ModelRequest,
        output_model: type[T],
    ) -> StructuredResponse[T]: ...
```

Implementation steps:
1. Define provider-neutral message parts for text and bounded JSON data. Do not place provider-native assistant objects in core history.
2. Keep current HTTP code but wrap it behind adapters.
3. Anthropic structured output may use a forced synthetic output tool when supported; parse the tool input as the result.
4. OpenRouter may use `response_format.json_schema` only when model capability says it is supported; otherwise use JSON mode/prompt fallback.
5. Ollama may use `format` with schema when supported; capabilities must be explicit/configurable by model.
6. Fallback path: request JSON only, parse exactly one JSON object, validate with Pydantic, then perform at most one repair request containing validation errors and prior invalid JSON. No infinite retries.
7. Publication mode defaults temperature to 0 where supported. Record ignored/unsupported parameters.
8. Add consistent timeout and transient retry policy; provider-specific upstream details become sanitized typed errors.
9. Track request ID, input/output token usage, latency, model, parameters, capability snapshot, and output artifact.
10. Register providers through built-ins plus `adaseli.providers` entry points.
11. Preserve legacy `llm_step` and `add_tool_results` wrappers only for `--engine legacy`.

Acceptance:
- No v2 module branches on provider name.
- Adapter raw payloads do not escape provider package except sanitized trace artifact references.
- Invalid structured output cannot silently become empty claims.

### TODO `p5-provider-conformance` — PR 10

Goal: prove all providers honor one behavioral contract.

Files to add:
- `tests/providers/conformance.py`
- `tests/providers/test_anthropic_contract.py`
- `tests/providers/test_ollama_contract.py`
- `tests/providers/test_openrouter_contract.py`
- `tests/providers/fixtures/`
- `tests/live/test_provider_smoke.py`

Shared contract cases:
1. Valid plain completion.
2. Valid native structured response.
3. Valid fallback JSON response.
4. JSON wrapped in prose: reject, do not heuristically accept.
5. Malformed JSON repaired once successfully.
6. Malformed JSON still invalid after repair: typed failure.
7. Schema-valid object with unknown evidence ID: downstream validator failure.
8. Refusal/safety response.
9. Empty response.
10. Token truncation.
11. Timeout and transient 5xx.
12. Rate limit with retry metadata.
13. Usage/request-ID present and absent.
14. Unsupported seed/tool/schema capability.
15. Secret-bearing error payload redaction.

Live tests:
- Mark `@pytest.mark.live` and provider-specific markers.
- Skip unless the exact environment key is present.
- Make one minimal request; never run full gene research.
- Do not assert wording, only connectivity and contract shape.

Acceptance:
- Every built-in adapter executes the same shared test function.
- Offline provider tests use recorded/synthetic responses and no real network.
- This TODO blocks `p6-*`.

### TODO `p6-prompts-evidence-pack` — PR 11

Goal: make LLM inputs reproducible, bounded, and resistant to source-text instructions.

Files to add:
- `adaseli/prompts/claim_synthesis_v1.md`
- `adaseli/prompts/evidence_verification_v1.md`
- `adaseli/prompts/scientific_critique_v1.md`
- `adaseli/prompts/loader.py`
- `adaseli/pipeline/evidence_pack.py`
- `tests/prompts/test_loader.py`
- `tests/pipeline/test_evidence_pack.py`

Prompt loader:
- Load package resources, normalize line endings, compute SHA-256, return name/version/text/hash.
- Prompt version changes require a new file or explicit version bump; do not silently mutate a released prompt.

Evidence-pack algorithm:
1. Group records into identity, annotation/pathway, structure, interaction, expression, literature, and orthology.
2. Include evidence ID, source record ID, evidence class, scope, normalized facts, mandatory caveats, and exact supporting spans.
3. Exclude raw HTML/XML, full sequences, authorization data, and irrelevant payload fields.
4. Estimate budget deterministically. Reserve response budget and provider overhead.
5. If oversized, split on whole evidence records. Never byte-truncate JSON or an abstract mid-span.
6. Write a pack manifest listing included and omitted evidence IDs and reason.
7. Delimit every source record as untrusted quoted data. Prompts state that instructions inside evidence are data.
8. Provide an explicit allowlist of evidence IDs. Structured output validation rejects references outside it.
9. Agents have no source tools and no artifact-write tool.

Acceptance:
- Same ledger/config produces byte-identical evidence packs.
- Prompt-injection fixture inside an abstract cannot change schema or reference unknown evidence.
- Omitted evidence is visible in pack metadata and final methods section.

### TODO `p6-claim-synthesis` — PR 12

Goal: turn frozen evidence into atomic, auditable claims.

Files to add:
- `adaseli/agents/claim_synthesizer.py`
- `adaseli/agents/claim_validation.py`
- `adaseli/pipeline/claims.py`
- `tests/agents/test_claim_synthesizer.py`
- `tests/agents/test_claim_validation.py`

Structured output contract:

```python
class ProposedClaimBundle(BaseModel):
    claims: list[ProposedClaim]
    uncovered_evidence_ids: list[str]
    conflicts: list[ProposedConflict]
```

Pipeline:
1. Call synthesis independently per evidence-pack domain/chunk.
2. Validate syntax/schema through provider adapter.
3. Reject unknown evidence IDs, missing scope, compound claims, unsupported numbers, and invalid relation types.
4. Split compound claims only through a deterministic rule when conjunction boundaries are unambiguous; otherwise reject and request one bounded repair.
5. Assign final claim IDs after sorting by claim type, normalized subject/predicate/object, and evidence IDs.
6. Deduplicate exact normalized claims. Do not semantic-merge claims using another untracked LLM call.
7. Numeric validator locates cited normalized values and units. Converted units require an explicit deterministic transformation record.
8. Publication mode:
   - factual claims require at least one `supports` edge;
   - identity scope must match resolved entity;
   - hypotheses are excluded from conclusion sections.
9. Exploratory mode:
   - still enforces identity and citations;
   - permits `hypothesis` claims only with observation, inference type, alternatives, limitations, and falsifiers.
10. Initial confidence is derived from evidence class/rules and remains provisional until verification.

Acceptance:
- Hallucinated citation fixture fails closed.
- GAL1/LGALS1 cross-scope claim fails.
- AlphaFold “confirms function/solubility” claim fails an evidence-class rule.
- GEO dataset mention cannot support gene expression.
- STRING text-mining-only edge cannot support physical interaction.

### TODO `p7-verifier-critic` — PR 13

Goal: verify entailment and expose uncertainty without creating new evidence.

Files to add:
- `adaseli/agents/evidence_verifier.py`
- `adaseli/agents/scientific_critic.py`
- `adaseli/agents/review_models.py`
- `adaseli/pipeline/verification.py`
- `tests/agents/test_evidence_verifier.py`
- `tests/agents/test_scientific_critic.py`

Verification order:
1. Deterministic identity, citation, pointer/span, numeric, unit, and evidence-class checks.
2. For surviving claims, send exactly one atomic claim plus only its cited evidence to verifier.
3. Verifier returns `supported`, `contradicted`, `insufficient`, or `mixed`, with cited edge IDs and concise rationale.
4. Core recomputes final status. LLM cannot override deterministic failure.
5. Accepted report facts require deterministic pass and verifier `supported`; `mixed` goes to conflicts/uncertainty.

Critic input/output:
- Input: resolved entity, accepted/rejected/mixed claims, evidence ledger summary, source coverage.
- Output: typed conflicts, alternative explanations, missing controls, possible source bias, falsifiers, and research gaps.
- Every critic item references claim/evidence IDs or is explicitly a methodological limitation.
- Critic cannot emit new factual biological claims.

Review independence labels:
- Same provider/model: `second_pass`.
- Different model, same provider: `independent_model`.
- Different provider/model: `independent_provider_model`.
- These labels concern model review only, never experimental replication.

Acceptance:
- Removing a cited evidence record invalidates dependent verification.
- Critic output with new unknown fact/evidence ID is rejected.
- Final confidence includes reasons/dimensions, not a fabricated precision score.

### TODO `p7-review-modes` — PR 14

Goal: separate three different reproducibility questions.

Files to add:
- `adaseli/review/__init__.py`
- `adaseli/review/audit.py`
- `adaseli/review/reproduce.py`
- `adaseli/review/compare.py`
- `adaseli/review/diff.py`
- `tests/review/`

`audit(run_id)`:
- Verify artifact hashes, schema versions, identity consistency, source accounting, claim citations, entailment results, report coverage, and disclaimer.
- Uses frozen artifacts; no source or provider call unless explicitly rerunning model verification.

`reproduce(run_id)`:
- Create a child run with `parent_run_id`.
- Reuse resolved stable identity unless user requests re-resolution; record choice.
- Execute fresh retrieval.
- Diff source plan, sanitized query fingerprint, source record IDs, raw/normalized hashes, parser versions, timestamps, status, and content-level values.
- Classify differences: source drift, HTTP failure, mapping drift, parser change, configuration change, cache change.

`compare(run_id, provider_models)`:
- Reuse identical frozen evidence packs.
- Run synthesis/verification across provider/model pairs.
- Match claims by normalized subject/predicate/object plus scope.
- Report agreement, unsupported-claim rate, omissions, contradiction labels, and cost/latency.
- Do not mix retrieval differences into provider comparison.

Compatibility:
- `research --review` invokes `audit` and warns that behavior changed.
- `--review-model` maps to verifier/critic model.
- Keep legacy review file naming for convenience, with canonical typed artifacts under run directory.

Acceptance:
- Status-only changes are not automatically “scientific red flags.”
- Reproduction diff explains the category of each difference.
- Provider comparison proves all models saw the same evidence-pack hash.

### TODO `p8-report-renderer` — PR 15

Goal: create readable reports whose statements remain traceable.

Files to add:
- `adaseli/reporting/__init__.py`
- `adaseli/reporting/renderer.py`
- `adaseli/reporting/sections.py`
- `adaseli/reporting/citations.py`
- `tests/reporting/test_renderer.py`
- `tests/reporting/golden/`

Do not call an LLM from reporting.

Required report order:
1. Title and run status.
2. Research scope and non-clinical disclaimer.
3. Resolved identity with stable IDs, organism, isoform, ambiguity notes.
4. Direct answer/bottom line using accepted claims only.
5. Annotation/function.
6. Structure/predictions with method caveats.
7. Network/interactions with evidence-channel labels.
8. Expression/omics distinguishing dataset mention from measured expression.
9. Literature with PMID/DOI and publication type.
10. Orthology/annotation transfer limits.
11. Conflicts and alternative explanations.
12. Hypotheses/falsifiers in exploratory mode only.
13. Gaps, failed/empty/skipped sources, truncation/pack omissions.
14. Methods: source queries, retrieval times, model roles, prompt hashes.
15. Reproduction command and artifact hashes.

Citation syntax:
- Claims: `[C0001]`.
- Evidence: `[E0001]` linked to local evidence JSON and external source record where available.
- Every factual bullet contains at least one accepted claim ID.
- Numeric value citations point to exact evidence pointer/span.

Rendering rules:
- Stable section and item ordering.
- Escape untrusted Markdown from source titles/snippets.
- Do not render empty boilerplate sections; render an explicit evidence-gap entry only when a source was planned and empty/error/skipped.
- Use source-provided terminology but add controlled evidence labels.
- Report `partial` prominently when required source retrieval failed.

Golden tests:
- Publication TP53.
- LGALS1 alias resolution.
- Sparse `slr1634`.
- Partial source failure.
- Exploratory hypotheses.
- No-protein/noncoding entity.

Acceptance:
- Same artifacts render byte-identically.
- Search the rendered report for every factual sentence/bullet and verify claim citation presence through a structural renderer test.
- Golden reports contain no “pLDDT confirms,” “GEO proves,” or unsupported STRING causality.

### TODO `p8-cli-cutover` — PR 16

Goal: expose v2 safely while preserving recognizable commands.

Files to modify/add:
- [`adaseli/cli.py`](adaseli/cli.py)
- `adaseli/application.py`
- `adaseli/pipeline/config.py`
- `tests/cli/test_research.py`
- `tests/cli/test_inspect.py`
- `tests/cli/test_review_commands.py`
- `docs/migration-v1-v2.md`

`ResearchConfig` minimum fields:
- query, taxon ID, optional explicit stable entity/protein ID;
- mode;
- output root/run directory;
- refresh/cache/offline settings;
- selected/disabled sources with reasons;
- synthesis provider/model;
- verifier provider/model;
- critic provider/model;
- model parameters;
- worker/retry/timeouts;
- legacy compatibility output path.

Commands:
- `adaseli research GENE`
- `adaseli inspect RUN_DIR`
- `adaseli audit RUN_DIR`
- `adaseli reproduce RUN_DIR`
- `adaseli compare RUN_DIR --provider-model PROVIDER:MODEL ...`
- retain `check`, `models`, `selftest`.

Flag mapping:
- `--provider/--model` map to synthesis role.
- `--report-model` maps to synthesis model with deprecation warning.
- `--review-model` maps to verifier and critic model.
- `--organism-name` validates resolved taxon name.
- `--string-species` and `--kegg-org` are deprecated validated overrides.
- `--review/--no-review` maps to post-run audit.
- Add `--engine legacy|v2` during preview; later default v2.

Exit/status policy:
- Exit 0: complete run.
- Exit 1: internal/provider/artifact failure.
- Exit 2: CLI/config validation.
- Exit 3: unresolved/ambiguous entity.
- Exit 10: partial run caused by required source failures; canonical partial report still exists.

Implementation steps:
1. Keep Typer command functions thin.
2. Add `application.run_research(config, dependencies)` for testable orchestration.
3. Dependency container supplies resolver, source registry, provider registry, HTTP client, clock, and artifact root.
4. `--offline` forbids network and succeeds only from fixture/cache data; fail with exact missing request fingerprints.
5. `inspect` validates hashes before showing summary.
6. `resume` may continue only a `RUNNING`/failed run with matching config/schema; never mutate a finalized run. Prefer child-run continuation if immutability conflicts.
7. Add migration examples for all README commands.

Acceptance:
- CliRunner tests cover old safe commands and new commands.
- Ambiguity error prints ranked candidates and selection flags.
- Partial and failed exit codes are stable/documented.

### TODO `p9-evaluation-release` — PR 17

Goal: demonstrate scientific and provider behavior before v2 becomes default.

Files to add:
- `evals/cases.yaml`
- `evals/annotations/*.json`
- `adaseli/evals/__init__.py`
- `adaseli/evals/runner.py`
- `adaseli/evals/metrics.py`
- `adaseli/evals/report.py`
- `tests/evals/`
- `docs/evaluation/methodology.md`
- `docs/evaluation/v2-results.md`
- `.github/workflows/scheduled-live.yml`
- release documentation/configuration.

Case schema:
- query and taxon;
- expected stable gene/protein IDs or expected ambiguity;
- permitted aliases/isoforms;
- frozen evidence ledger hash;
- human-annotated atomic claims;
- acceptable support evidence IDs/spans;
- prohibited overclaims;
- expected source applicability/status;
- mode-specific expected hypotheses/gaps.

Minimum benchmark composition:
- 5 human well-known genes with reviewed proteins.
- 5 alias/collision cases including GAL1/LGALS1.
- 5 nonhuman genes across at least two taxa.
- 3 sparse/uncharacterized genes.
- 2 noncoding/no-protein entities.
- 3 isoform-sensitive cases.
- 3 contradictory/partial-source cases.
- 3 prompt-injection/untrusted-text cases.

Metrics:
- Entity resolution accuracy and ambiguity recall.
- Cross-taxon error count.
- Planned-source accounting completeness.
- Evidence normalization accuracy.
- Accepted-claim entailment precision.
- Citation existence and pointer correctness.
- Numeric value/unit accuracy.
- Unsupported/overclaim count by severity.
- Contradiction and uncertainty recall.
- Provider schema success/repair/failure rate.
- Frozen-ledger claim agreement across providers.
- Runtime, token usage, and estimated cost; never combine cost with scientific quality into one score.

Release gates are those in Phase 9 plus:
- No P0/P1 open scientific-correctness bug.
- All schema changes documented with version/migration notes.
- Package build, wheel install, CLI smoke, SBOM, and provenance checks pass.
- Source/plugin author docs include a complete minimal adapter.
- Provider/plugin author docs include a complete fake adapter and conformance invocation.
- Example outputs are generated from frozen public/synthetic fixtures and include full manifests.

Scheduled live workflow:
- Manual/scheduled only.
- Query one low-cost record per source.
- Detect API/parser drift and open/report an issue; never auto-update fixtures.
- No provider keys required unless repository maintainers explicitly configure a separate provider smoke job.

Release sequence execution:
1. Tag alpha only after PRs 1–6.
2. Tag beta only after PRs 7–14 and frozen benchmark dry run.
3. Tag RC only after renderer/CLI/evaluation gates.
4. Make v2 default at RC; retain legacy engine for one release.
5. Remove legacy only in a later major release with explicit migration notice.

## 11. End-to-end v2 orchestration specification

The lower-model implementer should converge on this call sequence:

```python
def run_research(config: ResearchConfig, deps: Dependencies) -> RunResult:
    store = ArtifactStore.create(config.output_root, config)
    try:
        entity = deps.entity_resolver.resolve(
            config.query,
            config.taxon_id,
            explicit_entity_id=config.entity_id,
            explicit_uniprot=config.uniprot_accession,
        )
        store.write_model("entity.json", entity)
        require_resolved(entity)

        plan = build_source_plan(entity, deps.sources.all(), config.mode)
        store.write_model("source-plan.json", plan)
        ledger = retrieve(
            plan,
            deps.sources,
            store,
            deps.http,
            max_workers=config.max_workers,
        )
        store.write_model("evidence/ledger.json", ledger)

        packs = build_evidence_packs(entity, ledger, config, deps.prompts)
        claims = synthesize_claims(entity, packs, deps.synthesis_provider, config)
        verified = verify_claims(entity, ledger, claims, deps.verifier_provider, config)
        critique = critique_claims(entity, ledger, verified, deps.critic_provider, config)

        store.write_model("claims.json", verified)
        store.write_model("critique.json", critique)
        report = render_report(entity, plan, ledger, verified, critique, store.manifest_draft)
        store.write_bytes("report.md", report.encode("utf-8"), "text/markdown")

        status = derive_run_status(entity, plan, ledger, verified)
        manifest = store.finalize(status)
        write_compatibility_report(config.out, report, manifest)
        return RunResult(status=status, run_dir=store.run_dir)
    except Exception as exc:
        store.record_failure(exc)
        store.finalize_failed_if_possible()
        raise
```

Required invariants:
- No provider call occurs before identity is resolved and source evidence is persisted.
- No source call occurs from an agent.
- No report sentence bypasses validated claims.
- No finalized run mutates.
- Audit can reconstruct every rendered fact from local artifacts.
- Reproduction creates a child run; it does not replace original evidence.

## 12. Definition of v2 complete

V2 is complete only when a new contributor can:
1. Clone and run all ordinary tests without keys/network.
2. Execute a cached/offline example and obtain a complete immutable run bundle.
3. Trace any report fact to claim JSON, evidence pointer, normalized payload, raw payload hash, exact query, and source record.
4. Swap Anthropic, Ollama, or OpenRouter for synthesis without changing retrieval or report structure.
5. Add a source/provider plugin without editing core dispatch.
6. Re-audit a run without network.
7. Reproduce retrieval as a child run and receive content-level drift explanations.
8. See uncertainty and source limitations without reading prompts or logs.
9. Receive a hard stop for ambiguous biological identity.
10. Confirm from docs and output that the software is exploratory/publication-support research tooling, not clinical or diagnostic software.