"""
Codinex Attendance System - backend entrypoint.

Run locally with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import admin, attendance, auth, student
from core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Attendance tracking API for Codinex Computers Ltd internship students.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(attendance.router, prefix=settings.API_V1_PREFIX)
app.include_router(student.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin.router, prefix=settings.API_V1_PREFIX)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Ensures unexpected errors still return a normal CORS-compliant JSON
    response instead of a bare 500 that the browser reports as a CORS
    failure. The full error is printed server-side for debugging.
    """
    print(f"Unhandled error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please check the server logs."},
    )


@app.get("/", tags=["health"])
def health_check():
    """Basic liveness endpoint used by uptime checks and load balancers."""
    return {"status": "ok", "service": settings.APP_NAME}


@app.on_event("startup")
def on_startup():
    print(f"{settings.APP_NAME} backend starting up")
    if settings.ENFORCE_OFFICE_WIFI and not settings.CODINEX_OFFICE_IPS:
        print(
            "WARNING: ENFORCE_OFFICE_WIFI is true but CODINEX_OFFICE_IPS is empty. "
            "All check-in requests will be rejected until this is configured."
        )
