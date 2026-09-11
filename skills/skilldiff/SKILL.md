---
name: skilldiff
description: Audit two versions of an AI agent skill and surface capability, file, and network-domain changes before the updated skill is trusted or installed.
license: Apache-2.0
metadata:
  trustforge:
    maturity: experimental
    category: supply-chain
    destructive: false
---

# SkillDiff

Use SkillDiff when an agent skill, prompt package, MCP helper, or repository automation has changed and you need to know whether the new version silently gained capabilities.

## Goal

Produce a human-readable and machine-readable change report that answers:

1. Which files were added, removed, or changed?
2. Which risky capabilities appear in the new version but not the old one?
3. Which outbound network domains are newly referenced?
4. What is the resulting risk level?

SkillDiff is intentionally **not** a malware detector and must not claim that a skill is safe merely because no risky patterns were found.

## Inputs

- `before`: directory containing the previously trusted skill version.
- `after`: directory containing the candidate skill version.

## Output

A report containing:

- file delta;
- added/removed capability classes;
- source files that triggered capability detection;
- added/removed network domains;
- heuristic risk score and level.

Current MVP capability classes:

- `network`
- `subprocess`
- `environment_read`
- `filesystem_read`
- `filesystem_write`
- `dynamic_execution`
- `credential_material`

## Procedure

1. Resolve both directories without executing their contents.
2. Hash supported text files and calculate the file delta.
3. Scan text and source files for capability indicators.
4. Extract explicit HTTP(S) domains.
5. Compare the old and new capability sets.
6. Increase risk based only on **new** capabilities/domains.
7. Return evidence paths so a reviewer can inspect why a capability was flagged.

## CLI

```bash
trustforge skilldiff ./skill-v1 ./skill-v2
```

Machine-readable output:

```bash
trustforge skilldiff ./skill-v1 ./skill-v2 --json
```

Fail CI when the candidate introduces medium-or-higher risk:

```bash
trustforge skilldiff ./skill-v1 ./skill-v2 --fail-on medium
```

Exit codes:

- `0`: report generated and threshold not reached.
- `2`: configured risk threshold reached.

## Evidence rules

When reporting a capability change:

- identify the capability by name;
- include the file(s) that triggered it;
- distinguish a newly added capability from one that already existed;
- do not infer intent from the pattern alone.

Good:

> `subprocess` is newly detected in `scripts/install.py`.

Bad:

> This update is malicious.

## Failure modes

SkillDiff may miss capabilities implemented through:

- obfuscation;
- generated code;
- binaries;
- runtime downloads;
- unusual language APIs;
- indirect dependencies.

False positives are also possible because pattern detection is heuristic.

## Future work

- AST-based detectors per language;
- package/dependency capability analysis;
- behavioral canary replay in a sandbox;
- trigger-scope diff for `SKILL.md` descriptions;
- signed baseline manifests;
- SARIF output for code scanning UIs.
