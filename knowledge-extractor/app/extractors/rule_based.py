from __future__ import annotations

import re

from app.extractors.base import BaseExtractor
from app.models.canonical import CanonicalExtraction


class RuleBasedMedicalExtractor(BaseExtractor):
    symptom_keywords = [
        "pain",
        "headache",
        "fever",
        "cough",
        "nausea",
        "vomiting",
        "dizziness",
        "fatigue",
        "shortness of breath",
    ]
    concern_keywords = ["concern", "worried", "anxious", "stress", "afraid"]
    observation_keywords = ["exam", "observed", "noted", "appears", "physical"]
    diagnosis_keywords = ["diagnosis", "diagnosed", "impression", "assessment", "likely"]
    evaluation_keywords = ["stable", "improving", "worsening", "controlled", "uncontrolled"]
    treatment_keywords = ["start", "continue", "prescribe", "advised", "recommend", "plan"]
    follow_up_keywords = ["follow up", "return in", "come back", "recheck", "next visit"]
    medication_context = ["take", "taking", "medication", "prescribed", "prescribe", "continue"]
    allergy_keywords = ["allergic to", "allergy to", "no known allergies", "nka"]

    measurement_pattern = re.compile(
        r"\b(\d{2,3}/\d{2,3}\s?mmhg|\d+(?:\.\d+)?\s?(?:mg/dl|mmol/l|kg|lbs|bpm|°c|°f|cm)|"
        r"temp(?:erature)?\s?\d+(?:\.\d+)?|spo2\s?\d+%|oxygen saturation\s?\d+%)\b",
        flags=re.IGNORECASE,
    )

    medication_phrase_pattern = re.compile(
        r"\b(?:start(?:ed)?|continue|take|taking|prescribed?)\s+([a-zA-Z0-9\-\s]+?)(?:\.|,|;|$)",
        flags=re.IGNORECASE,
    )
    allergy_phrase_pattern = re.compile(
        r"\b(?:allergic to|allergy to)\s+([a-zA-Z0-9\-\s]+?)(?:\.|,|;|$)",
        flags=re.IGNORECASE,
    )

    def extract(self, transcript: str) -> CanonicalExtraction:
        sentences = self._split_sentences(transcript)
        extraction = CanonicalExtraction()

        for sentence in sentences:
            sentence_l = sentence.lower()

            if self._contains_any(sentence_l, self.symptom_keywords):
                extraction.symptoms.append(sentence)
            if self._contains_any(sentence_l, self.concern_keywords):
                extraction.concerns.append(sentence)
            if self._contains_any(sentence_l, self.observation_keywords):
                extraction.observations.append(sentence)
            if self._contains_any(sentence_l, self.diagnosis_keywords):
                extraction.diagnoses.append(sentence)
            if self._contains_any(sentence_l, self.evaluation_keywords):
                extraction.evaluation.append(sentence)
            if self._contains_any(sentence_l, self.treatment_keywords):
                extraction.treatment.append(sentence)
            if self._contains_any(sentence_l, self.follow_up_keywords):
                extraction.follow_up_instructions.append(sentence)

            if self._contains_any(sentence_l, self.medication_context):
                meds = self._extract_phrases(self.medication_phrase_pattern, sentence)
                extraction.medications.extend(meds if meds else [sentence])

            if self._contains_any(sentence_l, self.allergy_keywords):
                allergies = self._extract_phrases(self.allergy_phrase_pattern, sentence)
                extraction.allergies.extend(allergies if allergies else [sentence])

            extraction.measurements.extend(self.measurement_pattern.findall(sentence))

        self._deduplicate_lists(extraction)
        return extraction

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        parts = re.split(r"[\n\r]+|(?<=[.!?])\s+", text)
        return [part.strip() for part in parts if part and part.strip()]

    @staticmethod
    def _contains_any(text: str, keywords: list[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _extract_phrases(pattern: re.Pattern[str], sentence: str) -> list[str]:
        matches = [match.strip() for match in pattern.findall(sentence) if match.strip()]
        return matches

    @staticmethod
    def _deduplicate(values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            key = value.strip().lower()
            if key and key not in seen:
                seen.add(key)
                ordered.append(value.strip())
        return ordered

    def _deduplicate_lists(self, extraction: CanonicalExtraction) -> None:
        extraction.symptoms = self._deduplicate(extraction.symptoms)
        extraction.concerns = self._deduplicate(extraction.concerns)
        extraction.observations = self._deduplicate(extraction.observations)
        extraction.measurements = self._deduplicate(extraction.measurements)
        extraction.diagnoses = self._deduplicate(extraction.diagnoses)
        extraction.evaluation = self._deduplicate(extraction.evaluation)
        extraction.treatment = self._deduplicate(extraction.treatment)
        extraction.follow_up_instructions = self._deduplicate(extraction.follow_up_instructions)
        extraction.medications = self._deduplicate(extraction.medications)
        extraction.allergies = self._deduplicate(extraction.allergies)
