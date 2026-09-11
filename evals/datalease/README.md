# DataLease classifier evals

This directory contains deterministic, synthetic evaluation fixtures for DataLease field classification.

## Baseline dataset

`classifier-benchmark.jsonl` currently contains 30 cases spanning:

- email, phone, address, name, date-of-birth, government-id, payment, IP, and secret labels;
- negative fields that should remain unclassified;
- adversarial metadata such as `email_verified` and `email_domain`;
- context that the built-in heuristics intentionally do not yet understand, such as sensitive values embedded in free text.

All values are synthetic. Example domains and documentation IP ranges are used where possible.

Run the benchmark:

```bash
trustforge datalease benchmark \
  --dataset evals/datalease/classifier-benchmark.jsonl
```

Machine-readable output:

```bash
trustforge datalease benchmark \
  --dataset evals/datalease/classifier-benchmark.jsonl \
  --json
```

Use thresholds in CI:

```bash
trustforge datalease benchmark \
  --dataset evals/datalease/classifier-benchmark.jsonl \
  --min-precision 0.90 \
  --min-recall 0.85
```

The current built-in baseline is intentionally non-perfect. The dataset includes known false positives and false negatives so the benchmark documents limitations instead of hiding them.

This small synthetic set is a regression suite, not evidence of production-grade PII detection and not a compliance benchmark. Larger multilingual and domain-specific datasets are future work.
