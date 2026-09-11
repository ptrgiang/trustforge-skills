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
- [x] Release `v0.3.0`

### SkillDiff research backlog

- [ ] JavaScript/TypeScript structured detectors
- [ ] Transitive dependency capability analysis
- [ ] Signed baseline manifests
- [ ] Sandboxed behavioral canary replay
- [ ] Richer trigger-scope models and benchmark datasets

## v0.4 — DataLease

Purpose- and destination-bound minimum-necessary data projection before tool/API/MCP calls.

- [x] Purpose-bound transfer authorization
- [x] Field-path allow/redact/deny rules
- [x] JSON and YAML policy loading
- [x] Built-in PII/secret classifier hooks
- [x] Configurable hard-deny classifiers with `secret` safe default
- [x] Nested wildcard paths such as `items.*.sku`
- [x] Redaction strategies (`mask`, `null`, `last4`, `email_domain`)
- [x] Value-free audit trail explaining every leaf decision
- [x] CLI with payload-only and separate audit output
- [x] Policy JSON Schema, examples, unit tests, and CI smoke test
- [x] Reference sync/async HTTP interception adapter
- [x] Reference sync/async MCP tool-call adapter
- [x] Destination binding for HTTP scheme/host/method and MCP tool patterns
- [x] Pluggable classifier interface with provenance/confidence
- [x] Fail-closed classifier plugin errors
- [x] Primary precision/recall benchmark fixture and CI thresholds
- [x] Multilingual/domain regression fixture
- [x] Built-in classifier label/version contract
- [x] Release notes and release checklist
- [x] Release `v0.4.0` and advance stable `v0`

### DataLease research backlog

- [ ] Larger multilingual/domain-specific benchmark datasets
- [ ] Govern HTTP query parameters, headers, multipart, and streaming payloads
- [ ] Concrete integrations for selected popular HTTP/MCP client stacks
- [ ] Classifier sandboxing/isolation model

## v0.5 — FreshPlan

Freshness-aware dependency graphs and conservative recovery for long-running agents.

- [x] Metadata-only fact contract with provenance
- [x] TTL and explicit `valid_until` freshness windows
- [x] Dependency edges from facts to plan nodes and node-to-node edges
- [x] Timezone-aware deterministic `--as-of` evaluation
- [x] Fail-closed handling for future-dated observations
- [x] Selective invalidation instead of whole-plan invalidation
- [x] Root stale-fact propagation through affected descendants
- [x] Topological `replan_order` plus unaffected-node reporting
- [x] Cycle, self-dependency, and unknown-reference rejection
- [x] CLI, JSON output, and `--fail-on-stale` orchestration gate
- [x] JSON Schema, example, unit tests, eval fixture, and CI smoke gate
- [x] Value-free refresh-request contract
- [x] Explicit replacement-evidence contract
- [x] `changed | unchanged | unknown` replacement semantics
- [x] Minimal `blocked | replan | resume` plan-patch contract
- [x] Trusted Python refresh-adapter interface with fail-closed errors
- [x] CLI `freshplan requests` and `freshplan patch`
- [x] Refresh/patch schemas, examples, unit tests, eval fixture, and CI gates
- [x] Named freshness policies with soft `refresh_after_seconds` and hard `expire_after_seconds`
- [x] `fresh | refresh_due | stale` state model with proactive refresh requests
- [x] Policy-bound replacement evidence can preserve existing freshness policy
- [x] Deterministic large-graph benchmark CLI
- [x] 10k-node CI performance regression gate
- [x] Freeze FreshPlan contract/version compatibility notes
- [x] Prepare v0.5.0 release notes and checklist
- [x] Finalize package/runtime version to `0.5.0`
- [x] Run final CI/release-candidate matrix
- [x] Release `v0.5.0` and advance stable `v0`

### FreshPlan research backlog

- [ ] Async refresh adapter interface
- [ ] Runtime integrations for long-running agent frameworks
- [ ] Persistent state-store adapter for applying replacement metadata without copying raw values into reports
- [ ] Larger and more varied graph-shape benchmarks
- [ ] Domain-specific freshness-policy profiles and policy linting

## v0.6 — ReproCapsule

Portable failure reproduction for coding agents and autonomous debugging workflows.

- [x] ReproCapsule build spec and schema v0.1
- [x] Environment fingerprint without raw environment values
- [x] Explicit failing-input packaging with SHA-256 integrity metadata
- [x] Sanitized trace packaging
- [x] Fail-closed sensitive path and secret-like command checks
- [x] `trustforge reprocapsule build` CLI
- [x] Example capsule fixture, unit tests, and CI smoke gate
- [x] Replay verification with expected exit code / failure signature
- [x] Replay integrity checks before command execution
- [x] Explicit `--execute` gate and bounded timeout
- [x] Temporary replay workspace with `shell=False` and reduced environment inheritance
- [x] `ready | reproduced | diverged | blocked` replay decision contract
- [ ] Dockerfile/devcontainer export
- [ ] Additional trace redaction benchmark/adversarial fixtures
- [ ] Sandboxed/containerized replay runner
- [ ] Release hardening for `v0.6.0`

### ReproCapsule research backlog

- [ ] Cross-platform dependency/environment lock capture
- [ ] Framework adapters for coding-agent traces
- [ ] Reproduction minimization / input reduction
- [ ] Signed capsule manifests

## v1.0 goal

A stable, agent-agnostic trust layer with reusable contracts, evidence formats, evals, and adapters for major coding/agent runtimes.

## Research track

We maintain prior-art notes and avoid claims such as “first ever” unless they can be supported. The goal is useful open infrastructure, not novelty marketing.
