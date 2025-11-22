from twilio.rest import Client as TwilioClient
import os
from dotenv import load_dotenv

load_dotenv()

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")
TWILIO_VERIFY_SERVICE_SID = os.getenv("TWILIO_VERIFY_SERVICE_SID")

twilio_client = TwilioClient(TWILIO_SID, TWILIO_AUTH_TOKEN)

def send_otp(phone_number: str):
    """
    Send OTP using Twilio Verify API
    """
    try:
        verification = twilio_client.verify.v2.services(TWILIO_VERIFY_SERVICE_SID).verifications.create(
            to=phone_number,
            channel="sms"
        )
        return {
            "status": "otp_sent",
            "message": f"OTP sent to {phone_number[-4:].rjust(len(phone_number), '*')}",
            "phone_number": phone_number
        }, 200
    except Exception as e:
        return {
            "status": "failed",
            "message": f"Error sending OTP: {str(e)}"
        }, 500

def verify_otp(phone_number: str, otp_code: str):
    """
    Verify OTP using Twilio Verify API
    """
    try:
        verification_check = twilio_client.verify.v2.services(TWILIO_VERIFY_SERVICE_SID).verification_checks.create(
            to=phone_number,
            code=otp_code
        )

        if verification_check.status == "approved":
            return {
                # "status": "approved",
                "status": "success",
                "message": "Proceed to create password"
            }, 201
        else:
            return {
                "status": "failed",
                "message": "Invalid OTP"
            }, 400

    except Exception as e:
        return {
            "status": "failed",
            "message": str(e)
        }, 500