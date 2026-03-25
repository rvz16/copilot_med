from dataclasses import dataclass
import hashlib
from typing import Any


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

    def generate_from_realtime_analysis(
        self,
        *,
        session_id: str,
        analysis: dict[str, Any],
        existing_pairs: set[tuple[str, str]],
    ) -> list[dict]:
        generated: list[dict] = []

        for suggestion in analysis.get("suggestions", []):
            if not isinstance(suggestion, dict):
                continue
            text = suggestion.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            hint_type = suggestion.get("type")
            if not isinstance(hint_type, str) or not hint_type.strip():
                hint_type = "next_step"
            pair = (hint_type, text.strip())
            if pair in existing_pairs:
                continue
            generated.append(
                {
                    "hint_id": self._build_hint_id(session_id, hint_type, text),
                    "type": hint_type,
                    "message": text.strip(),
                    "confidence": suggestion.get("confidence"),
                    "severity": self._severity_for_suggestion(hint_type),
                    "source": "realtime_analysis",
                }
            )
            existing_pairs.add(pair)

        for interaction in analysis.get("drug_interactions", []):
            if not isinstance(interaction, dict):
                continue
            drug_a = interaction.get("drug_a")
            drug_b = interaction.get("drug_b")
            rationale = interaction.get("rationale")
            if not all(isinstance(value, str) and value.strip() for value in (drug_a, drug_b, rationale)):
                continue
            message = f"{drug_a.strip()} + {drug_b.strip()}: {rationale.strip()}"
            pair = ("drug_interaction", message)
            if pair in existing_pairs:
                continue
            generated.append(
                {
                    "hint_id": self._build_hint_id(session_id, "drug_interaction", message),
                    "type": "drug_interaction",
                    "message": message,
                    "confidence": interaction.get("confidence"),
                    "severity": interaction.get("severity") if isinstance(interaction.get("severity"), str) else "medium",
                    "source": "realtime_analysis",
                }
            )
            existing_pairs.add(pair)

        return generated

    @staticmethod
    def _severity_for_suggestion(hint_type: str) -> str:
        if hint_type == "warning":
            return "high"
        if hint_type == "diagnosis_suggestion":
            return "medium"
        if hint_type == "next_step":
            return "medium"
        return "low"

    @staticmethod
    def _build_hint_id(session_id: str, hint_type: str, message: str) -> str:
        digest = hashlib.sha1(f"{session_id}:{hint_type}:{message}".encode("utf-8")).hexdigest()[:10]
        return f"hint_{digest}"
