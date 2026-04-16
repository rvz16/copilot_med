from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import numpy as np

    NDArrayFloat = np.ndarray
else:
    NDArrayFloat = object

logger = logging.getLogger(__name__)


class RecommendationEntryLike(Protocol):
    id: str
    title: str
    pdf_filename: str
    pdf_available: bool
    pdf_path: Path | None


@dataclass(frozen=True)
class EmbeddingSearchMatch:
    recommendation_id: str
    score: float


class EmbeddingBackend(Protocol):
    model_name: str
    token_limit: int

    def truncate_text(self, text: str) -> tuple[str, int]:
        ...

    def encode_texts(self, texts: list[str]) -> NDArrayFloat:
        ...


class BertEmbeddingBackend:
    """Small Russian BERT encoder with mean pooling and L2-normalized vectors."""

    def __init__(self, *, model_name: str, token_limit: int, batch_size: int) -> None:
        self.model_name = model_name
        self.token_limit = token_limit
        self.batch_size = batch_size
        self._tokenizer = None
        self._model = None
        self._device = None

    def truncate_text(self, text: str) -> tuple[str, int]:
        self._ensure_loaded()
        token_ids = self._tokenizer.encode(
            text,
            add_special_tokens=False,
            max_length=self.token_limit,
            truncation=True,
        )
        return self._tokenizer.decode(token_ids, skip_special_tokens=True), len(token_ids)

    def encode_texts(self, texts: list[str]) -> NDArrayFloat:
        self._ensure_loaded()
        import numpy as np
        import torch

        vectors = []
        for offset in range(0, len(texts), self.batch_size):
            batch = texts[offset : offset + self.batch_size]
            encoded = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self.token_limit,
                return_tensors="pt",
            )
            encoded = {key: value.to(self._device) for key, value in encoded.items()}
            with torch.no_grad():
                output = self._model(**encoded)
            last_hidden_state = output.last_hidden_state
            if getattr(last_hidden_state, "device", None) is not None and last_hidden_state.device.type == "meta":
                raise RuntimeError(
                    f"Embedding model {self.model_name} returned meta tensors during inference."
                )
            attention_mask = encoded["attention_mask"]
            if getattr(last_hidden_state, "device", None) is not None:
                attention_mask = attention_mask.to(last_hidden_state.device)
            embeddings = _mean_pool(last_hidden_state, attention_mask)
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
            vectors.append(embeddings.cpu().numpy().astype("float32"))

        if not vectors:
            return np.empty((0, 0), dtype="float32")
        return np.vstack(vectors).astype("float32")

    def _ensure_loaded(self) -> None:
        if self._tokenizer is not None and self._model is not None:
            return

        import torch
        from transformers import AutoModel, AutoTokenizer

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Loading embedding model %s on %s", self.model_name, self._device)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModel.from_pretrained(self.model_name)
        self._model.to(self._device)
        self._model.eval()


