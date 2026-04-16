from __future__ import annotations

import argparse
import logging

from app.core.config import get_settings
from app.services.embeddings import ClinicalRecommendationEmbeddingIndex
from app.services.pdf_assets import ensure_pdf_assets
from app.services.recommendations import ClinicalRecommendationsService


def main() -> None:
    parser = argparse.ArgumentParser(description="Build clinical recommendation PDF embeddings.")
    parser.add_argument("--force", action="store_true", help="Rebuild the parquet index even if it is current.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()
    ensure_pdf_assets(
        pdf_dir=settings.clinical_recommendations_pdf_dir,
        archive_url=settings.clinical_recommendations_pdf_archive_url,
        archive_path=settings.clinical_recommendations_pdf_archive_path,
        download_enabled=settings.clinical_recommendations_pdf_download_enabled,
    )
    embedding_index = ClinicalRecommendationEmbeddingIndex(
        embeddings_path=settings.clinical_recommendations_embeddings_path,
        model_name=settings.clinical_recommendations_embedding_model_name,
        token_limit=settings.clinical_recommendations_embedding_token_limit,
        batch_size=settings.clinical_recommendations_embedding_batch_size,
        min_score=settings.clinical_recommendations_embedding_min_score,
        pdf_text_max_chars=settings.clinical_recommendations_pdf_text_max_chars,
        query_prefix=settings.clinical_recommendations_embedding_query_prefix,
        passage_prefix=settings.clinical_recommendations_embedding_passage_prefix,
    )
    service = ClinicalRecommendationsService(
        csv_path=settings.clinical_recommendations_csv_path,
        pdf_dir=settings.clinical_recommendations_pdf_dir,
        embedding_index=embedding_index,
        embeddings_enabled=True,
    )
    service.ensure_embedding_index(force=args.force)
    print(settings.clinical_recommendations_embeddings_path)


if __name__ == "__main__":
    main()
