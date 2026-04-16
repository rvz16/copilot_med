from pathlib import Path

from app.services.embeddings import ClinicalRecommendationEmbeddingIndex
from app.services.recommendations import ClinicalRecommendationsService


class DummyEmbeddingBackend:
    model_name = "dummy-model"
    token_limit = 32

    def truncate_text(self, text: str) -> tuple[str, int]:
        return text, min(len(text), self.token_limit)

    def encode_texts(self, texts: list[str]):
        raise AssertionError("encode_texts() should not be called in this test")


class RecordingEmbeddingIndex(ClinicalRecommendationEmbeddingIndex):
    def __init__(self, *, embeddings_path: Path) -> None:
        super().__init__(
            embeddings_path=embeddings_path,
            model_name="dummy-model",
            token_limit=32,
            batch_size=1,
            min_score=0.1,
            pdf_text_max_chars=1000,
            backend=DummyEmbeddingBackend(),
        )
        self.build_calls = 0
        self.load_calls = 0

    def build(self, entries) -> None:
        self.build_calls += 1

    def load(self) -> None:
        self.load_calls += 1

    def _is_current(self, entries) -> bool:
        return False


def test_service_matches_noncanonical_archive_pdf_filename(sample_data):
    csv_path, pdf_dir = sample_data
    (pdf_dir / "КР30.pdf").unlink()
    alternate_pdf_path = pdf_dir / "kr-30.PDF"
    alternate_pdf_path.write_bytes(b"%PDF-1.4\nlung-cancer\n")

    service = ClinicalRecommendationsService(
        csv_path=csv_path,
        pdf_dir=pdf_dir,
        embeddings_enabled=False,
    )

    entry = service.get_entry("30_5")

    assert entry.pdf_available is True
    assert entry.pdf_path == alternate_pdf_path


def test_existing_parquet_is_reused_when_no_pdfs_match(sample_data, tmp_path: Path):
    csv_path, _ = sample_data
    empty_pdf_dir = tmp_path / "empty_pdf_files"
    empty_pdf_dir.mkdir()
    embeddings_path = tmp_path / "recommendation_embeddings.parquet"
    embeddings_path.write_text("tracked-index", encoding="utf-8")
    embedding_index = RecordingEmbeddingIndex(embeddings_path=embeddings_path)

    service = ClinicalRecommendationsService(
        csv_path=csv_path,
        pdf_dir=empty_pdf_dir,
        embedding_index=embedding_index,
        embeddings_enabled=True,
    )

    service.ensure_embedding_index()

    assert embedding_index.build_calls == 0
    assert embedding_index.load_calls == 1


def test_service_matches_mojibake_pdf_filename(sample_data):
    csv_path, pdf_dir = sample_data
    (pdf_dir / "КР30.pdf").unlink()
    mojibake_pdf_path = pdf_dir / "╨Ü╨á30.pdf"
    mojibake_pdf_path.write_bytes(b"%PDF-1.4\nlung-cancer\n")

    service = ClinicalRecommendationsService(
        csv_path=csv_path,
        pdf_dir=pdf_dir,
        embeddings_enabled=False,
    )

    entry = service.get_entry("30_5")

    assert entry.pdf_available is True
    assert entry.pdf_path == mojibake_pdf_path
