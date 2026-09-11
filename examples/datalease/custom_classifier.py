from __future__ import annotations

from trustforge.datalease import apply_policy
from trustforge.datalease_classifiers import ClassificationFinding


class EmployeeIdClassifier:
    """Example organization-specific classifier supplied by trusted application code."""

    name = "employee-id-v1"

    def classify(self, path, value):
        if path.endswith("employee_id") and isinstance(value, str):
            return [
                ClassificationFinding(
                    label="sensitivity.internal_id",
                    detector=self.name,
                    confidence=0.98,
                    reason="Organization-specific employee identifier.",
                )
            ]
        return []


policy = {
    "version": "0.1",
    "purpose": "send support summary",
    "default_action": "allow",
    "hard_deny_classifiers": ["secret", "sensitivity.internal_id"],
    "rules": [],
}

payload = {
    "employee_id": "EMP-123",
    "status": "active",
}

report = apply_policy(
    policy,
    "send support summary",
    payload,
    classifiers=[EmployeeIdClassifier()],
)

assert report["output"] == {"status": "active"}
print(report["output"])
