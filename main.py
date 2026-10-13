from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi.errors import RateLimitExceeded

from config import settings
from dependencies.rate_limit import limiter
from routers.menu import router as menu_router
from routers.order import router as order_router
from routers.seller import router as seller_router

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="UMKM Ordering API")

# Attach limiter to app state so slowapi middleware can find it
app.state.limiter = limiter

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    # If the detail is already our error envelope, pass it through unchanged.
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        content = exc.detail
    else:
        content = {"error": {"code": "HTTP_ERROR", "message": str(exc.detail)}}
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Too many requests"}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {
            "field": ".".join(str(loc) for loc in err["loc"]),
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": details,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    body: dict = {"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}}
    # In development, surface the exception message to aid debugging.
    # Never include stack trace in any environment.
    if settings.environment == "development":
        body["error"]["message"] = str(exc) or "An unexpected error occurred"  # type: ignore[index]
    return JSONResponse(status_code=500, content=body)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(menu_router)
app.include_router(order_router)
app.include_router(seller_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "environment": settings.environment}
