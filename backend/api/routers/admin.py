"""
Admin-facing endpoints (require an authenticated admin).
"""
import csv
import io
from datetime import date as date_cls, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from api.dependencies import get_current_admin
from core.config import settings
from models.schemas import (
    AttendanceHistoryResponse,
    DashboardSummary,
    StudentCreate,
    StudentDetailResponse,
    StudentImportRowResult,
    StudentImportSummary,
    StudentOut,
    SystemSettingsOut,
    TodayAttendanceRow,
    UpdateCutoffTimesRequest,
    UpdateOfficeIpsRequest,
)
from services import attendance_stats, settings_service
from services.supabase_client import get_service_client

router = APIRouter(prefix="/admin", tags=["admin"])

REQUIRED_IMPORT_COLUMNS = [
    "registration_number",
    "full_name",
    "university_name",
    "phone_number",
    "email",
    "password",
]


def _today_local() -> date_cls:
    return datetime.now(ZoneInfo(settings.CODINEX_TIMEZONE)).date()


def _create_student_record(service_client, student: StudentCreate) -> dict:
    """
    Creates a Supabase Auth user for the student, then a matching row in
    the students table. If the students table insert fails, the auth user
    is removed again so partial records are never left behind.
    """
    auth_result = service_client.auth.admin.create_user(
        {
            "email": student.email,
            "password": student.password,
            "email_confirm": True,
        }
    )
    user = getattr(auth_result, "user", None)
    if not user:
        raise RuntimeError("Could not create the authentication account")

    try:
        insert_result = (
            service_client.table("students")
            .insert(
                {
                    "user_id": user.id,
                    "registration_number": student.registration_number,
                    "full_name": student.full_name,
                    "university_name": student.university_name,
                    "phone_number": student.phone_number,
                    "email": student.email,
                    "status": "active",
                }
            )
            .execute()
        )
    except Exception as exc:
        service_client.auth.admin.delete_user(user.id)
        raise RuntimeError(str(exc))

    if not insert_result.data:
        service_client.auth.admin.delete_user(user.id)
        raise RuntimeError("Could not create the student record")

    return insert_result.data[0]


@router.get("/dashboard-summary", response_model=DashboardSummary)
def dashboard_summary(admin: dict = Depends(get_current_admin)):
    """Returns present/late/absent/total counts for the current day."""
    service_client = get_service_client()
    today = _today_local().isoformat()

    students_result = (
        service_client.table("students").select("student_id").eq("status", "active").execute()
    )
    total_students = len(students_result.data or [])

    attendance_result = (
        service_client.table("attendance").select("status").eq("date", today).execute()
    )
    rows = attendance_result.data or []
    present = sum(1 for r in rows if r.get("status") == "present")
    late = sum(1 for r in rows if r.get("status") == "late")
    absent = max(total_students - (present + late), 0)

    return DashboardSummary(
        report_date=_today_local(),
        present=present,
        late=late,
        absent=absent,
        total_students=total_students,
    )


def _basic_ip_looks_valid(ip: str) -> bool:
    """
    A light sanity check, not a strict validator: catches obvious typos
    (empty strings, stray spaces, pasted URLs) without being so strict
    that it rejects IPv6 addresses or CIDR-style entries an admin might
    reasonably want to use.
    """
    return bool(ip) and " " not in ip and len(ip) <= 64


@router.get("/settings", response_model=SystemSettingsOut)
def get_settings(admin: dict = Depends(get_current_admin)):
    """Returns the current office IP list and Wi-Fi override status."""
    return settings_service.get_system_settings()


@router.put("/settings/office-ips", response_model=SystemSettingsOut)
def update_office_ips(payload: UpdateOfficeIpsRequest, admin: dict = Depends(get_current_admin)):
    """
    Replaces the full list of office IP addresses used to gate check-in.
    Takes effect immediately for the next check-in request - no redeploy
    needed.
    """
    invalid = [ip for ip in payload.office_ips if not _basic_ip_looks_valid(ip.strip())]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"These entries don't look like valid IP addresses: {', '.join(invalid)}",
        )
    return settings_service.update_office_ips(payload.office_ips)


def _looks_like_hh_mm(value: str) -> bool:
    try:
        hour, minute = value.split(":")
        return 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59
    except (ValueError, AttributeError):
        return False


@router.put("/settings/cutoff-times", response_model=SystemSettingsOut)
def update_cutoff_times(payload: UpdateCutoffTimesRequest, admin: dict = Depends(get_current_admin)):
    """
    Updates the present/late check-in cutoff times, replacing the
    PRESENT_CUTOFF_TIME/LATE_CUTOFF_TIME environment variables as the
    source of truth. Takes effect on the next check-in - no redeploy.
    """
    if not _looks_like_hh_mm(payload.present_cutoff_time) or not _looks_like_hh_mm(
        payload.late_cutoff_time
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cutoff times must be in 24-hour HH:MM format, e.g. '09:00'",
        )
    if payload.late_cutoff_time < payload.present_cutoff_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The late cutoff must not be earlier than the present cutoff",
        )
    return settings_service.update_cutoff_times(
        payload.present_cutoff_time, payload.late_cutoff_time
    )


