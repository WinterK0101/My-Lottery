import os
from supabase import create_client, Client

# Supabase configuration
# Use service role key for backend operations (bypasses RLS)
SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Initialize Supabase client
supabase_client: Client | None = None


def get_supabase_client() -> Client:
    """Get Supabase client instance with service role key (bypasses RLS)."""
    global supabase_client
    if supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError(
                "Missing Supabase credentials. Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
            )
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return supabase_client
