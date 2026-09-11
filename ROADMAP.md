# Roadmap

TrustForge is intentionally starting narrow: prove the trust primitives before expanding the catalog.

## v0.1 — Inspect and verify

- [x] SkillDiff static capability delta MVP
- [x] CommitmentGuard evidence verifier MVP
- [x] CLI entry point
- [x] Minimal unit tests
- [x] TrustForge skill contract draft

## v0.2 — SkillDiff flagship

- [x] Trigger-scope diff for `SKILL.md`
- [x] Evidence provenance with path + line + excerpt
- [x] Dependency delta
- [x] Secret-like environment access delta
- [x] Declared-vs-observed capability manifest
- [x] Human-readable risk explanations
- [x] JSON output
- [x] SARIF 2.1.0 output
- [x] Adversarial trigger-expansion eval fixture
- [ ] Language-aware AST detectors
- [ ] Transitive dependency capability analysis
- [ ] Sandboxed behavioral canary replay
- [ ] Signed baseline manifests

## v0.3 — DataLease

Purpose-bound data projection for tool/API calls.

- field-level necessity rules;
- PII classification hooks;
- allow/deny/redact actions;
- MCP proxy reference implementation;
- audit log explaining why a field was shared.

## v0.4 — FreshPlan

Freshness-aware dependency graphs for long-running agents.

- fact provenance;
- TTL/validity windows;
- dependency edges from facts to plan nodes;
- selective invalidation and re-planning.

## v0.5 — ReproCapsule

Portable failure reproduction for coding agents.

- environment fingerprint;
- minimal failing inputs;
- sanitized traces;
- Docker/devcontainer export;
- replay verification.

## v1.0 goal

A stable, agent-agnostic trust layer with reusable contracts, evidence formats, evals, and adapters for major coding/agent runtimes.

## Research track

We will maintain prior-art notes and avoid claims such as “first ever” unless they can be supported. The goal is useful open infrastructure, not novelty marketing.
