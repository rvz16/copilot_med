from __future__ import annotations

import csv
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re

from app.core.errors import ApiError

_STOPWORDS = {
    "а",
    "без",
    "в",
    "во",
    "для",
    "и",
    "или",
    "к",
    "на",
    "не",
    "о",
    "об",
    "от",
    "по",
    "при",
    "с",
    "со",
    "у",
}

_RUSSIAN_ENDINGS = (
    "иями",
    "ями",
    "ами",
    "его",
    "ого",
    "ему",
    "ому",
    "ыми",
    "ими",
    "ией",
    "ией",
    "ией",
    "иям",
    "иях",
    "ью",
    "ия",
    "ья",
    "ие",
    "ье",
    "ий",
    "ый",
    "ой",
    "ая",
    "яя",
    "ое",
    "ее",
    "ые",
    "ие",
    "ам",
    "ям",
    "ах",
    "ях",
    "ов",
    "ев",
    "ом",
    "ем",
    "ую",
    "юю",
    "а",
    "я",
    "ы",
    "и",
    "о",
    "е",
    "у",
    "ю",
)

_TOKEN_SYNONYMS = {
    "рак": {"злокачествен", "новообразован", "опухол", "онколог"},
    "онколог": {"злокачествен", "новообразован", "опухол", "рак"},
    "опухол": {"злокачествен", "новообразован", "рак"},
}


@dataclass(frozen=True)
class ClinicalRecommendationEntry:
    id: str
    title: str
    icd10_codes: tuple[str, ...]
    age_category: str
    developer: str
    approval_status: str
    published_at: str
    application_status: str
    pdf_number: int
    pdf_filename: str
    pdf_available: bool
    pdf_path: Path | None
    normalized_title: str
    search_tokens: frozenset[str]


@dataclass(frozen=True)
class SearchResult:
    entry: ClinicalRecommendationEntry
    score: float


