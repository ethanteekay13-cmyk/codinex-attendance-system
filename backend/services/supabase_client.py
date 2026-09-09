"""
Supabase client factory.

Two clients are exposed:

- get_anon_client(): used only to authenticate end users against Supabase
  Auth (sign in with email and password). It never touches application
  tables directly.
- get_service_client(): uses the Supabase service role key and bypasses
  Row Level Security. Used for all privileged server-side reads/writes
  (students, attendance, admins, qr_sessions). This key must never be
  exposed to the frontend.
"""
from supabase import create_client, Client

from core.config import settings

_anon_client: Client = None
_service_client: Client = None


def get_anon_client() -> Client:
    global _anon_client
    if _anon_client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_ANON_KEY must be set to create the anon client"
            )
        _anon_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    return _anon_client


def get_service_client() -> Client:
    global _service_client
    if _service_client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set to create the service client"
            )
        _service_client = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
        )
    return _service_client
