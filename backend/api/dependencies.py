"""
Shared FastAPI dependencies used across routers.
"""
from typing import NamedTuple, Optional

from fastapi import Depends, Header, HTTPException, Request, status

from core.config import settings
from core.security import extract_bearer_token, verify_supabase_access_token
from services.settings_service import get_system_settings
from services.supabase_client import get_service_client


def get_current_user_id(authorization: Optional[str] = Header(default=None)) -> str:
    """Extracts and verifies the caller's Supabase access token, returning their user id."""
    token = extract_bearer_token(authorization)
    return verify_supabase_access_token(token)


def get_current_student(user_id: str = Depends(get_current_user_id)) -> dict:
    """
    Resolves the authenticated Supabase user to a row in the students table.
    Raises 403 if the authenticated user is not a registered student.
    """
    client = get_service_client()
    result = client.table("students").select("*").eq("user_id", user_id).limit(1).execute()
    rows = result.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not registered as a student",
        )
    student = rows[0]
    if student.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This student account is not active",
        )
    return student


def get_current_admin(user_id: str = Depends(get_current_user_id)) -> dict:
    """
    Resolves the authenticated Supabase user to a row in the admins table.
    Raises 403 if the authenticated user is not a registered admin.
    """
    client = get_service_client()
    result = client.table("admins").select("*").eq("user_id", user_id).limit(1).execute()
    rows = result.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not registered as an admin",
        )
    return rows[0]


def get_client_ip(request: Request) -> str:
    """
    Resolves the caller's IP address, preferring the left-most entry of
    X-Forwarded-For (the original client) when the app sits behind a proxy
    or router, and falling back to the direct socket address.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class WifiCheckResult(NamedTuple):
    ip: str
    via_override: bool


def verify_office_wifi(request: Request) -> WifiCheckResult:
    """
    Rejects requests that do not originate from an approved office IP
    address, as configured by admins from the dashboard (system_settings
    .office_ips). If an admin has enabled the Wi-Fi override, any IP is
    allowed until the override's own expiry, and the result is marked so
    the check-in can be tagged for later review.

    ENFORCE_OFFICE_WIFI=false is a local-development-only escape hatch
    that skips this check entirely without touching the database; it
    should always be true in production.
    """
    client_ip = get_client_ip(request)

    if not settings.ENFORCE_OFFICE_WIFI:
        return WifiCheckResult(ip=client_ip, via_override=False)

    system_settings = get_system_settings()

    if system_settings.get("wifi_override_enabled"):
        return WifiCheckResult(ip=client_ip, via_override=True)

    office_ips = system_settings.get("office_ips") or []
    if not office_ips:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "No office IP addresses are configured yet. An admin must add at "
                "least one from the dashboard's settings panel."
            ),
        )

    if client_ip not in office_ips:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Check-in is only allowed from the Codinex office network",
        )

    return WifiCheckResult(ip=client_ip, via_override=False)
