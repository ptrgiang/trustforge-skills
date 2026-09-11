# TrustForge Skills

> **Don't just let agents act. Make them prove it.**

TrustForge Skills is an open-source collection of reliability, verification, privacy, and safety primitives for autonomous AI agents.

The project starts from a simple observation: as agent ecosystems grow, the hard problem is no longer only *what can an agent do?* It is also:

- Did a skill silently gain new capabilities?
- Did the agent satisfy every user constraint before claiming completion?
- Did it expose more data than the task required?
- Is the plan still valid after external facts changed?
- Can a failure be reproduced by another developer?

TrustForge turns those questions into reusable skills, contracts, evidence, and evals.

## v0.1 focus

| Skill | Purpose | Status |
| --- | --- | --- |
| **SkillDiff** | Detect capability and behavioral changes between skill versions | 🚧 MVP |
| **CommitmentGuard** | Require evidence for user constraints before an agent can claim completion | 🚧 MVP |
| **DataLease** | Minimize and gate data shared with tools/APIs | 🧭 Planned |
| **FreshPlan** | Invalidate plan nodes when facts become stale | 🧭 Planned |
| **ReproCapsule** | Package failures into reproducible environments | 🧭 Planned |

## Core idea

```text
SkillDiff → DataLease → FreshPlan → CommitmentGuard → ReproCapsule

Can I trust this skill?
        ↓
What data may it use?
        ↓
Are its assumptions still fresh?
        ↓
Did it actually finish the job?
        ↓
Can we reproduce the failure?
```

## Quick start

Clone the repository and inspect the first two skills:

```bash
git clone https://github.com/ptrgiang/trustforge-skills.git
cd trustforge-skills

cat skills/skilldiff/SKILL.md
cat skills/commitment-guard/SKILL.md
```

Once the Python MVP lands, the intended CLI is:

```bash
trustforge skilldiff ./before-skill ./after-skill
trustforge verify ./commitments.yaml --evidence ./evidence.json
```

## Design principles

1. **Evidence over confidence** — an agent saying “done” is not proof.
2. **Least capability** — new filesystem, network, subprocess, secret, or environment access should be visible.
3. **Least data** — tools should receive only fields necessary for the declared purpose.
4. **Freshness is explicit** — facts used in plans should have provenance and validity windows.
5. **Failures should travel** — a bug report is more useful when another machine can reproduce it.
6. **Agent-agnostic by default** — skills should be usable from Codex, Claude Code, Cursor, Gemini CLI, MCP-based agents, and custom runtimes.
7. **No unverifiable novelty claims** — TrustForge documents prior art and focuses on measurable capability gaps.

## Repository layout

```text
trustforge-skills/
├── skills/
│   ├── skilldiff/
│   └── commitment-guard/
├── trustforge/
├── contracts/
├── examples/
├── evals/
├── tests/
└── .github/workflows/
```

## What makes a TrustForge skill?

A TrustForge skill should define:

- a narrow trust/reliability problem;
- explicit inputs and outputs;
- capabilities and side effects;
- machine-checkable evidence where possible;
- failure modes and refusal conditions;
- eval cases demonstrating both success and failure.

## Roadmap

See [`ROADMAP.md`](ROADMAP.md).

## Contributing

Contributions are welcome, especially adversarial eval cases, integrations with agent runtimes, and prior-art references. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security

TrustForge analyzes agent capabilities and may eventually execute sandboxed canary tasks. Please read [`SECURITY.md`](SECURITY.md) before reporting security-sensitive findings.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