def _normalize_text(value: str) -> str:
    normalized = value.lower().replace("ё", "е")
    normalized = re.sub(r"[^0-9a-zа-я]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _stem_token(token: str) -> str:
    if len(token) <= 4:
        return token

    for ending in _RUSSIAN_ENDINGS:
        if token.endswith(ending) and len(token) - len(ending) >= 3:
            return token[: -len(ending)]
    return token


def _tokenize(text: str) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    tokens: list[str] = []
    for token in normalized.split():
        if token in _STOPWORDS:
            continue
        stemmed = _stem_token(token)
        if len(stemmed) >= 2:
            tokens.append(stemmed)
    return tokens


def _expand_query_tokens(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for token in list(tokens):
        expanded.update(_TOKEN_SYNONYMS.get(token, set()))
    return expanded


class ClinicalRecommendationsService:
    """Loads official recommendations from CSV and exposes lookup/search helpers."""

    def __init__(self, csv_path: Path, pdf_dir: Path) -> None:
        self._csv_path = csv_path
        self._pdf_dir = pdf_dir
        self._entries = self._load_entries(csv_path, pdf_dir)
        self._entries_by_id = {entry.id: entry for entry in self._entries}

    @property
    def total(self) -> int:
        return len(self._entries)

    def list_entries(
        self,
        *,
        limit: int,
        offset: int,
        has_pdf: bool | None = None,
    ) -> tuple[list[ClinicalRecommendationEntry], int]:
        entries = self._entries
        if has_pdf is not None:
            entries = [entry for entry in entries if entry.pdf_available is has_pdf]
        total = len(entries)
        return entries[offset : offset + limit], total

    def get_entry(self, recommendation_id: str) -> ClinicalRecommendationEntry:
        entry = self._entries_by_id.get(recommendation_id)
        if entry is None:
            raise ApiError(
                code="RECOMMENDATION_NOT_FOUND",
                message=f"Clinical recommendation '{recommendation_id}' was not found.",
                status_code=404,
            )
        return entry

    def search(self, *, query: str, limit: int) -> list[SearchResult]:
        normalized_query = _normalize_text(query)
        if not normalized_query:
            raise ApiError(
                code="INVALID_QUERY",
                message="Search query must be a non-empty string.",
                status_code=400,
            )

        query_tokens = set(_tokenize(normalized_query))
        if not query_tokens:
            query_tokens = {normalized_query}

        expanded_query_tokens = _expand_query_tokens(query_tokens)
        scored: list[SearchResult] = []
        for entry in self._entries:
            score = self._score_entry(
                normalized_query=normalized_query,
                query_tokens=query_tokens,
                expanded_query_tokens=expanded_query_tokens,
                entry=entry,
            )
            if score > 0:
                scored.append(SearchResult(entry=entry, score=round(score, 4)))

        scored.sort(
            key=lambda item: (
                -item.score,
                item.entry.title.lower(),
                item.entry.id,
            ),
        )
        return scored[:limit]

    def get_pdf_path(self, recommendation_id: str) -> Path:
        entry = self.get_entry(recommendation_id)
        if entry.pdf_path is None:
            raise ApiError(
                code="PDF_NOT_FOUND",
                message=f"PDF for clinical recommendation '{recommendation_id}' is not available.",
                status_code=404,
            )
        return entry.pdf_path

    def _score_entry(
        self,
        *,
        normalized_query: str,
        query_tokens: set[str],
        expanded_query_tokens: set[str],
        entry: ClinicalRecommendationEntry,
    ) -> float:
        direct_token_coverage = self._token_coverage(query_tokens, entry.search_tokens)
        if direct_token_coverage == 0:
            expanded_overlap = len(expanded_query_tokens & entry.search_tokens)
            if expanded_overlap == 0 and normalized_query not in entry.normalized_title:
                return 0.0
        else:
            expanded_overlap = len(expanded_query_tokens & entry.search_tokens)

        phrase_bonus = 0.8 if normalized_query in entry.normalized_title else 0.0
        all_terms_bonus = 0.6 if query_tokens and all(
            self._matches_token(term, entry.search_tokens) > 0 for term in query_tokens
        ) else 0.0
        expanded_ratio = expanded_overlap / max(len(expanded_query_tokens), 1)
        sequence_ratio = SequenceMatcher(None, normalized_query, entry.normalized_title).ratio()

        score = (
            3.0 * direct_token_coverage
            + 1.2 * expanded_ratio
            + 0.8 * sequence_ratio
            + phrase_bonus
            + all_terms_bonus
        )
        return score if score >= 0.75 else 0.0

    def _token_coverage(self, query_tokens: set[str], entry_tokens: frozenset[str]) -> float:
        if not query_tokens:
            return 0.0
        matched = sum(self._matches_token(token, entry_tokens) for token in query_tokens)
        return matched / len(query_tokens)

    def _matches_token(self, query_token: str, entry_tokens: frozenset[str]) -> float:
        if query_token in entry_tokens:
            return 1.0

        synonym_matches = _TOKEN_SYNONYMS.get(query_token, set()) & entry_tokens
        if synonym_matches:
            return 0.92

        if any(token.startswith(query_token) or query_token.startswith(token) for token in entry_tokens):
            return 0.65

        return 0.0

    @staticmethod
    def _load_entries(csv_path: Path, pdf_dir: Path) -> list[ClinicalRecommendationEntry]:
        if not csv_path.is_file():
            raise RuntimeError(f"Clinical recommendations CSV not found: {csv_path}")
        if not pdf_dir.is_dir():
            raise RuntimeError(f"Clinical recommendations PDF directory not found: {pdf_dir}")

        entries: list[ClinicalRecommendationEntry] = []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as file_obj:
            reader = csv.DictReader(file_obj, delimiter=";")
            for row in reader:
                recommendation_id = row["ID"].strip()
                pdf_number = ClinicalRecommendationsService._extract_pdf_number(recommendation_id)
                pdf_filename = f"КР{pdf_number}.pdf"
                pdf_path = pdf_dir / pdf_filename
                title = row["Наименование"].strip()
                entries.append(
                    ClinicalRecommendationEntry(
                        id=recommendation_id,
                        title=title,
                        icd10_codes=tuple(
                            code.strip() for code in row["МКБ-10"].split(",") if code.strip()
                        ),
                        age_category=row["Возрастная категория"].strip(),
                        developer=row["Разработчик"].strip(),
                        approval_status=row["Статус одобрения НПС"].strip(),
                        published_at=row["Дата размещения"].strip(),
                        application_status=row["Статус применения"].strip(),
                        pdf_number=pdf_number,
                        pdf_filename=pdf_filename,
                        pdf_available=pdf_path.is_file(),
                        pdf_path=pdf_path if pdf_path.is_file() else None,
                        normalized_title=_normalize_text(title),
                        search_tokens=frozenset(_tokenize(title)),
                    )
                )
        return entries

    @staticmethod
    def _extract_pdf_number(recommendation_id: str) -> int:
        number_str, _, _ = recommendation_id.partition("_")
        if not number_str.isdigit():
            raise RuntimeError(f"Unexpected clinical recommendation id format: {recommendation_id}")
        return int(number_str)
