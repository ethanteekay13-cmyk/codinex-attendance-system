"""
Pydantic models for request validation and response serialization.
"""
from datetime import datetime, date
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


# --- Auth ---

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    role: str
    profile: dict


# --- Students ---

class StudentBase(BaseModel):
    registration_number: str
    full_name: str
    university_name: str
    phone_number: str
    email: EmailStr


class StudentCreate(StudentBase):
    password: str = Field(min_length=8, description="Initial password for the student account")


class StudentOut(StudentBase):
    student_id: str
    photo_url: Optional[str] = None
    status: str
    created_at: datetime
    attendance_percentage: float = 0.0


class StudentImportRowResult(BaseModel):
    row_number: int
    registration_number: Optional[str] = None
    email: Optional[str] = None
    success: bool
    message: str


class StudentImportSummary(BaseModel):
    total_rows: int
    created: int
    failed: int
    results: List[StudentImportRowResult]


# --- Attendance ---

class QRTokenResponse(BaseModel):
    token: str
    window_seconds: int
    seconds_remaining: int
    server_time: datetime


class AttendanceCheckInRequest(BaseModel):
    token: str = Field(min_length=1, description="Current QR token displayed on the kiosk")


class AttendanceOut(BaseModel):
    attendance_id: str
    student_id: str
    date: date
    check_in_time: datetime
    status: str
    device_info: Optional[str] = None
    ip_address: Optional[str] = None
    via_wifi_override: bool = False


class AttendanceHistoryResponse(BaseModel):
    records: List[AttendanceOut]
    total_present: int
    total_late: int
    total_absent: int
    attendance_percentage: float


# --- Admin ---

class AdminOut(BaseModel):
    admin_id: str
    full_name: str
    role: str


class DashboardSummary(BaseModel):
    report_date: date
    present: int
    late: int
    absent: int
    total_students: int


class AttendanceReportRow(BaseModel):
    registration_number: str
    full_name: str
    university_name: str
    date: date
    check_in_time: Optional[datetime] = None
    status: str


# --- System settings ---

class SystemSettingsOut(BaseModel):
    office_ips: List[str]
    wifi_override_enabled: bool
    wifi_override_expires_at: Optional[datetime] = None
    wifi_override_enabled_by: Optional[str] = None
    wifi_override_enabled_at: Optional[datetime] = None
    present_cutoff_time: str
    late_cutoff_time: str


class UpdateOfficeIpsRequest(BaseModel):
    office_ips: List[str] = Field(
        description="Full replacement list of allowed office IP addresses"
    )


class UpdateCutoffTimesRequest(BaseModel):
    present_cutoff_time: str = Field(description="24-hour HH:MM, e.g. '09:00'")
    late_cutoff_time: str = Field(description="24-hour HH:MM, e.g. '09:30'")


class TodayAttendanceRow(BaseModel):
    attendance_id: str
    full_name: str
    registration_number: str
    check_in_time: datetime
    status: str
    via_wifi_override: bool


class StudentDetailResponse(BaseModel):
    student: StudentOut
    history: AttendanceHistoryResponse


# --- Password change ---

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)
