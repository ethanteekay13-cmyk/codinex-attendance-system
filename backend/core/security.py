"""
Security utilities.

Two independent mechanisms live here:

1. A stateless, time-boxed HMAC token used to defeat "photo of the QR code"
   style cheating. The token is derived purely from a shared secret and the
   current 15 second time window, so it never has to be looked up in a
   database to be verified, and a screenshot of it is only useful for one
   window (plus a small tolerance for scan/network latency).

2. Supabase access token verification. Rather than decoding and verifying
   the JWT locally (which requires knowing whether a given project signs
   tokens with the legacy shared secret or a newer asymmetric key, and
   Supabase's own JWKS endpoint has known rough edges around API-key
   requirements), this asks Supabase's Auth server to verify the token
   directly via GET /auth/v1/user. This costs one extra network call per
   authenticated request, which is a fine trade-off at this system's scale
   (a few hundred students), and it keeps working no matter how a given
   project is configured to sign tokens, now or in the future.
"""
import hmac
import hashlib
import time
from typing import Optional, Tuple

from fastapi import HTTPException, status

from core.config import settings
from services.supabase_client import get_anon_client


def _window_index(timestamp: Optional[float] = None) -> int:
    ts = timestamp if timestamp is not None else time.time()
    return int(ts // settings.QR_TOKEN_WINDOW_SECONDS)


def _derive_token(window_index: int) -> str:
    message = str(window_index).encode("utf-8")
    digest = hmac.new(
        settings.QR_HMAC_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()
    return digest[: settings.QR_TOKEN_LENGTH].upper()


def get_current_qr_token() -> Tuple[str, int, int]:
    """
    Returns a tuple of (token, window_index, seconds_remaining_in_window).
    Intended to be polled by the kiosk display roughly once per second.
    """
    now = time.time()
    window = _window_index(now)
    token = _derive_token(window)
    elapsed_in_window = now - (window * settings.QR_TOKEN_WINDOW_SECONDS)
    seconds_remaining = int(settings.QR_TOKEN_WINDOW_SECONDS - elapsed_in_window)
    return token, window, max(seconds_remaining, 0)


def verify_qr_token(token: str) -> bool:
    """
    Validates a scanned token against the current window and a small
    tolerance window on either side, to account for the delay between the
    kiosk rendering a token and the student's check-in request arriving.
    """
    if not token:
        return False
    now = time.time()
    current_window = _window_index(now)
    normalized = token.strip().upper()
    tolerance = settings.QR_TOKEN_TOLERANCE_WINDOWS
    for offset in range(-tolerance, tolerance + 1):
        candidate = _derive_token(current_window + offset)
        if hmac.compare_digest(candidate, normalized):
            return True
    return False


def verify_supabase_access_token(token: str) -> str:
    """
    Verifies a Supabase-issued access token by asking Supabase's own Auth
    server to check it, instead of verifying the JWT signature locally.
    Returns the authenticated user's Supabase user id.
    """
    anon_client = get_anon_client()
    try:
        response = anon_client.auth.get_user(token)
    except Exception as exc:
        print(f"Token verification failed: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session, please log in again",
        )

    if not response or not response.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session, please log in again",
        )

    return response.user.id


def extract_bearer_token(authorization: Optional[str]) -> str:
    """Pulls the raw token out of an "Authorization: Bearer <token>" header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    return authorization.split(" ", 1)[1].strip()
