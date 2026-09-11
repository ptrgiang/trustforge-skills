# ReproCapsule container replay

Development target: `0.6.0.dev4`.

Container replay adds an explicit Docker execution boundary after capsule integrity verification.

```bash
trustforge reprocapsule replay-container \
  --capsule .artifacts/reprocapsule
```

Without `--execute`, this is an integrity-only preflight and Docker is not touched.

Actual build/run requires explicit opt-in:

```bash
trustforge reprocapsule replay-container \
  --capsule .artifacts/reprocapsule \
  --execute \
  --fail-on-divergence
```

Runtime defaults:

- `--network none`;
- read-only root filesystem;
- `/tmp` tmpfs with `noexec,nosuid`;
- all Linux capabilities dropped;
- `no-new-privileges`;
- PID limit 128;
- memory limit 512 MiB;
- CPU limit 1.0;
- no captured environment values injected;
- bounded build and run timeouts;
- integrity verification before Docker build;
- replay stdout/stderr sanitized before reporting.

These controls reduce attack surface but are **not** presented as a complete security sandbox. Docker daemon access remains privileged infrastructure and untrusted workloads may require stronger isolation such as dedicated workers, microVMs, seccomp/AppArmor profiles, or rootless container infrastructure.

The build step may still need registry/network access when the base image is not cached. Runtime network access is disabled.
