# ReproCapsule

Status: v0.6 development

ReproCapsule packages failure context into a portable, sanitized artifact that another developer or agent can inspect and replay later.

## Why

Failure reports from autonomous coding agents are often incomplete or machine-specific. A useful reproduction needs more than a stack trace: it needs the failing command, relevant inputs, environment fingerprint, and enough integrity metadata to tell whether the capsule changed in transit.

ReproCapsule v0.6 starts with a conservative build step that does **not** execute the failing command.

## Build

```bash
trustforge reprocapsule build \
  --spec examples/reprocapsule/example-spec.yaml \
  --output .artifacts/reprocapsule
```

JSON report:

```bash
trustforge reprocapsule build \
  --spec examples/reprocapsule/example-spec.yaml \
  --output .artifacts/reprocapsule \
  --json
```

## Capsule contents

A capsule can contain:

- `reprocapsule.json`: portable manifest;
- copied failing inputs explicitly listed by the spec;
- SHA-256 and size metadata for packaged inputs;
- sanitized failure trace;
- OS, architecture, Python version, and implementation fingerprint;
- environment variable **presence** metadata for explicitly named variables.

Raw environment values are not captured.

## Safety boundaries

ReproCapsule v0.6 MVP fails closed when:

- input paths are absolute or escape the spec directory;
- a requested input looks like `.env`, SSH/AWS/GPG credential material, or another protected credential filename;
- command arguments appear to contain API keys, passwords, bearer tokens, access tokens, or private-key material;
- required inputs or trace files are missing;
- unknown spec fields are supplied.

Trace sanitization handles common secret assignments, bearer tokens, GitHub-style tokens, OpenAI-style `sk-` tokens, and AWS access-key identifiers. This is a defensive baseline, not a guarantee that arbitrary secrets cannot appear in a trace.

## Non-goals in the MVP

The build step does not:

- execute or replay the command;
- capture raw environment values;
- automatically crawl the filesystem for inputs;
- package secret-bearing configuration files;
- create Docker/devcontainer definitions yet;
- prove that the failure reproduces elsewhere.

Replay verification and container/devcontainer export are planned next.