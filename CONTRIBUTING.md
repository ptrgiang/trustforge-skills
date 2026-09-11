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

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

Try the verifier:

```bash
trustforge verify examples/refactor-contract.json --evidence examples/refactor-evidence.json
```

## Pull request expectations

1. Keep the trust claim narrow and testable.
2. Add or update tests for behavior changes.
3. Document false positives and false negatives.
4. Do not describe heuristic detection as a security guarantee.
5. Avoid adding network calls or telemetry without an explicit design discussion.

## Adding a new skill

A new skill should include a `SKILL.md` covering its problem, inputs, outputs, procedure, evidence model, failure modes, and eval plan. If it adds code, include tests that demonstrate at least one success case and one blocked/failure case.
