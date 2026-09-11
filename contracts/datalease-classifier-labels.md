# DataLease Classifier Label Contract

Status: v0.4.0

DataLease classifier labels are stable identifiers consumed by policies, audit records, benchmarks, and custom classifier implementations.

## Built-in namespace

Built-in labels use the `secret`, `pii.*`, and `network.*` namespaces.

| Label | Meaning |
| --- | --- |
| `secret` | Secret-like credential material or authentication bearer material. |
| `pii.email` | Email address. |
| `pii.phone` | Telephone or mobile number. |
| `pii.address` | Postal/location address components. |
| `pii.name` | Person name fields. |
| `pii.dob` | Date of birth. |
| `pii.government_id` | Government-issued or tax identifier. |
| `pii.payment` | Payment-card or bank-account material. |
| `network.ip` | IPv4 or IPv6 address. |

## Versioning rules

1. Existing built-in label strings are compatibility-sensitive and must not be silently renamed or repurposed within the `0.x` line.
2. A new detector may improve precision/recall while keeping the same label when the semantic category is unchanged.
3. A materially different semantic category requires a new label.
4. Removing or renaming a built-in label requires an explicit migration note and a release-level compatibility decision.
5. Policies should match labels, not detector implementation names.

## Custom namespaces

Third-party or organization-specific classifiers SHOULD use a namespaced label rather than extending `pii.*` or `network.*` without coordination.

Recommended forms:

```text
org.example.employee_id
vendor.product.category
sensitivity.internal_id
```

Custom classifier names identify detector provenance; labels identify policy semantics.

Example:

```python
ClassificationFinding(
    label="org.acme.employee_id",
    detector="acme-employee-id-v1",
    confidence=0.98,
)
```

A policy may then use:

```yaml
hard_deny_classifiers:
  - org.acme.employee_id
```

## Confidence

`confidence` is evidence metadata in the inclusive range `0.0` to `1.0`. DataLease v0.4 does not use confidence as an authorization override. Rules and hard-deny decisions match the classifier label regardless of confidence.

This avoids a low-confidence finding silently bypassing an explicit security policy. Applications that want confidence-aware behavior should express it in a trusted custom classifier that decides whether to emit the label.

## Audit compatibility

Classifier audit evidence is value-free and has this shape:

```json
{
  "label": "pii.email",
  "detector": "builtin-v1",
  "confidence": 0.95,
  "reason": "... optional ..."
}
```

Consumers SHOULD tolerate additional evidence keys in future versions, but SHOULD treat `label`, `detector`, and `confidence` as the stable v0.4 fields.
