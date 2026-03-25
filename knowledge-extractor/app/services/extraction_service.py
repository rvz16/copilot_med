from app.models import ExtractionRequest, ExtractionResponse, PersistenceResult, SoapNote


class ExtractionService:
    """Stub service for MVP skeleton.

    Extraction logic and FHIR persistence are intentionally not implemented at this stage.
    """

    def process(self, request: ExtractionRequest) -> ExtractionResponse:
        return ExtractionResponse(
            session_id=request.session_id,
            soap_note=SoapNote(),
            extracted_facts={},
            fhir_resources=[],
            persistence=PersistenceResult(enabled=request.persist, created=[], errors=[]),
        )
