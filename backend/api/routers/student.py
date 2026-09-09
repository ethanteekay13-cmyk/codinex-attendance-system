"""
Student-facing endpoints (require an authenticated student).
"""
from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_current_student
from models.schemas import AttendanceHistoryResponse, ChangePasswordRequest, StudentOut
from services import attendance_stats
from services.supabase_client import get_anon_client, get_service_client

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/me", response_model=StudentOut)
def get_my_profile(student: dict = Depends(get_current_student)):
    """Returns the profile of the currently authenticated student."""
    return student


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
    summary = attendance_stats.summarize_records(records, student.get("created_at"))

    return AttendanceHistoryResponse(records=records, **summary)


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
