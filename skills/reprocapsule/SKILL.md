# ReproCapsule

Status: v0.6 development

ReproCapsule packages failure context into a portable, sanitized artifact, verifies whether the declared failure still reproduces, and can export a verified capsule into a Docker/devcontainer build context.

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

Replay verifies packaged SHA-256 and sizes before execution, copies inputs into a temporary workspace, uses `shell=False` with reduced environment inheritance, then compares the observed exit code and optional literal failure signature.

Decisions are `ready`, `reproduced`, `diverged`, or `blocked`.

## Container export

```bash
trustforge reprocapsule export-container \
  --capsule .artifacts/reprocapsule \
  --output .artifacts/reprocapsule-container
```

Export first verifies capsule integrity. A successful export includes:

- `Dockerfile`;
- `.dockerignore`;
- `.devcontainer/devcontainer.json`;
- `reprocapsule.json`;
- `container-export.json`;
- verified packaged inputs;
- the sanitized trace when present.

The Python base image is derived from the captured runtime major/minor version. The generated Dockerfile uses a non-root `repro` user and preserves the declared replay command as JSON-array `CMD`.

Container export deliberately does **not** build or execute Docker. It also does not inject environment values or secrets.

## Safety boundaries

ReproCapsule fails closed when:

- input paths are absolute or escape the spec directory;
- a requested input looks like `.env`, SSH/AWS/GPG credential material, or another protected credential filename;
- command arguments appear to contain API keys, passwords, bearer tokens, access tokens, or private-key material;
- required inputs or trace files are missing;
- packaged files fail hash/size verification;
- replay has neither an expected exit code nor a failure signature;
- container export is requested from a tampered capsule;
- the export output would overwrite the capsule directory or one of its parent directories;
- unknown spec fields are supplied.

The temporary replay workspace and generated container definition are **not claimed to be complete security sandboxes**. Untrusted capsules still require a hardened runtime/container policy. The current container export also does not capture arbitrary native/system dependency locks.

Trace and replay-output sanitization handles common secret assignments, bearer tokens, GitHub-style tokens, OpenAI-style `sk-` tokens, and AWS access-key identifiers. This is a defensive baseline, not a guarantee that arbitrary secrets cannot appear.

## Still planned

- stronger sandboxed/containerized replay;
- adversarial trace-redaction fixtures;
- dependency/environment lock capture;
- signed capsule manifests.