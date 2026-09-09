"""
Shared attendance statistics helpers.

Centralizes the business-day/percentage math so the student's own
"/students/me/history" endpoint and the admin's per-student and
list-of-students endpoints all compute attendance percentage identically,
rather than three slightly different copies drifting apart over time.
"""
from datetime import date as date_cls, datetime
from typing import Dict, List
from zoneinfo import ZoneInfo

from core.config import settings


def today_local() -> date_cls:
    return datetime.now(ZoneInfo(settings.CODINEX_TIMEZONE)).date()


def count_business_days(start: date_cls, end: date_cls) -> int:
    """Counts Monday-to-Friday business days between two dates, inclusive."""
    if end < start:
        return 0
    total = 0
    current = start
    while current <= end:
        if current.weekday() < 5:  # Monday=0 ... Sunday=6
            total += 1
        current = date_cls.fromordinal(current.toordinal() + 1)
    return total


def parse_registration_date(created_at_raw, fallback: date_cls) -> date_cls:
    if not created_at_raw:
        return fallback
    try:
        return datetime.fromisoformat(str(created_at_raw).replace("Z", "+00:00")).date()
    except ValueError:
        return fallback


def compute_percentage(present_count: int, late_count: int, expected_days: int) -> float:
    if expected_days <= 0:
        return 0.0
    return round(((present_count + late_count) / expected_days) * 100, 2)


def summarize_records(records: List[dict], created_at_raw) -> dict:
    """
    Given a student's raw attendance rows and their registration
    timestamp, returns present/late/absent counts and the attendance
    percentage, all computed against expected business days since
    registration.
    """
    today = today_local()
    registration_date = parse_registration_date(created_at_raw, today)

    total_present = sum(1 for r in records if r.get("status") == "present")
    total_late = sum(1 for r in records if r.get("status") == "late")

    expected_days = count_business_days(registration_date, today)
    total_absent = max(expected_days - (total_present + total_late), 0)
    percentage = compute_percentage(total_present, total_late, expected_days)

    return {
        "total_present": total_present,
        "total_late": total_late,
        "total_absent": total_absent,
        "attendance_percentage": percentage,
    }


def bulk_percentages_by_student(
    students: List[dict], attendance_rows: List[dict]
) -> Dict[str, float]:
    """
    Computes attendance percentage for many students at once from a single
    pre-fetched list of attendance rows (grouped in Python), instead of
    running one query per student - important once there are 100+
    students on the admin dashboard's list view.
    """
    rows_by_student: Dict[str, List[dict]] = {}
    for row in attendance_rows:
        rows_by_student.setdefault(row["student_id"], []).append(row)

    result: Dict[str, float] = {}
    for student in students:
        student_rows = rows_by_student.get(student["student_id"], [])
        summary = summarize_records(student_rows, student.get("created_at"))
        result[student["student_id"]] = summary["attendance_percentage"]
    return result
