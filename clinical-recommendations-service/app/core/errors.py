import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Structured API exception with a stable code and HTTP status."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def format_validation_error(exc: RequestValidationError) -> str:
    details: list[str] = []
    for err in exc.errors():
        location = ".".join(str(item) for item in err.get("loc", []) if item != "body")
        prefix = f"{location}: " if location else ""
        details.append(f"{prefix}{err.get('msg', 'Invalid value')}")
    return "; ".join(details) if details else "Invalid request."


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message)


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(400, "VALIDATION_ERROR", format_validation_error(exc))


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error", exc_info=exc)
    return error_response(500, "INTERNAL_ERROR", "Unexpected server error.")
