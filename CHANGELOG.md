# Changelog

All notable changes to TrustForge Skills are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows semantic versioning while it is pre-1.0.

## [Unreleased]

### Planned

- Cross-platform dependency/environment lock capture for ReproCapsule.
- Framework adapters for coding-agent traces.
- FreshPlan async refresh adapters and runtime integrations.
- Larger multilingual/domain-specific DataLease benchmarks.
- JavaScript/TypeScript structured SkillDiff detectors.
- Transitive dependency capability analysis.

## [0.6.0] - 2026-09-11

### Added

- ReproCapsule v0.6 build spec and schema.
- `trustforge reprocapsule build` CLI.
- Portable reproduction manifest with OS/Python environment fingerprint.
- Explicit failing-input packaging with SHA-256 integrity metadata.
- Sanitized trace packaging with common secret redaction.
- Environment-variable presence capture without raw values.
- Fail-closed checks for secret-like command arguments, path traversal, and sensitive credential/config inputs.
- `trustforge reprocapsule replay` integrity preflight and explicit `--execute` replay mode.
- Replay expectations using exit code and optional literal failure signature.
- Replay decisions: `ready`, `reproduced`, `diverged`, and `blocked`.
- Integrity verification before execution, including packaged input and trace hashes/sizes.
- Temporary replay workspace, bounded timeout, `shell=False`, and reduced environment inheritance.
- Replay report JSON Schema plus CI gates for reproduction and tamper blocking.
- `trustforge reprocapsule export-container` for Docker/devcontainer build-context generation.
- Generated non-root Docker runtime user and Python base image derived from the capsule runtime fingerprint.
- Self-contained export context with verified inputs, manifest, sanitized trace, Dockerfile, `.dockerignore`, devcontainer configuration, and export metadata.
- `trustforge reprocapsule replay-container` with integrity-gated Docker build/run and explicit `--execute` opt-in.
- Container replay runtime controls for disabled network, read-only root filesystem, tmpfs `/tmp`, dropped Linux capabilities, no-new-privileges, PID/memory/CPU limits, and bounded timeouts.
- Docker build-stage network disablement for generated replay contexts.
- Container replay report JSON Schema and injected-runner unit tests.
- `trustforge reprocapsule benchmark-redaction` for adversarial sanitizer regression testing.
- Synthetic redaction benchmark covering secret assignments, bearer headers, quoted JSON secret fields, GitHub/OpenAI-style tokens, AWS access keys, mixed multiline traces, and clean near-miss text.
- Case-level secret recall and clean specificity metrics with configurable CI thresholds.
- Machine-readable ReproCapsule redaction benchmark report schema.
- Shared `scripts/preflight.py` validation used locally and by CI.
- Draft-PR development flow so intermediate development commits can avoid noisy CI failures.

### Changed

- Package version advanced to `0.6.0`.
- ReproCapsule release benchmark now gates the bundled adversarial fixture at 1.0 secret recall and 1.0 clean specificity.
- Bearer trace redaction now avoids the known plain-English `Bearer authentication` false positive in the release fixture.
- Quoted JSON secret fields such as `"refresh_token": "..."` are sanitized.

### Security

- Capsule build never executes the declared command.
- Raw environment values are not captured by ReproCapsule.
- Replay does not execute by default; `--execute` is required explicitly.
- Tampered or missing packaged inputs block execution before the declared command starts.
- Host replay uses `shell=False`, a temporary workspace, bounded timeout, and reduced environment inheritance.
- Replay stdout/stderr are sanitized before being returned.
- Container export verifies capsule integrity before copying files or generating runtime definitions.
- Container export never builds or executes the generated container automatically.
- Container replay verifies integrity before build/run and applies conservative Docker restrictions.
- Redaction regressions fail CI when the bundled benchmark drops below release thresholds.
- Host/container replay are not claimed to be complete security sandboxes.

## [0.5.0] - 2026-09-11

### Added

- FreshPlan v0.5 freshness-aware plan dependency graphs.
- Fact provenance plus TTL/absolute validity windows.
- Selective invalidation from stale facts through dependent plan nodes.
- Root-cause propagation and dependency-safe `replan_order` output.
- `trustforge freshplan check` CLI with deterministic `--as-of` and `--fail-on-stale` gating.
- FreshPlan JSON Schema, example plan, unit tests, selective-invalidation eval fixture, and CI smoke gate.
- Value-free refresh-request generation for stale facts with explicit adapter names and opaque refresh references.
- Trusted Python `FactRefreshAdapter` / `CallableRefreshAdapter` interface with fail-closed adapter errors.
- Strict replacement-evidence contract that rejects raw value fields and requires explicit `changed`, `unchanged`, or `unknown` semantics.
- Minimal FreshPlan control patch with `blocked`, `replan`, and `resume` node operations.
- Conservative handling where `unknown` replacement changes trigger re-planning instead of resuming old reasoning.
- `trustforge freshplan requests` and `trustforge freshplan patch` CLI commands.
- Refresh-request, replacement-evidence, and plan-patch JSON Schemas plus deterministic refresh/patch eval fixtures.
- Reference refresh adapter demo and CI gates for request generation, replacement patching, adapter execution, and replan exit codes.
- Named FreshPlan freshness policies with soft `refresh_after_seconds` and hard `expire_after_seconds` boundaries.
- `refresh_due` fact state and proactive refresh requests that do not invalidate still-valid plan branches.
- Policy-aware replacement handling that can preserve an existing named policy when evidence omits new TTL/absolute-expiry fields.
- `trustforge freshplan benchmark` deterministic large-graph performance runner with nodes/edges/throughput metrics.
- 10k-node FreshPlan CI performance regression gate.
- FreshPlan v0.5.0 release notes and release checklist.

