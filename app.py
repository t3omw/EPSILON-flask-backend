from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from supabase import create_client, Client
from twilio.rest import Client as TwilioClient
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv
from OTP_call import send_otp, verify_otp
from supabase_call import (
    get_user_id_by_email, 
    create_auth_user, 
    update_auth_password, 
    update_participant_with_auth_id,
    get_participant_by_token, 
    get_participant_by_user_id
)
from feedback_logic import feedback_bp
import os
import time

app = Flask(__name__)
# CORS(app)
CORS(app, supports_credentials=True, origins=["http://localhost:3000"])

# Register Blueprints
app.register_blueprint(feedback_bp)
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")
TWILIO_VERIFY_SERVICE_SID = os.getenv("TWILIO_VERIFY_SERVICE_SID")

# Connect to Supabase (use service role for admin functions)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Connect to Twilio
twilio_client = TwilioClient(TWILIO_SID, TWILIO_AUTH_TOKEN)

# login attempts per email
login_attempts = {}
lockout_timestamps = {}
LOCKOUT_DURATION_SECONDS = 300  # 5 minutes

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    # --- Step 1: Check if the account is ALREADY locked ---
    if email in lockout_timestamps:
        time_since_lockout = time.time() - lockout_timestamps[email]
        if time_since_lockout < LOCKOUT_DURATION_SECONDS:
            remaining_lockout = int(LOCKOUT_DURATION_SECONDS - time_since_lockout)
            return jsonify({
                "status": "locked",
                "message": f"Account is locked. Please try again in {remaining_lockout} seconds."
            }), 429 # Using 429 for "Too Many Requests"
        else:
            # If the lockout has expired, clear the old data before proceeding
            del lockout_timestamps[email]
            login_attempts[email] = 0

    # --- Step 2: Check if the email exists in the database ---
    user_id = get_user_id_by_email(email)
    if not user_id:
        return jsonify({
            "status": "new_member",
            "message": "Email not found. Proceed to new member verification."
        }), 404

    # --- Step 3: Attempt to sign in with the password ---
    try:
        result = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        # If login is successful, clear any previous attempts and return the session
        login_attempts[email] = 0
        if email in lockout_timestamps: del lockout_timestamps[email] # Also clear old lockouts
        
        if result.session:
            return jsonify({
                "status": "successful",
                "message": "Login successful",
                "user_id": result.user.id,
                "access_token": result.session.access_token,
                "refresh_token": result.session.refresh_token,
            }), 200
        else:
            return jsonify({"status": "unsuccessful", "message": "Login failed: No session data."}), 401

    except Exception:
        # --- This block runs ONLY if the password was wrong ---
        login_attempts[email] = login_attempts.get(email, 0) + 1
        remaining = 3 - login_attempts[email]

        if remaining > 0:
            return jsonify({
                "status": "unsuccessful",
                "message": f"Wrong password. {remaining} attempt(s) left."
            }), 401
        else:
            # --- MODIFICATION: INSTEAD OF RESETTING, CREATE A TIMESTAMP ---
            # This is attempt #3, so we lock the account
            lockout_timestamps[email] = time.time() # Record the current time
            login_attempts[email] = 0 # Reset the counter for the next cycle
            
            return jsonify({
                "status": "locked",
                "message": "Too many failed login attempts. Account locked for 5 minutes."
            }), 429 # Or 401


# @app.route("/login", methods=["POST"])
# def login():
#     data = request.json
#     email = data.get("email")
#     password = data.get("password")

#     # Step 1: Check if email exists
#     user_id = get_user_id_by_email(email)

#     if not user_id:
#         return jsonify({
#             "status": "new_member",
#             "message": "Email not found. Proceed to new member verification."
#         }), 404

#     # Step 2: Try login
#     try:
#         result = supabase.auth.sign_in_with_password({
#             "email": email,
#             "password": password
#         })
#         login_attempts[email] = 0
    
#         if result.session:
#             return jsonify({
#                 "status": "successful",
#                 "message": "Login successful",
#                 "user_id": result.user.id,
#                 "access_token": result.session.access_token,
#                 "refresh_token": result.session.refresh_token,
#                 "expires_at": result.session.expires_at,
#                 "expires_in": result.session.expires_in,
#                 "token_type": result.session.token_type
#             }), 200
#         else:
#             # Fallback if session is unexpectedly not found (shouldn't happen on success)
#             return jsonify({
#                 "status": "unsuccessful",
#                 "message": "Login failed: No session data."
#             }), 401

#     except Exception:
#         login_attempts[email] = login_attempts.get(email, 0) + 1
#         remaining = 3 - login_attempts[email]

