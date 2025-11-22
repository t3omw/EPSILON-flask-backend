from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")
TWILIO_VERIFY_SERVICE_SID = os.getenv("TWILIO_VERIFY_SERVICE_SID")

# Connect to Supabase (use service role for admin functions)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# def get_user_id_by_email(email: str):
#     """Get user_id from email using Supabase RPC."""
#     # response = supabase.rpc("get_user_id_by_email", {"email": email}).execute()
#     user = supabase.auth.get_user()
#     user_id = user.user.id  # Supabase Auth UUID
#     response = supabase.table('participants').select('id').eq('auth_user_id', user_id).execute()
#     return response.data if response.data else None

def get_user_id_by_email(email: str):
    """Get user_id from email using Supabase RPC."""
    response = supabase.rpc("get_user_id_by_email", {"user_email": email}).execute()

    if response.data:
        return response.data[0]  # Should return the UUID
    else:
        return None


def get_participant_id_from_auth_id(auth_user_id: str):
    """Map an auth_user_id (UUID) to participant.id."""
    response = supabase.table("participants").select("id").eq("auth_user_id", auth_user_id).execute()
    return response.data[0]["id"] if response.data else None

def create_auth_user(email: str, password: str):
    """Create user in Supabase Auth."""
    return supabase.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True
    })

def update_auth_password(user_id: str, new_password: str):
    """Update password in Supabase Auth."""
    return supabase.auth.admin.update_user_by_id(
        user_id,
        {"password": new_password}
    )

def get_participant_by_token(token: str):
    """Fetch participant record by token."""
    return supabase.table("participants").select("*").eq("id", token).execute()


def update_participant_with_auth_id(token: str, user_id: str):
    """Update participant with new auth_user_id."""
    return supabase.table("participants").update({
        "auth_user_id": user_id
    }).eq("id", token).execute()


def get_participant_by_user_id(user_id: str):
    """Fetch participant record by auth_user_id."""
    return supabase.table("participants").select("*").eq("auth_user_id", user_id).execute()