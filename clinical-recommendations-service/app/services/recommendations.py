from __future__ import annotations

import csv
from dataclasses import dataclass
from difflib import SequenceMatcher
import logging
from pathlib import Path
import re

from app.core.errors import ApiError
from app.services.embeddings import ClinicalRecommendationEmbeddingIndex

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
    "боль",
    "груди",
    "день",
    "дней",
    "есть",
    "жалоба",
    "жалуется",
    "по",
    "пациент",
    "пациентка",
    "подозрение",
    "подозревается",
    "при",
    "с",
    "со",
    "течение",
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
    "остеохондроз": {"спондилопат", "спондилез", "дорсопат", "дегенератив", "позвоноч"},
    "спондилопат": {"остеохондроз", "спондилез", "дорсопат", "дегенератив", "позвоноч"},
    "спондилез": {"остеохондроз", "спондилопат", "дорсопат", "дегенератив"},
    "дорсопат": {"остеохондроз", "спондилопат", "спондилез", "позвоноч"},
    "шейн": {"цервикальн", "позвоноч", "шея"},
    "цервикальн": {"шейн", "позвоноч", "шея"},
    "радикулопат": {"корешк", "невролог", "нейропат"},
    "миелопат": {"спинн", "мозг", "невролог"},
}

_PDF_FILENAME_PATTERN = re.compile(r"^(?:кр|kr)[\s._-]*0*(\d+)(?:[\s._-].*)?$", re.IGNORECASE)
_PDF_NUMBER_FALLBACK_PATTERN = re.compile(r"(?<!\d)0*(\d{1,5})(?!\d)")

logger = logging.getLogger(__name__)


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


def _build_pdf_lookup(pdf_dir: Path) -> dict[int, Path]:
    candidates_by_number: dict[int, list[Path]] = {}
    for path in pdf_dir.iterdir():
        if not path.is_file() or path.suffix.casefold() != ".pdf":
            continue
        pdf_number = _extract_pdf_number_from_filename(path)
        if pdf_number is None:
            continue
        candidates_by_number.setdefault(pdf_number, []).append(path)

    return {
        number: _select_preferred_pdf_path(number=number, candidates=candidates)
        for number, candidates in candidates_by_number.items()
    }


def _select_preferred_pdf_path(*, number: int, candidates: list[Path]) -> Path:
    return min(
        candidates,
        key=lambda path: _pdf_candidate_sort_key(path=path, number=number),
    )


def _pdf_candidate_sort_key(*, path: Path, number: int) -> tuple[int, int, str]:
    normalized_stem = re.sub(r"[\s._-]+", "", path.stem.casefold())
    metadata_rank = 1 if path.name.startswith("._") else 0
    if normalized_stem == f"кр{number}":
        rank = 0
    elif normalized_stem == f"kr{number}":
        rank = 1
    elif normalized_stem.startswith(f"кр{number}"):
        rank = 2
    elif normalized_stem.startswith(f"kr{number}"):
        rank = 3
    else:
        rank = 4
    return metadata_rank, rank, len(normalized_stem), path.name.casefold()


def _extract_pdf_number_from_filename(path: Path) -> int | None:
    match = _PDF_FILENAME_PATTERN.match(path.stem)
    if match is not None:
        return int(match.group(1))

    fallback_match = _PDF_NUMBER_FALLBACK_PATTERN.search(path.stem)
    if fallback_match is not None:
        return int(fallback_match.group(1))
    return None


