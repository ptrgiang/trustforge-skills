# Contributing

Thanks for helping make agent behavior more inspectable and verifiable.

## Good contributions

We especially welcome:

- adversarial eval cases that break a current detector;
- false-positive reductions with tests;
- new capability detectors with clear evidence;
- commitment evidence adapters;
- prior-art references;
- integrations with Codex, Claude Code, Cursor, Gemini CLI, MCP, and custom runtimes.

## Development

Install once:

```bash
python -m pip install -e .
```

Before pushing a development branch, run the shared preflight locally:

```bash
python scripts/preflight.py
```

The same preflight is used by GitHub Actions, so local and hosted gates stay aligned.

## Pull request workflow

TrustForge uses a low-noise development flow:

1. Create a feature branch instead of committing development work directly to `main`.
2. Run `python scripts/preflight.py` locally.
3. Push only after preflight passes.
4. Open a **Draft PR** while work is still changing. CI jobs are skipped for draft PRs.
5. Mark the PR **Ready for review** only after local preflight is green. That triggers the Python CI matrix and action smoke test.
6. Merge only after CI passes.

Direct pushes to `main` still run CI as a final post-merge verification, but ordinary feature-branch pushes do not run the workflow unless they belong to a non-draft PR.

## Pull request expectations

1. Keep the trust claim narrow and testable.
2. Add or update tests for behavior changes.
3. Document false positives and false negatives.
4. Do not describe heuristic detection as a security guarantee.
5. Avoid adding network calls or telemetry without an explicit design discussion.
6. Do not lower benchmark thresholds merely to make CI green. Record an explicit known baseline or fix the regression.

## Adding a new skill

A new skill should include a `SKILL.md` covering its problem, inputs, outputs, procedure, evidence model, failure modes, and eval plan. If it adds code, include tests that demonstrate at least one success case and one blocked/failure case.
