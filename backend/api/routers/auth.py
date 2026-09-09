"""
Authentication endpoints.
"""
from fastapi import APIRouter, HTTPException, status

from models.schemas import LoginRequest, LoginResponse
from services.supabase_client import get_anon_client, get_service_client

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    """
    Authenticates a user against Supabase Auth, then resolves whether the
    account belongs to an admin or a student and returns the matching
    profile alongside the session tokens.
    """
    anon_client = get_anon_client()

    try:
        auth_response = anon_client.auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    session = getattr(auth_response, "session", None)
    user = getattr(auth_response, "user", None)
    if not session or not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    user_id = user.id

    try:
        service_client = get_service_client()

        admin_result = (
            service_client.table("admins").select("*").eq("user_id", user_id).limit(1).execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Signed in, but could not look up the account role. Check that "
                "SUPABASE_SERVICE_ROLE_KEY is set correctly and that the schema "
                f"migration has been run. ({exc})"
            ),
        )

    if admin_result.data:
        return LoginResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            role="admin",
            profile=admin_result.data[0],
        )

    student_result = (
        service_client.table("students").select("*").eq("user_id", user_id).limit(1).execute()
    )
    if student_result.data:
        return LoginResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            role="student",
            profile=student_result.data[0],
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="This account is not registered as a student or an admin",
    )
