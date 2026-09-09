"""
Application configuration.

All values are loaded from environment variables so the same codebase can
run in local development, staging, and production without code changes.
See backend/.env.example for the full list of variables and sample values.

load_dotenv() below reads backend/.env (if present) into the process
environment before anything else runs, so os.getenv() picks up values from
that file automatically. It never overrides a variable that is already set
in the real environment, so this is safe in production where the platform
(Render, Railway, Docker, and so on) sets real environment variables
directly instead of shipping a .env file.

Plain os.getenv is used deliberately instead of a settings framework so the
backend has no dependency beyond what is listed in requirements.txt.
"""
import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _parse_list(raw: str) -> List[str]:
    """Splits a comma separated environment variable into a clean list."""
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    # --- Supabase ---
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")

    # --- Dynamic QR token ---
    QR_HMAC_SECRET: str = os.getenv("QR_HMAC_SECRET", "change-this-secret-in-production")
    QR_TOKEN_WINDOW_SECONDS: int = int(os.getenv("QR_TOKEN_WINDOW_SECONDS", "15"))
    QR_TOKEN_LENGTH: int = int(os.getenv("QR_TOKEN_LENGTH", "12"))
    QR_TOKEN_TOLERANCE_WINDOWS: int = int(os.getenv("QR_TOKEN_TOLERANCE_WINDOWS", "1"))

    # --- Office Wi-Fi IP restriction ---
    CODINEX_OFFICE_IPS: List[str] = _parse_list(os.getenv("CODINEX_OFFICE_IPS", ""))
    ENFORCE_OFFICE_WIFI: bool = os.getenv("ENFORCE_OFFICE_WIFI", "true").lower() == "true"

    # --- Attendance business rules ---
    CODINEX_TIMEZONE: str = os.getenv("CODINEX_TIMEZONE", "Africa/Kampala")
    PRESENT_CUTOFF_TIME: str = os.getenv("PRESENT_CUTOFF_TIME", "09:00")
    LATE_CUTOFF_TIME: str = os.getenv("LATE_CUTOFF_TIME", "09:30")

    # --- Student self-service scan link (used only for reference/logging) ---
    STUDENT_SCAN_BASE_URL: str = os.getenv(
        "STUDENT_SCAN_BASE_URL", "https://attendance.codinex.com/student/scan.html"
    )

    # --- CORS ---
    ALLOWED_ORIGINS: List[str] = _parse_list(os.getenv("ALLOWED_ORIGINS", "*"))

    # --- App metadata ---
    APP_NAME: str = "Codinex Attendance System"
    API_V1_PREFIX: str = "/api/v1"


settings = Settings()
