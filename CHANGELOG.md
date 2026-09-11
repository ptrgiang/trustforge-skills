# Changelog

All notable changes to TrustForge Skills are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows semantic versioning while it is pre-1.0.

## [Unreleased]

### Added

- DataLease purpose-bound payload projection engine.
- JSON/YAML policies with field-level `allow`, `redact`, and `deny` actions.
- Safe-default hard-deny classifiers, with `secret` enabled by default.
- PII/secret classifier hooks and nested wildcard paths.
- Redaction strategies for masking, nulling, last-four preservation, and email-domain preservation.
- Value-free decision audit trails.
- `trustforge datalease apply` CLI with payload-only and separate audit-report modes.
- DataLease policy schema, examples, unit tests, and CI smoke test.

### Planned

- DataLease MCP/HTTP interception adapter and pluggable classifier interface.
- JavaScript/TypeScript structured SkillDiff detectors.
- Transitive dependency capability analysis.
- Signed capability baselines.
- Sandboxed behavioral canary replay.

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

[Unreleased]: https://github.com/ptrgiang/trustforge-skills/compare/v0.3.0...main
[0.3.0]: https://github.com/ptrgiang/trustforge-skills/releases/tag/v0.3.0
[0.2.0]: https://github.com/ptrgiang/trustforge-skills/commits/abfadc6be0c3c4442696d5ed99b47134bd4eea3a
[0.1.0]: https://github.com/ptrgiang/trustforge-skills/commits/07631d19859f57dbf534039933b606cd0347c7d8