#         if remaining > 0:
#             return jsonify({
#                 "status": "unsuccessful",
#                 "message": f"Wrong password. {remaining} attempt(s) left."
#             }), 401
#         else:
#             login_attempts[email] = 0
#             # Redirect to forgot password route
#             # return forgot_password()
#             return jsonify({
#             "status": "locked",
#             "message": "Too many failed login attempts. Please reset your password."
#             }), 401 

@app.route("/create_account", methods=["POST"])
def create_account():
    data = request.json
    link = data.get("link")
    email = data.get("email")

    user_id = get_user_id_by_email(email)
    if user_id:
        return jsonify({"status": "failed", "message": "Account already exists"}), 400

    try:
        parsed_url = urlparse(link)
        query_params = parse_qs(parsed_url.query)
        token = query_params.get("token", [None])[0]
    except Exception:
        return jsonify({"status": "failed", "message": "Invalid link format"}), 400

    if not token:
        return jsonify({"status": "failed", "message": "Token not found in link"}), 400

    participant = get_participant_by_token(token)
    if len(participant.data) == 0:
        return jsonify({"status": "failed", "message": "Invalid token"}), 400

    phone_number = TWILIO_PHONE  # testing
    otp_response, status_code = send_otp(phone_number)
    if status_code == 200:
        # Add or override the 'status' key to be 'pending' for the frontend
        otp_response["status"] = "pending" # <--- ADDED/MODIFIED THIS LINE
        otp_response["email"] = email
        otp_response["token"] = token
        otp_response["phone_number"] = phone_number
    return jsonify(otp_response), status_code


@app.route("/verify_otp", methods=["POST"])
def verify_otp_route():
    data = request.json
    phone_number = data.get("phone_number")
    otp_code = data.get("otp")

    otp_response, status_code = verify_otp(phone_number, otp_code)
    return jsonify(otp_response), status_code

@app.route("/create_password", methods=["POST"])
def create_password():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    token = data.get("token")

    try:
        result = create_auth_user(email, password)
        user_id = result.user.id
        update_participant_with_auth_id(token, user_id)
        # return jsonify({"status": "success", "message": "Account created successfully"}), 201
        sign_in_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if sign_in_response.session:
            # Return the session data to the frontend so it can store the tokens
            return jsonify({
                "status": "success",
                "message": "Account created successfully. Logging in...",
                "user_id": sign_in_response.user.id,
                "access_token": sign_in_response.session.access_token,
                "refresh_token": sign_in_response.session.refresh_token,
                "expires_at": sign_in_response.session.expires_at,
                "expires_in": sign_in_response.session.expires_in,
                "token_type": sign_in_response.session.token_type
            }), 201
        else:
            raise Exception("Failed to establish user session after account creation.")
            # This case should ideally not happen if create_auth_user and sign_in_with_password work
    except Exception as e:
        return jsonify({"status": "failed", "message": str(e)}), 500

@app.route("/forgot_password", methods=["POST"])
def forgot_password():
    data = request.json
    email = data.get("email")
    user_id = get_user_id_by_email(email)
    # print(user_id)

    if not user_id:
        return jsonify({
            "status": "new_member",
            "message": "Email not found. Proceed to new member verification."
        }), 404
    
    # participant = get_participant_by_user_id(user_id)

    # phone_number = participant.data[0].get("phone")
    phone_number = TWILIO_PHONE  # testing
    otp_response, status_code = send_otp(phone_number)
    if status_code == 200:
        otp_response["status"] = "pending" 
        otp_response["email"] = email
        otp_response["phone_number"] = phone_number
    return jsonify(otp_response), status_code

@app.route("/renew_password", methods=["POST"])
def renew_password():
    data = request.json
    email = data.get("email")
    new_password = data.get("password")

    print(f"\n--- /renew_password Debug ---")
    print(f"Received email: {email}")
    print(f"Received password (first 3 chars): {new_password[:3]}...")

    try:
        user_id_data = get_user_id_by_email(email)
        print(f"1. Raw result from get_user_id_by_email (user_id_data): {user_id_data} (Type: {type(user_id_data)})")

        user_id = user_id_data.get('id') if isinstance(user_id_data, dict) else user_id_data # Handle case if RPC returns just UUID string directly
        print(f"2. Extracted user_id for update_auth_password: {user_id} (Type: {type(user_id)})")

        if not user_id:
            print("3. User ID not found or invalid from RPC.")
            return jsonify({"status": "failed", "message": "User not found for password renewal."}), 404

        update_auth_password(user_id, new_password)
        print(f"4. Password update initiated successfully for user_id: {user_id}")
        return jsonify({"status": "success", "message": "Password updated successfully"}), 200

    except Exception as e:
        return jsonify({"status": "failed", "message": str(e)}), 500
        import traceback
        traceback.print_exc() # Print full traceback for more context
        return jsonify({"status": "failed", "message": str(e)}), 500
if __name__ == "__main__":
    # print(get_user_id_by_email("test@example.com"))
    app.run(debug=True, port=5000)