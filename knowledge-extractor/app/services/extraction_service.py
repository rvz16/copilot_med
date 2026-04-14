from app.models import ExtractionRequest, ExtractionResponse

from .documentation_service import DocumentationService


class ExtractionService:
    """Compatibility wrapper around the active documentation pipeline."""

    def __init__(self, documentation_service: DocumentationService | None = None) -> None:
        self.documentation_service = documentation_service or DocumentationService()

    def process(self, request: ExtractionRequest) -> ExtractionResponse:
        return self.documentation_service.build_documentation(request)
