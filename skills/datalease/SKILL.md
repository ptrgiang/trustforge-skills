---
name: datalease
description: Enforce purpose- and destination-bound minimum-necessary data sharing before an AI agent sends a payload to a tool, MCP server, API, or connector.
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
destination binding
    ↓
field classification
    ↓
allow / redact / deny
    ↓
minimum-necessary payload
    ↓
HTTP / MCP / connector
```

DataLease v0.4 is a local projection and interception layer. It does not make the external destination trustworthy and does not claim that redaction makes data anonymous.

## Core guarantees

1. **Purpose binding** — unauthorized purposes deny the whole transfer.
2. **Destination binding** — HTTP scheme/host/method and MCP tool names must match policy bindings.
3. **Default deny** — recommended policies share only explicitly justified fields.
4. **Field-level decisions** — nested fields can be allowed, redacted, or denied.
5. **Classifier hooks** — policies can match built-in or caller-supplied classifier labels.
6. **Hard denies** — selected labels, `secret` by default, run before normal allow rules.
7. **Value-free audit** — audit records paths, decisions, classifier provenance, and reasons without copying original leaf values.
8. **Block before dispatch** — unauthorized or empty projected transfers do not invoke the wrapped transport/caller by default.
9. **Fail-closed classifier plugins** — classifier exceptions become `DataLeaseError` instead of silently allowing a transfer.

These are policy-engine guarantees, not claims about downstream storage, retention, model training, or recipient behavior.

## Policy model

```yaml
version: "0.1"
purpose: send order summary to support tool
default_action: deny
hard_deny_classifiers:
  - secret

destinations:
  http:
    schemes: [https]
    hosts: [support.example.com]
    methods: [POST]
  mcp:
    tools: [support.create_ticket]

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
    paths: [customer.email]
    classifiers: [pii.email]
    action: redact
    strategy: email_domain
    reason: Only domain context is necessary.
```

Rules are evaluated top-to-bottom. When a rule contains both `paths` and `classifiers`, both selectors must match. `hard_deny_classifiers` are checked before normal rules.

Wildcard field paths use shell-style matching. `items.*.sku` matches `items.0.sku`, `items.1.sku`, and so on. HTTP host and MCP tool bindings also accept shell-style wildcard patterns.

## Built-in classifiers

The built-in heuristic detector currently emits:

- `secret`
- `pii.email`
- `pii.phone`
- `pii.address`
- `pii.name`
- `pii.dob`
- `pii.government_id`
- `pii.payment`
- `network.ip`

The heuristics are deliberately conservative and imperfect. Do not treat them as a compliance classifier.

## Pluggable classifiers

Trusted application code can add organization- or domain-specific classification without modifying the serialized policy format.

```python
from trustforge.datalease_classifiers import ClassificationFinding

class EmployeeIdClassifier:
    name = "employee-id-v1"

    def classify(self, path, value):
        if path.endswith("employee_id"):
            return [ClassificationFinding(
                label="sensitivity.internal_id",
                detector=self.name,
                confidence=0.98,
                reason="Organization-specific employee identifier.",
            )]
        return []
```

Then pass the classifier explicitly:

```python
report = apply_policy(
    policy,
    purpose,
    payload,
    classifiers=[EmployeeIdClassifier()],
)
```

Adapters accept the same `classifiers=[...]` parameter.

Classifier outputs may be strings or `ClassificationFinding` objects. Audit evidence records `label`, `detector`, `confidence`, and optional `reason`. Raw field values are never inserted into classifier evidence.

DataLease intentionally does **not** expose a CLI option that dynamically imports arbitrary classifier strings. Plugins must come from trusted application code.

## Actions

- `allow` keeps the original value.
- `deny` removes the field from the outgoing payload.
- `redact` replaces the value using `mask`, `null`, `last4`, or `email_domain`.

Redaction reduces disclosure; it is not proof of anonymization.

## CLI projection

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

## Classifier benchmark

Run the synthetic regression suite:

```bash
trustforge datalease benchmark \
  --dataset evals/datalease/classifier-benchmark.jsonl
```

Use measurable CI gates:

```bash
trustforge datalease benchmark \
  --dataset evals/datalease/classifier-benchmark.jsonl \
  --min-precision 0.90 \
  --min-recall 0.85
```

Current built-in baseline on the 30-case synthetic fixture is approximately:

```text
precision = 0.913
recall    = 0.875
F1        = 0.894
exact     = 25 / 30
```

Known mismatches remain in the fixture intentionally, including `email_verified`, `email_domain`, free-text sensitive values, and an unsupported name variant. The fixture is a deterministic regression suite, not a production/compliance benchmark.

Benchmark threshold failure exits with code `5`.

## HTTP interception

```python
from trustforge.datalease_adapters import HTTPDataLeaseAdapter

adapter = HTTPDataLeaseAdapter.from_policy_file(
    "policy.yaml",
    transport,
    classifiers=custom_classifiers,
)
result = adapter.send_json(
    "POST",
    "https://support.example.com/tickets",
    purpose="send order summary to support tool",
    json_body=payload,
)
```

`AsyncHTTPDataLeaseAdapter` provides the same contract for async transports.

The reference HTTP adapter governs the application JSON body. Transport-owned headers are passed through unchanged; do not place user data in ungoverned headers.

## MCP interception

```python
from trustforge.datalease_adapters import MCPDataLeaseAdapter

adapter = MCPDataLeaseAdapter.from_policy_file(
    "policy.yaml",
    call_tool,
    classifiers=custom_classifiers,
)
result = adapter.call_tool(
    "support.create_ticket",
    purpose="send order summary to support tool",
    arguments=payload,
)
```

`AsyncMCPDataLeaseAdapter` provides the same contract for async dispatchers.

## Refusal behavior

`DataLeaseBlocked` is raised before the wrapped transport/caller executes when:

- the HTTP scheme, host, or method is not authorized;
- the MCP tool is not authorized;
- the declared purpose is not authorized;
- the projected payload contains no authorized fields and `block_empty=True` (default).

The exception carries the value-free DataLease report for audit/debugging; it does not contain the original payload.

## Audit format

Each leaf decision records:

- path;
- action;
- classifier labels;
- classifier evidence (`detector`, `confidence`, optional reason);
- matched rule id;
- decision reason;
- redaction strategy when applicable.

Original leaf values are intentionally omitted.

## Failure modes

The built-in classifier can miss sensitive values with uncommon names or formats, secrets/PII embedded inside large free-text fields, context-dependent sensitivity, binaries/attachments, and sensitive relationships visible only across multiple fields.

The HTTP reference adapter currently does not project transport headers, multipart bodies, streaming bodies, or URL/query parameters. The MCP adapter governs the arguments object passed through it, but cannot govern data a tool obtains independently after invocation.

Custom classifier code is trusted runtime code. DataLease can fail closed when a plugin raises, but it cannot sandbox a malicious classifier implementation.

## Next work

- larger multilingual/domain-specific benchmark datasets;
- classifier label namespace and version governance;
- concrete integrations for selected popular MCP/HTTP client stacks;
- release `v0.4.0` after the API surface stabilizes.
