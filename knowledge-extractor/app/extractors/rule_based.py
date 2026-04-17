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
        "бол",
        "головн",
        "температур",
        "каш",
        "тошнот",
        "рвот",
        "головокруж",
        "слабост",
        "устал",
        "сонлив",
        "одыш",
        "отдыш",
        "жажд",
        "сухост",
        "разбит",
        "тяжест",
    ]
    concern_keywords = [
        "concern",
        "worried",
        "anxious",
        "stress",
        "afraid",
        "беспок",
        "волн",
        "трев",
        "боюс",
        "страш",
        "опаса",
        "раздража",
    ]
    observation_keywords = [
        "exam",
        "observed",
        "noted",
        "appears",
        "physical",
        "осмотр",
        "объектив",
        "наблюда",
        "отмеча",
        "выгляд",
        "при осмотре",
    ]
    diagnosis_keywords = [
        "diagnosis",
        "diagnosed",
        "impression",
        "assessment",
        "likely",
        "diagnosed with",
        "диагноз",
        "диагност",
        "оценка",
        "впечатлен",
        "вероятно",
        "подозр",
        "считает, что",
        "похоже на",
    ]
    evaluation_keywords = [
        "stable",
        "improving",
        "worsening",
        "controlled",
        "uncontrolled",
        "стабил",
        "улучш",
        "ухудш",
        "контрол",
        "легче",
        "тяжел",
        "выражен",
        "скорее всего",
    ]
    treatment_keywords = [
        "start",
        "continue",
        "prescribe",
        "advised",
        "recommend",
        "plan",
        "назнач",
        "рекоменд",
        "совет",
        "начать",
        "продолж",
        "принимать",
        "пейте",
        "план",
    ]
    follow_up_keywords = [
        "follow up",
        "return in",
        "come back",
        "recheck",
        "next visit",
        "повторн",
        "контроль",
        "следующ",
        "вернут",
        "повторный визит",
        "повторный прием",
    ]
    medication_context = [
        "take",
        "taking",
        "medication",
        "prescribed",
        "prescribe",
        "continue",
        "назнач",
        "начать",
        "продолж",
        "принимать",
        "пейте",
    ]
    allergy_keywords = ["allergic to", "allergy to", "allergic", "аллерг", "непереносим"]
    negative_allergy_keywords = [
        "no known allergies",
        "nka",
        "allergies denied",
        "нет известных аллерг",
        "аллерги нет",
        "аллергию отрица",
        "не аллерг",
    ]

    measurement_pattern = re.compile(
        r"(?<!\w)("
        r"\d{2,3}/\d{2,3}\s?(?:mmhg|мм\.?\s?рт\.?\s?ст\.?)"
        r"|"
        r"\d+(?:[.,]\d+)?\s?(?:mg/dl|mmol/l|mmol/l|kg|lbs|bpm|°c|°f|cm|кг|см|ммоль/л|c)"
        r"|"
        r"(?:temp(?:erature)?|temperature|температура|t)\s?\d+(?:[.,]\d+)?(?:\s?(?:°c|°f|c))?"
        r"|"
        r"(?:spo2|oxygen saturation|сатурация|спо2)\s?\d+%"
        r"|"
        r"(?:pulse|heart rate|пульс|чсс)\s?\d+"
        r")(?!\w)",
        flags=re.IGNORECASE,
    )

    medication_phrase_pattern = re.compile(
        r"\b(?:start(?:ed)?|continue|take|taking|prescribed?)\s+([a-zA-Z0-9\-\s]+?)(?:\.|,|;|$)",
        flags=re.IGNORECASE,
    )
    medication_phrase_pattern_ru = re.compile(
        r"\b(?:назнач(?:ен[аоы]?|ить|или)?|начать|продолжить|принимать|пейте)\s+"
        r"([a-zA-Zа-яА-ЯёЁ0-9\-+/%.,\s]+?)(?:\.|,|;|$)",
        flags=re.IGNORECASE,
    )
    allergy_phrase_pattern = re.compile(
        r"\b(?:allergic to|allergy to)\s+([a-zA-Z0-9\-\s]+?)(?:\.|,|;|$)",
        flags=re.IGNORECASE,
    )
    allergy_phrase_pattern_ru = re.compile(
        r"\b(?:аллерг(?:ия|ии)?\s+на|аллерг(?:ен|ична)\s+к|непереносим(?:ость|а)\s+к)\s+"
        r"([a-zA-Zа-яА-ЯёЁ0-9\-\s]+?)(?:\.|,|;|$)",
        flags=re.IGNORECASE,
    )
    follow_up_pattern = re.compile(
        r"\b(?:follow up|return in|come back|recheck|next visit|через\s+"
        r"(?:\d+|од\w+|дв\w+|три|четыр\w+|пят\w+)\s+"
        r"(?:дн\w+|недел\w+|месяц\w+)|повторн\w+\s+(?:визит|прием)|контроль\w+\s+через)\b",
        flags=re.IGNORECASE,
    )

    def extract(self, transcript: str, language: str = "ru") -> CanonicalExtraction:
        del language
        sentences = self._split_sentences(transcript)
        extraction = CanonicalExtraction()

        for sentence in sentences:
            sentence_l = self._normalize(sentence)

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
            if self._contains_any(sentence_l, self.follow_up_keywords) or self.follow_up_pattern.search(sentence_l):
                extraction.follow_up_instructions.append(sentence)

            if self._contains_any(sentence_l, self.medication_context):
                extraction.medications.extend(self._extract_medication_candidates(sentence))

            if not self._contains_any(sentence_l, self.negative_allergy_keywords) and self._contains_any(
                sentence_l, self.allergy_keywords
            ):
                allergies = self._extract_phrases(self.allergy_phrase_pattern, sentence)
                allergies.extend(self._extract_phrases(self.allergy_phrase_pattern_ru, sentence))
                extraction.allergies.extend(allergies if allergies else [sentence])

            extraction.measurements.extend(self._extract_measurements(sentence))

        self._deduplicate_lists(extraction)
        return extraction

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        parts = re.split(r"[\n\r]+|(?<=[.!?…])\s+|(?<=\.\.\.)\s*", text)
        return [part.strip() for part in parts if part and part.strip()]

    @staticmethod
    def _contains_any(text: str, keywords: list[str]) -> bool:
        return any(re.search(rf"\b{re.escape(keyword)}", text) for keyword in keywords)

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.lower().replace("ё", "е")).strip()

    @staticmethod
    def _extract_phrases(pattern: re.Pattern[str], sentence: str) -> list[str]:
        matches = [match.strip() for match in pattern.findall(sentence) if match.strip()]
        return matches

    def _extract_measurements(self, sentence: str) -> list[str]:
        return [
            match.replace(",", ".").strip()
            for match in self.measurement_pattern.findall(sentence)
            if match and match.strip()
        ]

    def _extract_medication_candidates(self, sentence: str) -> list[str]:
        candidates = self._extract_phrases(self.medication_phrase_pattern, sentence)
        candidates.extend(self._extract_phrases(self.medication_phrase_pattern_ru, sentence))
        candidates = [candidate for candidate in candidates if self._is_medication_candidate(candidate)]
        if candidates:
            return candidates
        return [sentence] if self._looks_like_medication_sentence(sentence) else []

    def _is_medication_candidate(self, candidate: str) -> bool:
        normalized = self._normalize(candidate)
        if any(
            re.search(rf"\b{re.escape(keyword)}", normalized)
            for keyword in ("water", "tea", "coffee", "вода", "воды", "водоем", "чай", "кофе", "бутыл")
        ):
            return False
        return bool(re.search(r"\d+\s?(?:mg|мг|ml|мл)\b", normalized)) or len(normalized.split()) <= 2

    def _looks_like_medication_sentence(self, sentence: str) -> bool:
        normalized = self._normalize(sentence)
        if any(
            re.search(rf"\b{re.escape(keyword)}", normalized)
            for keyword in ("water", "tea", "coffee", "вода", "воды", "водоем", "чай", "кофе", "бутыл")
        ):
            return False
        return bool(
            re.search(r"\d+\s?(?:mg|мг|ml|мл)\b", normalized)
            or self._contains_any(normalized, ["tablet", "capsule", "medication", "лекар", "препарат", "таблет"])
        )

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