class ClinicalRecommendationEmbeddingIndex:
    """Build, persist, and query PDF embeddings for clinical recommendations."""

    def __init__(
        self,
        *,
        embeddings_path: Path,
        model_name: str,
        token_limit: int,
        batch_size: int,
        min_score: float,
        pdf_text_max_chars: int,
        query_prefix: str = "",
        passage_prefix: str = "",
        backend: EmbeddingBackend | None = None,
    ) -> None:
        self.embeddings_path = embeddings_path
        self.model_name = model_name
        self.token_limit = token_limit
        self.batch_size = batch_size
        self.min_score = min_score
        self.pdf_text_max_chars = pdf_text_max_chars
        self.query_prefix = query_prefix
        self.passage_prefix = passage_prefix
        self.backend = backend or BertEmbeddingBackend(
            model_name=model_name,
            token_limit=token_limit,
            batch_size=batch_size,
        )
        self._ids: list[str] = []
        self._matrix = None

    def ensure_current(self, entries: list[RecommendationEntryLike], *, force: bool = False) -> None:
        available_entries = self._available_entries(entries)
        if force:
            self.build(entries)
        elif available_entries:
            if not self._is_current(entries):
                self.build(entries)
        elif self.embeddings_path.is_file():
            logger.warning(
                "No matched clinical recommendation PDFs were found; reusing existing embedding index at %s",
                self.embeddings_path,
            )
        else:
            raise RuntimeError(
                "No matched clinical recommendation PDFs were found and no existing embedding index is available."
            )
        self.load()

    def build(self, entries: list[RecommendationEntryLike]) -> None:
        documents: list[tuple[RecommendationEntryLike, str, int, int, int]] = []
        for entry in entries:
            if not entry.pdf_available or entry.pdf_path is None:
                continue
            text = extract_pdf_text(entry.pdf_path, max_chars=self.pdf_text_max_chars)
            if not text:
                logger.warning(
                    "No extractable text found in %s; falling back to recommendation title",
                    entry.pdf_path,
                )
                text = entry.title
            document_text = self._build_document_text(entry=entry, pdf_text=text)
            truncated_text, token_count = self.backend.truncate_text(document_text)
            stat = entry.pdf_path.stat()
            documents.append((entry, truncated_text, token_count, stat.st_size, stat.st_mtime_ns))

        if not documents:
            raise RuntimeError("No matched clinical recommendation PDFs are available for embedding.")

        logger.info("Building embeddings for %s clinical recommendation PDFs", len(documents))
        texts = [document[1] for document in documents]
        embeddings = self.backend.encode_texts(texts)
        self.embeddings_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_parquet(documents=documents, embeddings=embeddings)
        logger.info("Saved clinical recommendation embeddings to %s", self.embeddings_path)

    def load(self) -> None:
        import numpy as np
        import pyarrow.parquet as pq

        table = pq.read_table(self.embeddings_path)
        data = table.to_pydict()
        self._ids = [str(value) for value in data["recommendation_id"]]
        self._matrix = np.asarray(data["embedding"], dtype="float32")

    def search(self, query: str, *, limit: int) -> list[EmbeddingSearchMatch]:
        if self._matrix is None or not self._ids:
            self.load()

        import numpy as np

        query_text, _ = self.backend.truncate_text(f"{self.query_prefix}{query}")
        query_vector = self.backend.encode_texts([query_text])
        if query_vector.size == 0:
            return []

        scores = np.matmul(self._matrix, query_vector[0])
        order = np.argsort(scores)[::-1]
        matches: list[EmbeddingSearchMatch] = []
        for index in order:
            score = float(scores[index])
            if score < self.min_score:
                continue
            matches.append(
                EmbeddingSearchMatch(
                    recommendation_id=self._ids[int(index)],
                    score=round(score, 4),
                )
            )
            if len(matches) >= limit:
                break
        return matches

    def _is_current(self, entries: list[RecommendationEntryLike]) -> bool:
        if not self.embeddings_path.is_file():
            return False

        try:
            import pyarrow.parquet as pq

            data = pq.read_table(
                self.embeddings_path,
                columns=[
                    "recommendation_id",
                    "model_name",
                    "token_limit",
                    "passage_prefix",
                    "pdf_size",
                ],
            ).to_pydict()
        except Exception as exc:
            logger.warning("Failed to inspect existing embedding index %s: %s", self.embeddings_path, exc)
            return False

        indexed = {
            recommendation_id: {
                "model_name": model_name,
                "token_limit": token_limit,
                "passage_prefix": passage_prefix,
                "pdf_size": pdf_size,
            }
            for recommendation_id, model_name, token_limit, passage_prefix, pdf_size in zip(
                data["recommendation_id"],
                data["model_name"],
                data["token_limit"],
                data["passage_prefix"],
                data["pdf_size"],
                strict=True,
            )
        }
        expected_entries = [
            entry
            for entry in entries
            if entry.pdf_available and entry.pdf_path is not None and entry.pdf_path.is_file()
        ]
        if len(indexed) != len(expected_entries):
            return False

        for entry in expected_entries:
            row = indexed.get(entry.id)
            if row is None:
                return False
            stat = entry.pdf_path.stat()
            if row["model_name"] != self.model_name:
                return False
            if int(row["token_limit"]) != self.token_limit:
                return False
            if row["passage_prefix"] != self.passage_prefix:
                return False
            if int(row["pdf_size"]) != stat.st_size:
                return False
        return True

    def _build_document_text(self, *, entry: RecommendationEntryLike, pdf_text: str) -> str:
        title = entry.title.strip()
        if title and title.casefold() not in pdf_text[:1000].casefold():
            pdf_text = f"{title}. {pdf_text}"
        return f"{self.passage_prefix}{pdf_text}"

    @staticmethod
    def _available_entries(entries: list[RecommendationEntryLike]) -> list[RecommendationEntryLike]:
        return [
            entry
            for entry in entries
            if entry.pdf_available and entry.pdf_path is not None and entry.pdf_path.is_file()
        ]

    def _write_parquet(
        self,
        *,
        documents: list[tuple[RecommendationEntryLike, str, int, int, int]],
        embeddings,
    ) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        rows = {
            "recommendation_id": [],
            "title": [],
            "pdf_filename": [],
            "model_name": [],
            "token_limit": [],
            "passage_prefix": [],
            "text_token_count": [],
            "extracted_text": [],
            "pdf_size": [],
            "pdf_mtime_ns": [],
            "embedding": [],
        }
        for index, (entry, text, token_count, pdf_size, pdf_mtime_ns) in enumerate(documents):
            rows["recommendation_id"].append(entry.id)
            rows["title"].append(entry.title)
            rows["pdf_filename"].append(entry.pdf_filename)
            rows["model_name"].append(self.model_name)
            rows["token_limit"].append(self.token_limit)
            rows["passage_prefix"].append(self.passage_prefix)
            rows["text_token_count"].append(token_count)
            rows["extracted_text"].append(text)
            rows["pdf_size"].append(pdf_size)
            rows["pdf_mtime_ns"].append(pdf_mtime_ns)
            rows["embedding"].append(embeddings[index].astype("float32").tolist())

        table = pa.table(
            {
                "recommendation_id": pa.array(rows["recommendation_id"], type=pa.string()),
                "title": pa.array(rows["title"], type=pa.string()),
                "pdf_filename": pa.array(rows["pdf_filename"], type=pa.string()),
                "model_name": pa.array(rows["model_name"], type=pa.string()),
                "token_limit": pa.array(rows["token_limit"], type=pa.int32()),
                "passage_prefix": pa.array(rows["passage_prefix"], type=pa.string()),
                "text_token_count": pa.array(rows["text_token_count"], type=pa.int32()),
                "extracted_text": pa.array(rows["extracted_text"], type=pa.string()),
                "pdf_size": pa.array(rows["pdf_size"], type=pa.int64()),
                "pdf_mtime_ns": pa.array(rows["pdf_mtime_ns"], type=pa.int64()),
                "embedding": pa.array(rows["embedding"], type=pa.list_(pa.float32())),
            }
        )
        pq.write_table(table, self.embeddings_path)


def extract_pdf_text(pdf_path: Path, *, max_chars: int) -> str:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Install PyMuPDF to extract clinical recommendation PDF text.") from exc

    chunks: list[str] = []
    char_count = 0
    with fitz.open(pdf_path) as document:
        for page in document:
            page_text = page.get_text("text")
            if not page_text:
                continue
            page_text = _clean_extracted_text(page_text)
            if not page_text:
                continue
            remaining = max_chars - char_count
            if remaining <= 0:
                break
            chunks.append(page_text[:remaining])
            char_count += len(chunks[-1])
            if char_count >= max_chars:
                break
    return _clean_extracted_text(" ".join(chunks))


def _clean_extracted_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"[^\wа-яА-ЯёЁ.,;:!?()%/+\-\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _mean_pool(last_hidden_state, attention_mask):
    import torch

    mask = attention_mask.to(
        device=last_hidden_state.device,
        dtype=last_hidden_state.dtype,
    ).unsqueeze(-1).expand(last_hidden_state.size())
    summed = torch.sum(last_hidden_state * mask, dim=1)
    counts = torch.clamp(mask.sum(dim=1), min=1e-9)
    return summed / counts
