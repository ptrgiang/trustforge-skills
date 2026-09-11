---
name: datalease
description: Enforce purpose-bound, minimum-necessary data sharing before an AI agent sends a payload to a tool, MCP server, API, or connector.
license: Apache-2.0
metadata:
  trustforge:
    maturity: experimental
    category: privacy
    destructive: false
---

# DataLease

Use DataLease immediately before an agent transfers structured data to an external tool, API, MCP server, connector, plugin, or other trust boundary.

## Goal

Convert "the agent probably only sends what it needs" into an inspectable policy decision:

```text
agent payload
    ↓
declared purpose
    ↓
DataLease policy
    ↓
field classification
    ↓
allow / redact / deny
    ↓
minimum-necessary payload + audit trail
```

DataLease v0.4 is a local projection engine. It does not make the external destination trustworthy and does not claim that redaction makes data anonymous.

## Core guarantees

1. **Purpose binding** — a transfer is denied when the requested purpose is not authorized by the policy.
2. **Default deny** — recommended policies share only fields explicitly justified for the task.
3. **Field-level decisions** — rules can allow, redact, or deny nested fields.
4. **Classifier hooks** — rules can match basic PII/secret classifiers.
5. **Hard denies** — selected classifiers, `secret` by default, are evaluated before ordinary allow rules.
6. **Audit without raw values** — decision logs include paths and reasons, not the original field values.

These are policy-engine guarantees, not claims about downstream storage, retention, model training, or recipient behavior.

## Policy model

```yaml
version: "0.1"
purpose: send order summary to support tool
default_action: deny
hard_deny_classifiers:
  - secret

rules:
  - id: order-summary
    paths:
      - order.id
      - order.status
      - items.*.sku
      - items.*.quantity
    action: allow
    reason: Required to explain the order state.

  - id: customer-email
    paths:
      - customer.email
    classifiers:
      - pii.email
    action: redact
    strategy: email_domain
    reason: Only domain context is necessary.
```

Rules are evaluated top-to-bottom. When a rule contains both `paths` and `classifiers`, both selectors must match. `hard_deny_classifiers` are checked before normal rules.

Wildcard field paths use shell-style matching. `items.*.sku` matches `items.0.sku`, `items.1.sku`, and so on.

## Built-in classifiers

The first MVP includes conservative hooks for `secret`, `pii.email`, `pii.phone`, `pii.address`, `pii.name`, `pii.dob`, `pii.government_id`, `pii.payment`, and `network.ip`.

Classifiers are heuristics. They may miss sensitive data or classify benign fields as sensitive. Policies should combine classifiers with explicit field paths for important workflows.

## Actions

- `allow` keeps the original value.
- `deny` removes the field from the outgoing payload.
- `redact` replaces the value using `mask`, `null`, `last4`, or `email_domain`.

Redaction reduces disclosure; it is not a proof of anonymization.

## CLI

Generate a projected payload plus audit report:

```bash
trustforge datalease apply \
  --policy examples/datalease/support-policy.yaml \
  --purpose "send order summary to support tool" \
  --input examples/datalease/order-payload.json
```

Pipe only the minimum-necessary payload:

```bash
trustforge datalease apply \
  --policy examples/datalease/support-policy.yaml \
  --purpose "send order summary to support tool" \
  --input examples/datalease/order-payload.json \
  --payload-only
```

Write the audit separately with `--audit-output .artifacts/datalease-audit.json`.

Exit codes:

- `0`: purpose authorized and projection completed;
- `4`: purpose denied, invalid policy, invalid input, or file error.

## Audit format

Each leaf decision records path, action, classifiers, rule id, reason, and redaction strategy when applicable. The audit intentionally omits the original field value.

## Refusal / deny behavior

DataLease does not silently reinterpret an unauthorized purpose. If the purpose does not match the policy, the entire transfer receives `decision: denied` and `output: null`.

## Failure modes

The MVP can miss sensitive values with uncommon names or formats, secrets embedded inside large free-text fields, context-dependent sensitivity, binaries/attachments, sensitive relationships visible only across multiple fields, and downstream use that violates the declared purpose.

Do not use the built-in classifiers as a compliance certification.

## Integration direction

```text
Agent
  ↓
DataLease.apply_policy(...)
  ↓
projected payload
  ↓
MCP / HTTP / connector
```

The next DataLease milestone is a reference MCP/HTTP interception adapter plus richer pluggable classifiers and policy evaluation metrics.
