from flask import Flask, Blueprint, request, jsonify
from flask_cors import CORS, cross_origin
from supabase import create_client, Client
from dotenv import load_dotenv
import os

feedback_bp = Blueprint("feedback_bp", __name__)

# app = Flask(__name__)

# # ✅ CORS setup
# CORS(
#     app,
#     resources={r"/api/*": {"origins": "http://localhost:3000"}},
#     supports_credentials=True,
# )

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# @app.after_request
# def after_request(response):
#     response.headers["Access-Control-Allow-Origin"] = "http://localhost:3000"
#     response.headers["Access-Control-Allow-Credentials"] = "true"
#     response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
#     response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
#     return response

# @app.route("/api/feedback_query", methods=["POST", "OPTIONS"])
@feedback_bp.route("/api/feedback_query", methods=["POST", "OPTIONS"])
def feedback_query():
    if request.method == "OPTIONS":
        return jsonify({"message": "CORS preflight OK"}), 200

    try:
        data = request.get_json()
        name = data.get("name")
        email = data.get("email")
        category = data.get("category")
        content = data.get("message")

        if not all([name, email, category, content]):
            return jsonify({"error": "All fields are required"}), 400

        response = supabase.rpc("get_user_id_by_email", {"user_email": email}).execute()
        # auth_user_id = response.data if response.data else None
        auth_user_id = None
        # Check if response.data is a list, not empty, and its first element is a dict with an 'id' key
        if response.data and isinstance(response.data, list) and len(response.data) > 0 and \
           isinstance(response.data[0], dict) and 'id' in response.data[0]:
            auth_user_id = response.data[0]['id'] # Extract ONLY the UUID string

        if not auth_user_id:
            return jsonify({"error": "Email not found in database"}), 404

        insert_response = supabase.table("forms").insert({
            "auth_user_id": auth_user_id,
            "name": name,
            "email": email,
            "category": category,
            "content": content
        }).execute()

        return jsonify({"success": True, "data": insert_response.data}), 201

    except Exception as e:
        print("Exception:", e)
        return jsonify({"error": str(e)}), 500