### Changed

- FreshPlan topological scheduling now uses a heap-backed ready queue for more predictable large-graph behavior.
- Package version advanced to `0.5.0`.
- `refresh_due` recommends proactive refresh without invalidating dependent nodes; only `stale` evidence invalidates.

### Security

- Freshness reports and refresh requests intentionally omit raw fact values.
- Future-dated observations fail closed as stale/suspicious freshness evidence.
- Adapter execution remains explicit trusted application code; the CLI does not dynamically import adapters.
- Adapter failures, wrong-fact evidence, malformed replacement evidence, graph cycles, and unknown dependencies fail closed.

## [0.4.0] - 2026-09-11

### Added

- DataLease purpose-bound payload projection engine.
- JSON/YAML policies with field-level `allow`, `redact`, and `deny` actions.
- Safe-default hard-deny classifiers, with `secret` enabled by default.
- Built-in PII/secret/network classifier hooks and nested wildcard paths.
- Redaction strategies for masking, nulling, last-four preservation, and email-domain preservation.
- Value-free decision audit trails with classifier provenance/confidence.
- `trustforge datalease apply` CLI with payload-only and separate audit-report modes.
- Sync and async HTTP interception adapters that sanitize JSON before transport execution.
- Sync and async MCP tool-call adapters that sanitize arguments before dispatch.
- Destination binding for HTTP schemes/hosts/methods and MCP tool patterns.
- `DataLeaseBlocked` refusal before unauthorized transports execute.
- Explicit pluggable classifier interface for trusted application code.
- Fail-closed handling for classifier plugin exceptions.
- `trustforge datalease benchmark` precision/recall/F1 regression runner.
- Primary adversarial classifier benchmark plus multilingual/domain regression fixture.
- Built-in classifier label/version contract.
- DataLease v0.4 release notes and checklist.

### Changed

- Package version advanced to `0.4.0`.
- Secret-name classification now recognizes authorization-style fields.
- Phone heuristics avoid several identifier/date/IP false positives covered by evals.

### Security

- Hard-deny classifier checks run before ordinary allow rules.
- Destination authorization and purpose authorization happen before wrapped HTTP/MCP dispatch.
- Classifier audit evidence intentionally omits raw field values.

## [0.3.0] - 2026-09-11

### Added

- Python AST capability detector using the standard-library `ast` module.
- Alias-aware detection for common network, subprocess, environment, filesystem, and dynamic-execution calls.
- AST evidence with source path, line, symbol, detector, and confidence.
- AST parse-error reporting instead of silently treating unparsed Python as fully scanned.
- SARIF findings for AST-discovered trust-boundary changes.
- Reusable composite GitHub Action in `action.yml`.
- Self-test job that exercises the repository as a local GitHub Action.
- Adversarial `python-ast-alias` eval fixture.

### Changed

- SkillDiff report schema advanced to `0.3`.
- Package version advanced to `0.3.0`.
- Capability manifest comparison now includes structured-detector findings.
- Documentation and skill specification updated for v0.3.

## [0.2.0] - 2026-09-11

### Added

- Trigger-scope expansion heuristic for `SKILL.md`.
- Evidence provenance with file, line, and excerpt.
- Dependency delta analysis.
- Secret-like environment reference detection.
- Declared-vs-observed capability manifests.
- JSON and SARIF 2.1.0 output.
- Adversarial trigger-expansion eval fixture.

## [0.1.0] - 2026-09-11

### Added

- Initial SkillDiff static capability-delta MVP.
- Initial CommitmentGuard evidence verifier.
- CLI, tests, contracts, examples, CI, security policy, and contributing guide.

[Unreleased]: https://github.com/ptrgiang/trustforge-skills/compare/v0.6.0...main
[0.6.0]: https://github.com/ptrgiang/trustforge-skills/releases/tag/v0.6.0
[0.5.0]: https://github.com/ptrgiang/trustforge-skills/releases/tag/v0.5.0
[0.4.0]: https://github.com/ptrgiang/trustforge-skills/releases/tag/v0.4.0
[0.3.0]: https://github.com/ptrgiang/trustforge-skills/releases/tag/v0.3.0
[0.2.0]: https://github.com/ptrgiang/trustforge-skills/commits/abfadc6be0c3c4442696d5ed99b47134bd4eea3a
[0.1.0]: https://github.com/ptrgiang/trustforge-skills/commits/07631d19859f57dbf534039933b606cd0347c7d8
