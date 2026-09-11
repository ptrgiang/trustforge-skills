# Roadmap

TrustForge is intentionally starting narrow: prove the trust primitives before expanding the catalog.

## v0.1 — Inspect and verify

- [x] SkillDiff static capability delta MVP
- [x] CommitmentGuard evidence verifier MVP
- [x] CLI entry point
- [x] Minimal unit tests
- [x] TrustForge skill contract draft
- [ ] Trigger-scope diff for SKILL.md
- [ ] Rich evidence provenance
- [ ] SARIF output
- [ ] More language-aware capability detectors

## v0.2 — DataLease

Purpose-bound data projection for tool/API calls.

- field-level necessity rules;
- PII classification hooks;
- allow/deny/redact actions;
- MCP proxy reference implementation;
- audit log explaining why a field was shared.

## v0.3 — FreshPlan

Freshness-aware dependency graphs for long-running agents.

- fact provenance;
- TTL/validity windows;
- dependency edges from facts to plan nodes;
- selective invalidation and re-planning.

## v0.4 — ReproCapsule

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
