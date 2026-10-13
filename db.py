from supabase import create_client, Client
from config import settings

# Anon client — for public/buyer operations, respects RLS
# Never uses the service-role key, safe to call from any context
_anon_client: Client | None = None

# Service-role client — for privileged server-side operations only
# SUPABASE_SERVICE_ROLE_KEY is accessed exclusively in this file
_service_client: Client | None = None


def get_anon_client() -> Client:
    """Return the module-level Supabase anon client (singleton).

    Uses the anon key so all operations respect Row Level Security policies.
    Suitable for public and buyer-facing operations.
    """
    global _anon_client
    if _anon_client is None:
        _anon_client = create_client(settings.supabase_url, settings.supabase_anon_key)
    return _anon_client


def get_service_client() -> Client:
    """Return the module-level Supabase service-role client (singleton).

    Uses the service-role key which bypasses RLS — use only for privileged
    server-side operations (order writes, storage uploads, audit logs).
    This function is the ONLY place SUPABASE_SERVICE_ROLE_KEY is referenced.
    Never call this from a router directly; go through a service function.
    """
    global _service_client
    if _service_client is None:
        _service_client = create_client(
            settings.supabase_url, settings.supabase_service_role_key
        )
    return _service_client
