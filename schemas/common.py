from pydantic import BaseModel
from fastapi.responses import JSONResponse


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    """Factory that returns a JSONResponse with the standard error envelope."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )
