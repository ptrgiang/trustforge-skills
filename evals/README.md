# TrustForge Evals

The eval suite will measure whether trust primitives catch meaningful failures without creating unusable false-positive rates.

## SkillDiff eval dimensions

- newly introduced network access;
- subprocess execution;
- environment/secret access;
- destructive filesystem behavior;
- dynamic execution;
- new outbound domains;
- benign refactors that should not increase risk.

Key metrics: capability-change recall, false-positive rate, evidence localization accuracy, and risk-threshold stability.

## CommitmentGuard eval dimensions

- all commitments satisfied;
- explicit failing evidence;
- missing evidence;
- nested evidence keys;
- explicit user waivers;
- unsupported operators;
- attempts to self-waive missing requirements.

Key metric: **false completion rate** — how often the system reports verified completion while a required commitment is failed or unknown.
