# Roadmap

TrustForge is intentionally starting narrow: prove the trust primitives before expanding the catalog.

## v0.1 — Inspect and verify

- [x] SkillDiff static capability delta MVP
- [x] CommitmentGuard evidence verifier MVP
- [x] CLI entry point
- [x] Minimal unit tests
- [x] TrustForge skill contract draft

## v0.2 — SkillDiff trust-boundary analysis

- [x] Trigger-scope diff for `SKILL.md`
- [x] Evidence provenance with path + line + excerpt
- [x] Dependency delta
- [x] Secret-like environment access delta
- [x] Declared-vs-observed capability manifest
- [x] Human-readable risk explanations
- [x] JSON output
- [x] SARIF 2.1.0 output
- [x] Adversarial trigger-expansion eval fixture

## v0.3 — Structured analysis and adoption

- [x] Python AST detector
- [x] Alias-aware structured capability detection
- [x] AST evidence provenance and parse-error reporting
- [x] AST-backed SARIF findings
- [x] Adversarial AST alias eval fixture
- [x] Reusable composite GitHub Action
- [x] Self-test the GitHub Action with `uses: ./`
- [x] Changelog and release notes
- [x] Copy-paste GitHub Actions example
- [x] Floating stable `v0` action line

### SkillDiff research backlog

- [ ] JavaScript/TypeScript structured detectors
- [ ] Transitive dependency capability analysis
- [ ] Signed baseline manifests
- [ ] Sandboxed behavioral canary replay
- [ ] Richer trigger-scope models and benchmark datasets

## v0.4 — DataLease

Purpose-bound data projection for tool/API calls.

- field-level necessity rules;
- PII classification hooks;
- allow/deny/redact actions;
- MCP proxy reference implementation;
- audit log explaining why a field was shared.

## v0.5 — FreshPlan

Freshness-aware dependency graphs for long-running agents.

- fact provenance;
- TTL/validity windows;
- dependency edges from facts to plan nodes;
- selective invalidation and re-planning.

## v0.6 — ReproCapsule

Portable failure reproduction for coding agents.

- environment fingerprint;
- minimal failing inputs;
- sanitized traces;
- Docker/devcontainer export;
- replay verification.

## v1.0 goal

A stable, agent-agnostic trust layer with reusable contracts, evidence formats, evals, and adapters for major coding/agent runtimes.

## Research track

We maintain prior-art notes and avoid claims such as “first ever” unless they can be supported. The goal is useful open infrastructure, not novelty marketing.
