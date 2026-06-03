from supabase import create_client, Client
from slate.config import settings


def get_client() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
