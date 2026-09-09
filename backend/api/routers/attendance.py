"""
Attendance endpoints: dynamic QR token issuance and student check-in.
"""
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, status

from api.dependencies import WifiCheckResult, get_current_student, verify_office_wifi
from core.config import settings
from core.security import get_current_qr_token, verify_qr_token
from models.schemas import AttendanceCheckInRequest, AttendanceOut, QRTokenResponse
from services.supabase_client import get_service_client

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _parse_cutoff(raw: str) -> dt_time:
    hour, minute = (int(part) for part in raw.split(":"))
    return dt_time(hour=hour, minute=minute)


def _local_now() -> datetime:
    return datetime.now(ZoneInfo(settings.CODINEX_TIMEZONE))


def _resolve_status(local_now: datetime) -> str:
    """
    Determines present/late status from the configured cutoff times.
    Check-in is expected to be closed on the frontend/kiosk side after the
    late cutoff; a check-in that still reaches the backend after that time
    is recorded as late rather than rejected, so late arrivals are still
    captured for reporting purposes.
    """
    current_time = local_now.time()
    present_cutoff = _parse_cutoff(settings.PRESENT_CUTOFF_TIME)
    late_cutoff = _parse_cutoff(settings.LATE_CUTOFF_TIME)

    if current_time <= present_cutoff:
        return "present"
    if current_time <= late_cutoff:
        return "late"
    return "late"


@router.get("/qr-token", response_model=QRTokenResponse)
def get_qr_token():
    """
    Returns the currently active dynamic QR token for the kiosk display.
    This endpoint is intentionally unauthenticated so the kiosk display can
    poll it continuously; the token itself is only valid for the current
    15 second window plus a small tolerance, so exposing it publicly does
    not weaken the check-in protocol.
    """
    token, _window, seconds_remaining = get_current_qr_token()

    try:
        service_client = get_service_client()
        service_client.table("qr_sessions").insert(
            {
                "token": token,
                "expires_at": (
                    datetime.utcnow().isoformat()
                ),
                "is_active": True,
            }
        ).execute()
    except Exception:
        # Logging the session is best-effort only; token issuance must not
        # fail because of a transient database or configuration issue.
        pass

    return QRTokenResponse(
        token=token,
        window_seconds=settings.QR_TOKEN_WINDOW_SECONDS,
        seconds_remaining=seconds_remaining,
        server_time=datetime.utcnow(),
    )


@router.post("/check-in", response_model=AttendanceOut)
def check_in(
    payload: AttendanceCheckInRequest,
    request: Request,
    student: dict = Depends(get_current_student),
    wifi_check: WifiCheckResult = Depends(verify_office_wifi),
):
    """
    Records a single daily attendance check-in for the authenticated
    student, enforcing:
      - a valid, current dynamic QR token
      - office Wi-Fi network origin (unless an admin has temporarily
        enabled the Wi-Fi override, in which case the check-in is tagged
        for later review instead of being rejected)
      - at most one check-in per student per day
    """
    if not verify_qr_token(payload.token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This QR code has expired, please rescan the kiosk screen",
        )

    service_client = get_service_client()
    local_now = _local_now()
    today = local_now.date().isoformat()

    existing = (
        service_client.table("attendance")
        .select("attendance_id")
        .eq("student_id", student["student_id"])
        .eq("date", today)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already checked in today",
        )

    device_info = request.headers.get("user-agent", "unknown")
    attendance_status = _resolve_status(local_now)

    try:
        insert_result = (
            service_client.table("attendance")
            .insert(
                {
                    "student_id": student["student_id"],
                    "date": today,
                    "check_in_time": local_now.isoformat(),
                    "status": attendance_status,
                    "device_info": device_info,
                    "ip_address": wifi_check.ip,
                    "via_wifi_override": wifi_check.via_override,
                }
            )
            .execute()
        )
    except Exception as exc:
        # The unique (student_id, date) constraint is the final safeguard
        # against a duplicate check-in racing in between the lookup above
        # and this insert.
        if "duplicate key" in str(exc).lower() or "unique" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already checked in today",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not record attendance, please try again",
        )

    if not insert_result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not record attendance, please try again",
        )

    return insert_result.data[0]
