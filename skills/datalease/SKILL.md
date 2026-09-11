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
DataLease policy
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

1. **Purpose binding** — a transfer is denied when the requested purpose is not authorized by the policy.
2. **Destination binding** — interception adapters refuse HTTP hosts/methods/schemes or MCP tools outside the policy binding.
3. **Default deny** — recommended policies share only fields explicitly justified for the task.
4. **Field-level decisions** — rules can allow, redact, or deny nested fields.
5. **Classifier hooks** — rules can match basic PII/secret classifiers.
6. **Hard denies** — selected classifiers, `secret` by default, are evaluated before ordinary allow rules.
7. **Audit without raw values** — decision logs include paths and reasons, not the original field values.
8. **Block before dispatch** — unauthorized or empty projected transfers do not invoke the wrapped transport/caller by default.

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
    paths:
      - customer.email
    classifiers:
      - pii.email
    action: redact
    strategy: email_domain
    reason: Only domain context is necessary.
```

Rules are evaluated top-to-bottom. When a rule contains both `paths` and `classifiers`, both selectors must match. `hard_deny_classifiers` are checked before normal rules.

Wildcard field paths use shell-style matching. `items.*.sku` matches `items.0.sku`, `items.1.sku`, and so on. HTTP host and MCP tool bindings also accept shell-style wildcard patterns.

## Built-in classifiers

The first MVP includes conservative hooks for `secret`, `pii.email`, `pii.phone`, `pii.address`, `pii.name`, `pii.dob`, `pii.government_id`, `pii.payment`, and `network.ip`.

Classifiers are heuristics. They may miss sensitive data or classify benign fields as sensitive. Policies should combine classifiers with explicit field paths for important workflows.

## Actions

- `allow` keeps the original value.
- `deny` removes the field from the outgoing payload.
- `redact` replaces the value using `mask`, `null`, `last4`, or `email_domain`.

Redaction reduces disclosure; it is not a proof of anonymization.

## CLI projection

```bash
trustforge datalease apply \
  --policy examples/datalease/support-policy.yaml \
  --purpose "send order summary to support tool" \
  --input examples/datalease/order-payload.json \
  --payload-only
```

Write the audit separately with `--audit-output .artifacts/datalease-audit.json`.

CLI exit codes:

- `0`: purpose authorized and projection completed;
- `4`: purpose denied, invalid policy, invalid input, or file error.

## HTTP interception

The reference HTTP adapter wraps a caller-provided transport. It checks destination binding, projects the JSON body, and only then invokes the transport:

```python
from trustforge.datalease_adapters import HTTPDataLeaseAdapter

adapter = HTTPDataLeaseAdapter.from_policy_file("policy.yaml", transport)
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

The MCP adapter wraps a tool dispatcher and applies DataLease before the tool receives arguments:

```python
from trustforge.datalease_adapters import MCPDataLeaseAdapter

adapter = MCPDataLeaseAdapter.from_policy_file("policy.yaml", call_tool)
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

Each leaf decision records path, action, classifiers, rule id, reason, and redaction strategy when applicable. The audit intentionally omits the original field value.

## Failure modes

The MVP can miss sensitive values with uncommon names or formats, secrets embedded inside large free-text fields, context-dependent sensitivity, binaries/attachments, sensitive relationships visible only across multiple fields, and downstream use that violates the declared purpose.

The HTTP reference adapter currently does not project transport headers, multipart bodies, streaming bodies, or URL/query parameters. The MCP adapter governs the arguments object passed through it, but cannot govern data a tool obtains independently after invocation.

Do not use the built-in classifiers as a compliance certification.

## Next work

- pluggable classifier interface;
- policy precision/recall benchmark fixtures;
- concrete integrations for popular MCP/HTTP client stacks after the transport-neutral contract stabilizes.