class ClinicalRecommendationsService:
    """Load official recommendations from CSV and expose lookup and search helpers."""

    def __init__(
        self,
        csv_path: Path,
        pdf_dir: Path,
        *,
        embedding_index: ClinicalRecommendationEmbeddingIndex | None = None,
        embeddings_enabled: bool = False,
    ) -> None:
        self._csv_path = csv_path
        self._pdf_dir = pdf_dir
        self._embedding_index = embedding_index
        self._embeddings_enabled = embeddings_enabled and embedding_index is not None
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

        lexical_results = self._search_by_lexical(normalized_query=normalized_query, limit=None)
        embedding_results: list[SearchResult] = []
        try:
            embedding_results = self._search_by_embeddings(query=query, limit=max(limit * 20, 100))
        except Exception as exc:
            logger.warning("Embedding search failed for query %r, falling back to lexical ranking: %s", query, exc)
        if embedding_results:
            hybrid_results = self._merge_search_results(
                embedding_results=embedding_results,
                lexical_results=lexical_results,
            )
            if hybrid_results:
                return self._ensure_pdf_backfill(
                    results=hybrid_results,
                    normalized_query=normalized_query,
                    limit=limit,
                )

        return self._ensure_pdf_backfill(
            results=lexical_results,
            normalized_query=normalized_query,
            limit=limit,
        )

    def _search_by_lexical(self, *, normalized_query: str, limit: int | None) -> list[SearchResult]:
        if not normalized_query:
            return []

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
        return scored[:limit] if limit is not None else scored

    def ensure_embedding_index(self, *, force: bool = False) -> None:
        if not self._embeddings_enabled or self._embedding_index is None:
            return
        self._embedding_index.ensure_current(self._entries, force=force)

    def get_pdf_path(self, recommendation_id: str) -> Path:
        entry = self.get_entry(recommendation_id)
        if entry.pdf_path is None:
            raise ApiError(
                code="PDF_NOT_FOUND",
                message=f"PDF for clinical recommendation '{recommendation_id}' is not available.",
                status_code=404,
            )
        return entry.pdf_path

    def _search_by_embeddings(self, *, query: str, limit: int) -> list[SearchResult]:
        if not self._embeddings_enabled or self._embedding_index is None:
            return []

        matches = self._embedding_index.search(query, limit=limit)
        results: list[SearchResult] = []
        for match in matches:
            entry = self._entries_by_id.get(match.recommendation_id)
            if entry is None:
                continue
            results.append(SearchResult(entry=entry, score=match.score))
        return results

    def _merge_search_results(
        self,
        *,
        embedding_results: list[SearchResult],
        lexical_results: list[SearchResult],
    ) -> list[SearchResult]:
        if not embedding_results:
            return []

        embedding_by_id = {result.entry.id: result for result in embedding_results}
        lexical_by_id = {result.entry.id: result for result in lexical_results}
        max_lexical_score = max((result.score for result in lexical_results), default=0.0)
        candidate_ids = set(embedding_by_id) | set(lexical_by_id)

        merged: list[SearchResult] = []
        for recommendation_id in candidate_ids:
            entry = self._entries_by_id.get(recommendation_id)
            if entry is None:
                continue

            embedding_score = (
                embedding_by_id.get(recommendation_id).score
                if recommendation_id in embedding_by_id
                else 0.0
            )
            lexical_score = (
                lexical_by_id.get(recommendation_id).score
                if recommendation_id in lexical_by_id
                else 0.0
            )
            normalized_lexical_score = (
                lexical_score / max_lexical_score if max_lexical_score > 0 else 0.0
            )
            if max_lexical_score > 0:
                score = (0.15 * embedding_score) + (0.85 * normalized_lexical_score)
            else:
                score = embedding_score
            if score > 0:
                merged.append(SearchResult(entry=entry, score=round(score, 4)))

        merged.sort(
            key=lambda item: (
                -item.score,
                item.entry.title.lower(),
                item.entry.id,
            ),
        )
        return merged

    def _ensure_pdf_backfill(
        self,
        *,
        results: list[SearchResult],
        normalized_query: str,
        limit: int,
    ) -> list[SearchResult]:
        trimmed = results[:limit]
        if limit <= 0:
            return []
        if any(result.entry.pdf_available for result in trimmed):
            return trimmed

        backfill = self._search_pdf_backfill(normalized_query=normalized_query, limit=limit)
        if not backfill:
            return trimmed

        existing_ids = {result.entry.id for result in trimmed}
        for candidate in backfill:
            if candidate.entry.id in existing_ids:
                continue
            if len(trimmed) < limit:
                trimmed.append(candidate)
            else:
                trimmed[-1] = candidate
            break
        return trimmed

    def _search_pdf_backfill(self, *, normalized_query: str, limit: int) -> list[SearchResult]:
        query_tokens = set(_tokenize(normalized_query))
        expanded_query_tokens = _expand_query_tokens(query_tokens) if query_tokens else set()
        candidates = [entry for entry in self._entries if entry.pdf_available] or self._entries

        scored: list[SearchResult] = []
        for entry in candidates:
            overlap = len(expanded_query_tokens & entry.search_tokens)
            sequence_ratio = SequenceMatcher(None, normalized_query, entry.normalized_title).ratio()
            score = round((0.08 * overlap) + (0.12 * sequence_ratio), 4)
            if score <= 0:
                continue
            scored.append(SearchResult(entry=entry, score=score))

        scored.sort(
            key=lambda item: (
                -item.score,
                not item.entry.pdf_available,
                item.entry.title.lower(),
                item.entry.id,
            ),
        )
        return scored[:limit]

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
        return score if score >= 0.5 else 0.0

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

        synonyms = _TOKEN_SYNONYMS.get(query_token, set())
        if any(
            entry_token.startswith(synonym) or synonym.startswith(entry_token)
            for synonym in synonyms
            for entry_token in entry_tokens
        ):
            return 0.9

        if any(token.startswith(query_token) or query_token.startswith(token) for token in entry_tokens):
            return 0.65

        return 0.0

    @staticmethod
    def _load_entries(csv_path: Path, pdf_dir: Path) -> list[ClinicalRecommendationEntry]:
        if not csv_path.is_file():
            raise RuntimeError(f"Clinical recommendations CSV not found: {csv_path}")
        if not pdf_dir.is_dir():
            raise RuntimeError(f"Clinical recommendations PDF directory not found: {pdf_dir}")

        pdf_lookup = _build_pdf_lookup(pdf_dir)
        entries: list[ClinicalRecommendationEntry] = []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as file_obj:
            reader = csv.DictReader(file_obj, delimiter=";")
            for row in reader:
                recommendation_id = row["ID"].strip()
                pdf_number = ClinicalRecommendationsService._extract_pdf_number(recommendation_id)
                pdf_filename = f"КР{pdf_number}.pdf"
                expected_pdf_path = pdf_dir / pdf_filename
                pdf_path = expected_pdf_path if expected_pdf_path.is_file() else pdf_lookup.get(pdf_number)
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
                        pdf_available=pdf_path is not None and pdf_path.is_file(),
                        pdf_path=pdf_path if pdf_path is not None and pdf_path.is_file() else None,
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
