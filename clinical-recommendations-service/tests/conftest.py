from collections.abc import Callable
from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def sample_data(tmp_path: Path) -> tuple[Path, Path]:
    csv_path = tmp_path / "clinical_recommendations.csv"
    pdf_dir = tmp_path / "pdf_files"
    pdf_dir.mkdir()

    csv_path.write_text(
        "\n".join(
            [
                "ID;Наименование;МКБ-10;Возрастная категория;Разработчик;Статус одобрения НПС;Дата размещения;Статус применения",
                "30_5;Злокачественное новообразование бронхов и легкого;C34;Взрослые;Минздрав;Да;10.01.2026;Применяется",
                "603_3;Хроническая обструктивная болезнь легких;J44;Взрослые;Минздрав;Да;11.01.2026;Применяется",
                "379_4;Рак молочной железы;C50;Взрослые;Минздрав;Да;12.01.2026;Применяется",
                "286_3;Сахарный диабет 1 типа у взрослых;E10.2, E10.3;Взрослые;Минздрав;Да;13.01.2026;Применяется",
            ]
        ),
        encoding="utf-8",
    )
    (pdf_dir / "КР30.pdf").write_bytes(b"%PDF-1.4\nlung-cancer\n")
    (pdf_dir / "КР379.pdf").write_bytes(b"%PDF-1.4\nbreast-cancer\n")
    return csv_path, pdf_dir


@pytest.fixture
def app_factory(sample_data: tuple[Path, Path]) -> Callable[..., object]:
    csv_path, pdf_dir = sample_data

    def _create(**overrides: object):
        config = {
            "APP_ENV": "test",
            "HOST": "127.0.0.1",
            "PORT": 8002,
            "CORS_ORIGINS": ["http://localhost:5173"],
            "CLINICAL_RECOMMENDATIONS_CSV_PATH": csv_path,
            "CLINICAL_RECOMMENDATIONS_PDF_DIR": pdf_dir,
        }
        config.update(overrides)
        settings = Settings(**config)
        return create_app(settings)

    return _create


@pytest.fixture
def client(app_factory: Callable[..., object]):
    app = app_factory()
    with TestClient(app) as test_client:
        yield test_client