@router.post("/settings/wifi-override/enable", response_model=SystemSettingsOut)
def enable_wifi_override(admin: dict = Depends(get_current_admin)):
    """
    Temporarily allows check-in from any IP address, for situations where
    the office Wi-Fi or internet connection is down. Automatically expires
    at the end of the current day so it can never be accidentally left on.
    Check-ins accepted under this override are tagged with
    via_wifi_override so they can be reviewed later.
    """
    return settings_service.enable_wifi_override(admin_id=admin["admin_id"])


@router.post("/settings/wifi-override/disable", response_model=SystemSettingsOut)
def disable_wifi_override(admin: dict = Depends(get_current_admin)):
    """Manually turns the Wi-Fi override off before its automatic expiry."""
    return settings_service.disable_wifi_override()


@router.get("/attendance/today", response_model=list[TodayAttendanceRow])
def get_today_attendance(admin: dict = Depends(get_current_admin)):
    """
    Returns today's check-ins with student names, most recent first, so
    admins can quickly spot and review any that were accepted under the
    Wi-Fi override.
    """
    service_client = get_service_client()
    today = _today_local().isoformat()

    attendance_result = (
        service_client.table("attendance")
        .select("attendance_id, student_id, check_in_time, status, via_wifi_override")
        .eq("date", today)
        .order("check_in_time", desc=True)
        .execute()
    )
    records = attendance_result.data or []
    if not records:
        return []

    student_ids = list({r["student_id"] for r in records})
    students_result = (
        service_client.table("students")
        .select("student_id, full_name, registration_number")
        .in_("student_id", student_ids)
        .execute()
    )
    students_by_id = {s["student_id"]: s for s in (students_result.data or [])}

    rows = []
    for record in records:
        student = students_by_id.get(record["student_id"], {})
        rows.append(
            TodayAttendanceRow(
                attendance_id=record["attendance_id"],
                full_name=student.get("full_name", "Unknown"),
                registration_number=student.get("registration_number", "-"),
                check_in_time=record["check_in_time"],
                status=record["status"],
                via_wifi_override=record.get("via_wifi_override", False),
            )
        )
    return rows


@router.get("/students", response_model=list[StudentOut])
def list_students(
    search: Optional[str] = Query(default=None, description="Search by name, registration number, or email"),
    admin: dict = Depends(get_current_admin),
):
    """
    Lists all registered students, optionally filtered by a search term.
    Each student's attendance percentage is computed in bulk from a
    single attendance-table query rather than one query per student.
    """
    service_client = get_service_client()
    result = service_client.table("students").select("*").order("full_name").execute()
    students = result.data or []

    if search:
        term = search.strip().lower()
        students = [
            s
            for s in students
            if term in (s.get("full_name") or "").lower()
            or term in (s.get("registration_number") or "").lower()
            or term in (s.get("email") or "").lower()
        ]

    if students:
        attendance_result = (
            service_client.table("attendance").select("student_id, status").execute()
        )
        percentages = attendance_stats.bulk_percentages_by_student(
            students, attendance_result.data or []
        )
        for student in students:
            student["attendance_percentage"] = percentages.get(student["student_id"], 0.0)

    return students


@router.get("/students/{student_id}", response_model=StudentDetailResponse)
def get_student_detail(student_id: str, admin: dict = Depends(get_current_admin)):
    """
    Returns one student's profile plus their full check-in history and
    attendance percentage - the admin dashboard's "click a student" view.
    """
    service_client = get_service_client()
    student_result = (
        service_client.table("students").select("*").eq("student_id", student_id).limit(1).execute()
    )
    if not student_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    student = student_result.data[0]

    attendance_result = (
        service_client.table("attendance")
        .select("*")
        .eq("student_id", student_id)
        .order("date", desc=True)
        .execute()
    )
    records = attendance_result.data or []
    summary = attendance_stats.summarize_records(records, student.get("created_at"))
    student["attendance_percentage"] = summary["attendance_percentage"]

    return StudentDetailResponse(
        student=student,
        history=AttendanceHistoryResponse(records=records, **summary),
    )


@router.delete("/students/{student_id}/history")
def delete_student_history(student_id: str, admin: dict = Depends(get_current_admin)):
    """
    Deletes all attendance records for one student while keeping their
    account and profile intact. Use this to correct a mistaken import or
    give a student a clean slate, without removing their login.
    """
    service_client = get_service_client()
    student_result = (
        service_client.table("students").select("student_id").eq("student_id", student_id).limit(1).execute()
    )
    if not student_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    service_client.table("attendance").delete().eq("student_id", student_id).execute()
    return {"detail": "Attendance history deleted"}


