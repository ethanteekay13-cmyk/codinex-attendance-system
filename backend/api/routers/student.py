"""
Student-facing endpoints (require an authenticated student).
"""
from datetime import datetime, date as date_cls
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_current_student
from core.config import settings
from models.schemas import AttendanceHistoryResponse, ChangePasswordRequest, StudentOut
from services.supabase_client import get_anon_client, get_service_client

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/me", response_model=StudentOut)
def get_my_profile(student: dict = Depends(get_current_student)):
    """Returns the profile of the currently authenticated student."""
    return student


def _count_business_days(start: date_cls, end: date_cls) -> int:
    """
    Counts Monday-to-Friday business days between two dates inclusive.
    Used as the denominator for the attendance percentage, since interns
    are only expected to check in on working days.
    """
    if end < start:
        return 0
    total = 0
    current = start
    one_day = 1
    while current <= end:
        if current.weekday() < 5:  # Monday=0 ... Sunday=6
            total += 1
        current = date_cls.fromordinal(current.toordinal() + one_day)
    return total


@router.get("/me/history", response_model=AttendanceHistoryResponse)
def get_my_history(student: dict = Depends(get_current_student)):
    """
    Returns the authenticated student's full check-in history along with
    an attendance percentage computed against expected business days since
    the student's registration date.
    """
    service_client = get_service_client()
    result = (
        service_client.table("attendance")
        .select("*")
        .eq("student_id", student["student_id"])
        .order("date", desc=True)
        .execute()
    )
    records = result.data or []

    total_present = sum(1 for r in records if r.get("status") == "present")
    total_late = sum(1 for r in records if r.get("status") == "late")

    created_at_raw = student.get("created_at")
    today_local = datetime.now(ZoneInfo(settings.CODINEX_TIMEZONE)).date()

    if created_at_raw:
        try:
            registration_date = datetime.fromisoformat(
                str(created_at_raw).replace("Z", "+00:00")
            ).date()
        except ValueError:
            registration_date = today_local
    else:
        registration_date = today_local

    expected_days = _count_business_days(registration_date, today_local)
    total_absent = max(expected_days - (total_present + total_late), 0)

    attendance_percentage = (
        round(((total_present + total_late) / expected_days) * 100, 2)
        if expected_days > 0
        else 0.0
    )

    return AttendanceHistoryResponse(
        records=records,
        total_present=total_present,
        total_late=total_late,
        total_absent=total_absent,
        attendance_percentage=attendance_percentage,
    )


@router.post("/me/change-password")
def change_my_password(
    payload: ChangePasswordRequest, student: dict = Depends(get_current_student)
):
    """
    Lets a student change their own password after signing in with the
    one an admin originally set for them. The current password must be
    supplied and verified first, so a stolen/left-open session alone
    isn't enough to lock the real student out of their own account.
    """
    anon_client = get_anon_client()
    try:
        anon_client.auth.sign_in_with_password(
            {"email": student["email"], "password": payload.current_password}
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your current password is incorrect",
        )

    service_client = get_service_client()
    try:
        service_client.auth.admin.update_user_by_id(
            student["user_id"], {"password": payload.new_password}
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not update your password: {exc}",
        )

    return {"detail": "Password updated successfully"}
