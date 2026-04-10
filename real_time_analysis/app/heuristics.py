from __future__ import annotations

import re
from typing import Any


SUGGESTION_TYPES = {
    "diagnosis_suggestion",
    "question_to_ask",
    "next_step",
    "warning",
}
SEVERITY_TYPES = {"low", "medium", "high"}
QUANTIZATION_TYPES = {"4bit", "8bit", "none"}


def clamp_confidence(value: Any, default: float = 0.5) -> float:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, val))


def normalize_text_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, str):
            continue
        text = " ".join(item.split())
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def extract_evidence_quotes(text: str, max_quotes: int = 2, max_words: int = 18) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    quotes: list[str] = []
    for chunk in chunks:
        clean = " ".join(chunk.split())
        if not clean:
            continue
        words = clean.split()
        if len(words) > max_words:
            clean = " ".join(words[:max_words]) + "..."
        quotes.append(clean)
        if len(quotes) >= max_quotes:
            break
    if quotes:
        return quotes
    fallback = " ".join(text.split())
    if not fallback:
        return []
    words = fallback.split()
    if len(words) > max_words:
        fallback = " ".join(words[:max_words]) + "..."
    return [fallback]


def _extract_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _extract_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    raw = match.group(1).replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def extract_facts(transcript_chunk: str) -> dict[str, Any]:
    text = transcript_chunk
    lowered = transcript_chunk.casefold()

    symptom_map = {
        "fever",
        "кашель",
        "cough",
        "headache",
        "головная боль",
        "fatigue",
        "усталость",
        "nausea",
        "тошнота",
        "chest pain",
        "боль в груди",
        "shortness of breath",
        "одышка",
        "dizziness",
        "головокружение",
    }
    condition_map = {
        "hypertension",
        "гипертония",
        "diabetes",
        "диабет",
        "asthma",
        "астма",
        "depression",
        "депрессия",
        "anxiety",
        "тревога",
    }
    medication_map = {
        "warfarin",
        "ibuprofen",
        "naproxen",
        "aspirin",
        "lisinopril",
        "spironolactone",
        "sertraline",
        "tramadol",
        "metformin",
        "insulin",
        "amoxicillin",
        "nitroglycerin",
        "sildenafil",
        "парацетамол",
        "ибупрофен",
    }

    symptoms = sorted([item for item in symptom_map if item in lowered], key=str.casefold)
    conditions = sorted([item for item in condition_map if item in lowered], key=str.casefold)
    medications = sorted([item for item in medication_map if item in lowered], key=str.casefold)

    allergies = []
    allergy_patterns = [
        r"allerg(?:y|ic)\s*(?:to)?\s*([a-zа-я0-9\-\s]{2,40})",
        r"аллерг(?:ия|и[чч]еск\w*)\s*(?:на)?\s*([a-zа-я0-9\-\s]{2,40})",
    ]
    for pattern in allergy_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            target = " ".join(match.group(1).split(" ")[:5]).strip(" ,.;:")
            if target:
                allergies.append(target)
    allergies = normalize_text_list(allergies)

    vitals: dict[str, Any] = {
        "age": _extract_int(r"\b(\d{1,3})\s*(?:years?\s*old|y\/o|yo|лет)\b", text),
        "weight_kg": _extract_float(r"\b(\d{2,3}(?:[.,]\d{1,2})?)\s*(?:kg|кг)\b", text),
        "height_cm": _extract_float(r"\b(\d{2,3}(?:[.,]\d{1,2})?)\s*(?:cm|см)\b", text),
        "bp": None,
        "hr": _extract_int(
            r"(?:\bhr\b|\bpulse\b|\bheart rate\b|\bпульс\b)\s*[:=]?\s*(\d{2,3})",
            text,
        ),
        "temp_c": _extract_float(
            r"(?:\btemp(?:erature)?\b|\bтемпература\b)\s*[:=]?\s*(\d{2}(?:[.,]\d)?)",
            text,
        ),
    }
    bp_match = re.search(r"\b(\d{2,3}\/\d{2,3})\b", text)
    if bp_match:
        vitals["bp"] = bp_match.group(1)

    return {
        "symptoms": symptoms,
        "conditions": conditions,
        "medications": medications,
        "allergies": allergies,
        "vitals": vitals,
    }