@router.delete("/students/{student_id}")
def delete_student(student_id: str, admin: dict = Depends(get_current_admin)):
    """
    Permanently deletes a student: their attendance history, their
    students-table profile, and their Supabase Auth login. This cannot be
    undone.
    """
    service_client = get_service_client()
    student_result = (
        service_client.table("students").select("*").eq("student_id", student_id).limit(1).execute()
    )
    if not student_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    student = student_result.data[0]

    service_client.table("attendance").delete().eq("student_id", student_id).execute()
    service_client.table("students").delete().eq("student_id", student_id).execute()

    if student.get("user_id"):
        try:
            service_client.auth.admin.delete_user(student["user_id"])
        except Exception as exc:
            # The student's data is already gone from our tables; surface
            # this rather than silently leaving an orphaned auth account,
            # but there's nothing left here worth rolling back.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Student record deleted, but the login account could not be "
                    f"removed automatically ({exc}). Remove it manually from "
                    "Supabase Authentication if needed."
                ),
            )

    return {"detail": "Student deleted"}


@router.post("/students", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def create_student(payload: StudentCreate, admin: dict = Depends(get_current_admin)):
    """Registers a single student, creating both their login and profile."""
    service_client = get_service_client()
    try:
        return _create_student_record(service_client, payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/students/import", response_model=StudentImportSummary)
async def import_students(file: UploadFile, admin: dict = Depends(get_current_admin)):
    """
    Bulk-creates students from an uploaded CSV file. Expected columns:
    registration_number, full_name, university_name, phone_number, email,
    password. Rows that fail (duplicate email, missing fields, and so on)
    are reported individually without stopping the rest of the import.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv files are supported for bulk import",
        )

    raw_bytes = await file.read()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is not valid UTF-8 encoded CSV",
        )

    reader = csv.DictReader(io.StringIO(text))
    missing_columns = [c for c in REQUIRED_IMPORT_COLUMNS if c not in (reader.fieldnames or [])]
    if missing_columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV is missing required columns: {', '.join(missing_columns)}",
        )

    service_client = get_service_client()
    results: list[StudentImportRowResult] = []
    created_count = 0

    for row_number, row in enumerate(reader, start=2):  # header is row 1
        registration_number = (row.get("registration_number") or "").strip()
        email = (row.get("email") or "").strip()
        try:
            student_payload = StudentCreate(
                registration_number=registration_number,
                full_name=(row.get("full_name") or "").strip(),
                university_name=(row.get("university_name") or "").strip(),
                phone_number=(row.get("phone_number") or "").strip(),
                email=email,
                password=(row.get("password") or "").strip(),
            )
            _create_student_record(service_client, student_payload)
            results.append(
                StudentImportRowResult(
                    row_number=row_number,
                    registration_number=registration_number,
                    email=email,
                    success=True,
                    message="Student created",
                )
            )
            created_count += 1
        except Exception as exc:
            results.append(
                StudentImportRowResult(
                    row_number=row_number,
                    registration_number=registration_number or None,
                    email=email or None,
                    success=False,
                    message=str(exc),
                )
            )

    return StudentImportSummary(
        total_rows=len(results),
        created=created_count,
        failed=len(results) - created_count,
        results=results,
    )


@router.get("/reports/export")
def export_report(
    date_from: Optional[date_cls] = Query(default=None),
    date_to: Optional[date_cls] = Query(default=None),
    admin: dict = Depends(get_current_admin),
):
    """
    Exports attendance records as a downloadable CSV file. Students with no
    attendance record on a given day within the range are included as
    absent, so the export reflects true attendance rather than only the
    days a student actually checked in.
    """
    service_client = get_service_client()

    effective_to = date_to or _today_local()
    effective_from = date_from or effective_to

    students_result = (
        service_client.table("students").select("*").eq("status", "active").execute()
    )
    students = students_result.data or []

    attendance_result = (
        service_client.table("attendance")
        .select("*")
        .gte("date", effective_from.isoformat())
        .lte("date", effective_to.isoformat())
        .execute()
    )
    attendance_by_key = {
        (row["student_id"], row["date"]): row for row in (attendance_result.data or [])
    }

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["registration_number", "full_name", "university_name", "date", "check_in_time", "status"]
    )

    current = effective_from
    while current <= effective_to:
        date_str = current.isoformat()
        for student in students:
            record = attendance_by_key.get((student["student_id"], date_str))
            writer.writerow(
                [
                    student.get("registration_number", ""),
                    student.get("full_name", ""),
                    student.get("university_name", ""),
                    date_str,
                    record.get("check_in_time", "") if record else "",
                    record.get("status", "") if record else "absent",
                ]
            )
        current = date_cls.fromordinal(current.toordinal() + 1)

    output.seek(0)
    filename = f"codinex-attendance-{effective_from.isoformat()}-to-{effective_to.isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
