# ReproCapsule

Status: v0.6 development

ReproCapsule packages failure context into a portable, sanitized artifact and can verify whether the declared failure still reproduces.

## Build

```bash
trustforge reprocapsule build \
  --spec examples/reprocapsule/example-spec.yaml \
  --output .artifacts/reprocapsule
```

The build step does not execute the failing command. It records the command, expected exit code / optional failure signature, hashes explicitly listed inputs, sanitizes the supplied trace, and records a runtime fingerprint without raw environment values.

## Replay verification

Integrity-only preflight is the default:

```bash
trustforge reprocapsule replay \
  --capsule .artifacts/reprocapsule
```

Actual execution requires explicit opt-in:

```bash
trustforge reprocapsule replay \
  --capsule .artifacts/reprocapsule \
  --execute \
  --fail-on-divergence
```

Replay follows this sequence:

```text
manifest
   ↓
verify packaged SHA-256 + sizes
   ↓
copy inputs into an isolated temporary workspace
   ↓
explicit --execute gate
   ↓
run command with shell=False and a minimal environment
   ↓
compare exit code + literal failure signature
   ↓
reproduced / diverged
```

A tampered or missing packaged input blocks execution before the command is started.

## Decisions

- `ready`: integrity passed, but execution was not explicitly requested.
- `reproduced`: all declared replay expectations matched.
- `diverged`: replay executed but exit code and/or failure signature did not match.
- `blocked`: integrity or replay prerequisites failed before execution.

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

ReproCapsule fails closed when:

- input paths are absolute or escape the spec directory;
- a requested input looks like `.env`, SSH/AWS/GPG credential material, or another protected credential filename;
- command arguments appear to contain API keys, passwords, bearer tokens, access tokens, or private-key material;
- required inputs or trace files are missing;
- packaged files fail hash/size verification;
- replay has neither an expected exit code nor a failure signature;
- unknown spec fields are supplied.

Replay execution is deliberately explicit. The current temporary workspace is **not a security sandbox**. The command can still access resources available to the operating-system process. The replay runner reduces accidental environment inheritance and uses `shell=False`, but untrusted capsules should not be executed outside a real sandbox/container.

Trace and replay-output sanitization handles common secret assignments, bearer tokens, GitHub-style tokens, OpenAI-style `sk-` tokens, and AWS access-key identifiers. This is a defensive baseline, not a guarantee that arbitrary secrets cannot appear.

## Still planned

- Dockerfile/devcontainer export;
- stronger sandboxed replay;
- adversarial trace-redaction fixtures;
- dependency/environment lock capture;
- signed capsule manifests.