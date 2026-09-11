# Changelog

All notable changes to TrustForge Skills are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows semantic versioning while it is pre-1.0.

## [Unreleased]

### Added

- FreshPlan v0.5 MVP for freshness-aware plan dependency graphs.
- Fact provenance plus TTL/absolute validity windows.
- Selective invalidation from stale facts through dependent plan nodes.
- Root-cause propagation and dependency-safe `replan_order` output.
- `trustforge freshplan check` CLI with deterministic `--as-of` and `--fail-on-stale` gating.
- FreshPlan JSON Schema, example plan, unit tests, selective-invalidation eval fixture, and CI smoke gate.

### Changed

- Development package version advanced to `0.5.0.dev0` while stable `v0` remains on `v0.4.0`.

### Planned

- FreshPlan fact refresh adapters and explicit plan patch format.
- Larger FreshPlan graph benchmarks and richer freshness policies.
- Larger multilingual/domain-specific DataLease benchmarks.
- JavaScript/TypeScript structured SkillDiff detectors.
- Transitive dependency capability analysis.

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

[Unreleased]: https://github.com/ptrgiang/trustforge-skills/compare/v0.4.0...main
[0.4.0]: https://github.com/ptrgiang/trustforge-skills/releases/tag/v0.4.0
[0.3.0]: https://github.com/ptrgiang/trustforge-skills/releases/tag/v0.3.0
[0.2.0]: https://github.com/ptrgiang/trustforge-skills/commits/abfadc6be0c3c4442696d5ed99b47134bd4eea3a
[0.1.0]: https://github.com/ptrgiang/trustforge-skills/commits/07631d19859f57dbf534039933b606cd0347c7d8
