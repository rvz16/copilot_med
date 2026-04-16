from __future__ import annotations

import re

from app.models import CanonicalExtraction


class ClinicalExtractionSanitizer:
    _speaker_label_pattern = re.compile(
        r"^\s*(patient|doctor|clinician|provider|nurse|пациент|врач|доктор|клиницист|медсестра)\s*:\s*",
        flags=re.IGNORECASE,
    )
    _imperative_prompt_prefixes = (
        "опишите",
        "расскажите",
        "скажите",
        "уточните",
        "подскажите",
        "покажите",
        "давайте",
        "please describe",
        "describe",
        "tell me",
        "can you",
        "could you",
        "please",
        "let's",
    )
    _acknowledgement_prefixes = (
        "понимаю",
        "понятно",
        "ясно",
        "хорошо",
        "ладно",
        "i understand",
        "understood",
        "okay",
        "ok",
        "alright",
    )
    _question_prefixes = (
        "это ",
        "есть ли ",
        "как ",
        "когда ",
        "почему ",
        "какой ",
        "какая ",
        "какие ",
        "is it ",
        "are you ",
        "do you ",
        "does it ",
        "did it ",
        "how ",
        "what ",
        "when ",
        "where ",
    )
    _short_fillers = {"да", "нет", "угу", "ага", "ok", "okay", "понятно", "ясно"}
    _clinician_speakers = {"doctor", "clinician", "provider", "nurse", "врач", "доктор", "клиницист", "медсестра"}
    _diagnosis_noise_prefixes = (
        "понимаю",
        "давайте",
        "опишите",
        "расскажите",
        "скажите",
        "это ",
        "скорее",
        "и началась",
        "прямая",
        "примая",
    )

    def sanitize(self, extraction: CanonicalExtraction) -> CanonicalExtraction:
        return CanonicalExtraction(
            symptoms=self._sanitize_items("symptoms", extraction.symptoms),
            concerns=self._sanitize_items("concerns", extraction.concerns),
            observations=self._sanitize_items("observations", extraction.observations),
            measurements=self._sanitize_items("measurements", extraction.measurements),
            diagnoses=self._sanitize_items("diagnoses", extraction.diagnoses),
            evaluation=self._sanitize_items("evaluation", extraction.evaluation),
            treatment=self._sanitize_items("treatment", extraction.treatment),
            follow_up_instructions=self._sanitize_items(
                "follow_up_instructions",
                extraction.follow_up_instructions,
            ),
            medications=self._sanitize_items("medications", extraction.medications),
            allergies=self._sanitize_items("allergies", extraction.allergies),
        )

    def _sanitize_items(self, field_name: str, items: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()

        for item in items:
            speaker, text = self._split_speaker_label(item)
            normalized = self._normalize(text)
            if self._should_drop(field_name, normalized, speaker):
                continue
            key = normalized
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(text)

        return cleaned

    def _should_drop(self, field_name: str, normalized: str, speaker: str | None) -> bool:
        if not normalized or normalized in self._short_fillers:
            return True
        if "?" in normalized:
            return True
        if any(normalized.startswith(prefix) for prefix in self._imperative_prompt_prefixes):
            return True
        if field_name in {"symptoms", "concerns"} and any(
            normalized.startswith(prefix) for prefix in self._acknowledgement_prefixes
        ):
            return True
        if field_name in {"symptoms", "concerns"} and any(
            normalized.startswith(prefix) for prefix in self._question_prefixes
        ):
            return True
        if speaker in self._clinician_speakers and field_name in {"symptoms", "concerns"}:
            return True
        if field_name == "diagnoses" and any(
            normalized.startswith(prefix) for prefix in self._diagnosis_noise_prefixes
        ):
            return True
        if field_name == "diagnoses" and len(normalized.split()) > 12:
            return True
        return False

    def _split_speaker_label(self, text: str) -> tuple[str | None, str]:
        match = self._speaker_label_pattern.match(text)
        if not match:
            return None, self._clean_text(text)
        speaker = self._normalize(match.group(1))
        return speaker, self._clean_text(text[match.end() :])

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip(" \t\r\n-:")

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.lower().replace("ё", "е")).strip()
