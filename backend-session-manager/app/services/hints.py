from dataclasses import dataclass
import hashlib


@dataclass(frozen=True)
class HintRule:
    keywords: tuple[str, ...]
    hint_type: str
    message: str
    confidence: float
    severity: str
    source: str = "rule_based"


class HintService:
    """Deterministic rule-based hint generation."""

    RULES = (
        HintRule(
            keywords=("headache",),
            hint_type="followup_hint",
            message="Ask about pain severity and duration.",
            confidence=0.84,
            severity="medium",
        ),
        HintRule(
            keywords=("blood pressure", "hypertension"),
            hint_type="followup_hint",
            message="Consider hypertension history and recent blood pressure readings.",
            confidence=0.76,
            severity="medium",
        ),
        HintRule(
            keywords=("allergic", "allergy"),
            hint_type="followup_hint",
            message="Confirm allergy history and prior reactions.",
            confidence=0.8,
            severity="high",
        ),
    )

    def generate(
        self,
        *,
        session_id: str,
        stable_text: str,
        existing_pairs: set[tuple[str, str]],
    ) -> list[dict]:
        lower_text = stable_text.lower()
        generated: list[dict] = []
        for rule in self.RULES:
            if not any(keyword in lower_text for keyword in rule.keywords):
                continue
            pair = (rule.hint_type, rule.message)
            if pair in existing_pairs:
                continue
            digest = hashlib.sha1(f"{session_id}:{rule.hint_type}:{rule.message}".encode("utf-8")).hexdigest()[:10]
            generated.append(
                {
                    "hint_id": f"hint_{digest}",
                    "type": rule.hint_type,
                    "message": rule.message,
                    "confidence": rule.confidence,
                    "severity": rule.severity,
                    "source": rule.source,
                }
            )
            existing_pairs.add(pair)
        return generated