DRUG_INTERACTION_RULES = [
    {
        "drugs": ("warfarin", "ibuprofen"),
        "severity": "high",
        "rationale": "Higher bleeding risk when anticoagulants are combined with NSAIDs.",
        "confidence": 0.91,
    },
    {
        "drugs": ("warfarin", "naproxen"),
        "severity": "high",
        "rationale": "Naproxen can increase bleeding risk in patients on warfarin.",
        "confidence": 0.9,
    },
    {
        "drugs": ("lisinopril", "spironolactone"),
        "severity": "medium",
        "rationale": "Combined RAAS effects can raise potassium and affect kidney function.",
        "confidence": 0.82,
    },
    {
        "drugs": ("sertraline", "tramadol"),
        "severity": "high",
        "rationale": "Serotonergic toxicity risk increases with this combination.",
        "confidence": 0.88,
    },
    {
        "drugs": ("nitroglycerin", "sildenafil"),
        "severity": "high",
        "rationale": "Marked hypotension risk due to additive vasodilation.",
        "confidence": 0.93,
    },
]


def detect_drug_interactions(transcript_chunk: str) -> list[dict[str, Any]]:
    lowered = transcript_chunk.casefold()
    interactions: list[dict[str, Any]] = []
    for rule in DRUG_INTERACTION_RULES:
        drug_a, drug_b = rule["drugs"]
        if drug_a in lowered and drug_b in lowered:
            interactions.append(
                {
                    "drug_a": drug_a,
                    "drug_b": drug_b,
                    "severity": rule["severity"],
                    "rationale": rule["rationale"],
                    "confidence": rule["confidence"],
                }
            )
    return interactions


KB_RULES = [
    {
        "keywords": {"chest pain", "боль в груди"},
        "title": "Chest Pain Evaluation Pathway",
        "snippet": "Risk-stratified approach for acute chest pain and triage decisions.",
        "confidence": 0.8,
    },
    {
        "keywords": {"fever", "кашель", "cough"},
        "title": "Respiratory Infection Differential",
        "snippet": "Checklist for common infectious causes and red-flag symptoms.",
        "confidence": 0.74,
    },
    {
        "keywords": {"hypertension", "гипертония"},
        "title": "Hypertension Follow-up Guidance",
        "snippet": "Targets, medication review points, and home BP monitoring tips.",
        "confidence": 0.76,
    },
    {
        "keywords": {"diabetes", "диабет", "metformin", "insulin"},
        "title": "Diabetes Medication Safety",
        "snippet": "Overview of glycemic targets and medication-related warning signs.",
        "confidence": 0.78,
    },
]


def build_knowledge_refs(transcript_chunk: str, facts: dict[str, Any]) -> list[dict[str, Any]]:
    lowered = transcript_chunk.casefold()
    refs: list[dict[str, Any]] = []
    for rule in KB_RULES:
        if any(keyword in lowered for keyword in rule["keywords"]):
            refs.append(
                {
                    "source": "heuristic_rules",
                    "title": rule["title"],
                    "snippet": rule["snippet"],
                    "url": None,
                    "confidence": rule["confidence"],
                }
            )

    if not refs and facts.get("symptoms"):
        refs.append(
            {
                "source": "heuristic_rules",
                "title": "General Symptom Triage Checklist",
                "snippet": "Structured triage prompts for symptom progression and red flags.",
                "url": None,
                "confidence": 0.6,
            }
        )
    return refs


def merge_extracted_facts(heuristic: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "symptoms": normalize_text_list(heuristic.get("symptoms", [])),
        "conditions": normalize_text_list(heuristic.get("conditions", [])),
        "medications": normalize_text_list(heuristic.get("medications", [])),
        "allergies": normalize_text_list(heuristic.get("allergies", [])),
        "vitals": {
            "age": None,
            "weight_kg": None,
            "height_cm": None,
            "bp": None,
            "hr": None,
            "temp_c": None,
        },
    }

    model = model if isinstance(model, dict) else {}
    for key in ("symptoms", "conditions", "medications", "allergies"):
        merged[key] = normalize_text_list(merged.get(key, []) + normalize_text_list(model.get(key, [])))

    model_vitals = model.get("vitals") if isinstance(model.get("vitals"), dict) else {}
    heuristic_vitals = heuristic.get("vitals") if isinstance(heuristic.get("vitals"), dict) else {}
    for field in merged["vitals"]:
        model_value = model_vitals.get(field)
        heuristic_value = heuristic_vitals.get(field)
        merged["vitals"][field] = model_value if model_value is not None else heuristic_value
    return merged
