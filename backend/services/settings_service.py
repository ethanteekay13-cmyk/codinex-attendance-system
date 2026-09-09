"""
System settings service.

Wraps the single-row system_settings table so the rest of the backend can
read and update the admin-editable office IP list and Wi-Fi override state
without touching Supabase query syntax directly. All reads/writes use the
service-role client (RLS on this table has no public policies).
"""
from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from core.config import settings as app_settings
from services.supabase_client import get_service_client

SETTINGS_ROW_ID = 1


def get_system_settings() -> dict:
    """
    Returns the current settings row, auto-clearing an expired Wi-Fi
    override so callers never see a stale "still enabled" flag past its
    own expiry time.
    """
    client = get_service_client()
    result = (
        client.table("system_settings").select("*").eq("id", SETTINGS_ROW_ID).limit(1).execute()
    )
    rows = result.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "System settings row is missing. Run "
                "backend/migrations/002_settings_and_wifi_override.sql in Supabase."
            ),
        )

    row = rows[0]

    if row.get("wifi_override_enabled") and _is_expired(row.get("wifi_override_expires_at")):
        row = _disable_wifi_override_row(client)

    return row


def _is_expired(expires_at_raw: Optional[str]) -> bool:
    if not expires_at_raw:
        return True
    expires_at = datetime.fromisoformat(str(expires_at_raw).replace("Z", "+00:00"))
    return datetime.now(expires_at.tzinfo) >= expires_at


def update_office_ips(ips: List[str]) -> dict:
    """Replaces the full list of office IP addresses."""
    cleaned = [ip.strip() for ip in ips if ip.strip()]
    client = get_service_client()
    result = (
        client.table("system_settings")
        .update({"office_ips": cleaned, "updated_at": datetime.utcnow().isoformat()})
        .eq("id", SETTINGS_ROW_ID)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update the office IP list",
        )
    return result.data[0]


def enable_wifi_override(admin_id: str) -> dict:
    """
    Enables the Wi-Fi override until the end of the current day in
    CODINEX_TIMEZONE, so it never has to be remembered and manually turned
    off - at worst it is active for the rest of "today".
    """
    local_now = datetime.now(ZoneInfo(app_settings.CODINEX_TIMEZONE))
    end_of_day = local_now.replace(hour=23, minute=59, second=59, microsecond=0)

    client = get_service_client()
    result = (
        client.table("system_settings")
        .update(
            {
                "wifi_override_enabled": True,
                "wifi_override_expires_at": end_of_day.isoformat(),
                "wifi_override_enabled_by": admin_id,
                "wifi_override_enabled_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
        )
        .eq("id", SETTINGS_ROW_ID)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not enable the Wi-Fi override",
        )
    return result.data[0]


def _disable_wifi_override_row(client) -> dict:
    result = (
        client.table("system_settings")
        .update(
            {
                "wifi_override_enabled": False,
                "wifi_override_expires_at": None,
                "updated_at": datetime.utcnow().isoformat(),
            }
        )
        .eq("id", SETTINGS_ROW_ID)
        .execute()
    )
    return result.data[0] if result.data else {}


def disable_wifi_override() -> dict:
    """Manually turns the Wi-Fi override off early (before its own expiry)."""
    client = get_service_client()
    return _disable_wifi_override_row(client)


def update_cutoff_times(present_cutoff_time: str, late_cutoff_time: str) -> dict:
    """Updates the present/late check-in cutoff times used by check-in."""
    client = get_service_client()
    result = (
        client.table("system_settings")
        .update(
            {
                "present_cutoff_time": present_cutoff_time,
                "late_cutoff_time": late_cutoff_time,
                "updated_at": datetime.utcnow().isoformat(),
            }
        )
        .eq("id", SETTINGS_ROW_ID)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update the cutoff times",
        )
    return result.data[0]
