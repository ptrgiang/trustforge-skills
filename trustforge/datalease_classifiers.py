from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Protocol, runtime_checkable


@dataclass(frozen=True)
class ClassificationFinding:
    """One classifier assertion without carrying the original field value."""

    label: str
    detector: str
    confidence: float = 1.0
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("ClassificationFinding.label must be non-empty.")
        if not self.detector.strip():
            raise ValueError("ClassificationFinding.detector must be non-empty.")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("ClassificationFinding.confidence must be between 0 and 1.")

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "label": self.label,
            "detector": self.detector,
            "confidence": round(float(self.confidence), 6),
        }
        if self.reason:
            result["reason"] = self.reason
        return result


@runtime_checkable
class FieldClassifier(Protocol):
    """Minimal interface for a DataLease field classifier."""

    name: str

    def classify(
        self,
        path: str,
        value: Any,
    ) -> Iterable[str | ClassificationFinding]:
        ...


class CallableClassifier:
    """Small adapter for integrating a trusted Python callable as a classifier."""

    def __init__(
        self,
        name: str,
        func: Callable[[str, Any], Iterable[str | ClassificationFinding]],
        *,
        confidence: float = 1.0,
    ) -> None:
        if not name.strip():
            raise ValueError("Classifier name must be non-empty.")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Classifier confidence must be between 0 and 1.")
        self.name = name
        self.func = func
        self.confidence = confidence

    def classify(self, path: str, value: Any) -> Iterable[str | ClassificationFinding]:
        return self.func(path, value)


def normalize_findings(
    classifier: FieldClassifier,
    path: str,
    value: Any,
) -> list[ClassificationFinding]:
    """Normalize one trusted classifier's output and attach provenance."""

    detector = str(getattr(classifier, "name", classifier.__class__.__name__)).strip()
    if not detector:
        detector = classifier.__class__.__name__

    raw = classifier.classify(path, value)
    if raw is None:
        return []
    if isinstance(raw, (str, ClassificationFinding)):
        raw = [raw]

    findings: list[ClassificationFinding] = []
    for item in raw:
        if isinstance(item, ClassificationFinding):
            findings.append(item)
        elif isinstance(item, str):
            findings.append(
                ClassificationFinding(
                    label=item,
                    detector=detector,
                    confidence=float(getattr(classifier, "confidence", 1.0)),
                )
            )
        else:
            raise TypeError(
                f"Classifier {detector!r} returned unsupported finding type: "
                f"{type(item).__name__}"
            )
    return findings
