# DataLease evals

DataLease includes deterministic synthetic regression fixtures for classifier quality.

## Built-in benchmark

```bash
trustforge datalease benchmark \
  --dataset evals/datalease/classifier-benchmark.jsonl
```

The primary 30-case fixture intentionally retains known mismatches so CI measures regression instead of presenting a perfect score.

Release baseline for v0.4.0:

```text
precision >= 0.90
recall    >= 0.85
```

## Multilingual/domain smoke fixture

```bash
trustforge datalease benchmark \
  --dataset evals/datalease/classifier-benchmark-multilingual.jsonl \
  --min-precision 0.90 \
  --min-recall 0.90
```

This small fixture adds Vietnamese phone/email examples, IPv6, credential-style field names, payment/government-id paths, and benign values that resemble identifiers.

These datasets are synthetic regression fixtures. They are not representative population samples and MUST NOT be presented as privacy/compliance certification benchmarks.
