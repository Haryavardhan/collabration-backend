# This is a mock notification service that logs to the console
# In a real app, you would use Twilio for SMS and an SMTP provider (like SendGrid or Gmail) for Email

import logging
import os
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def send_email(to_email: str, subject: str, message: str):
        # Run email in a separate thread to avoid blocking the main request
        threading.Thread(
            target=NotificationService._send_email_sync, 
            args=(to_email, subject, message),
            daemon=True
        ).start()

    @staticmethod
    def _send_email_sync(to_email: str, subject: str, message: str):
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        smtp_user = os.getenv("SMTP_USERNAME")
        smtp_pass = os.getenv("SMTP_PASSWORD")

        # Fallback to mock if no credentials are provided
        if not smtp_user or not smtp_pass:
            print("\n" + "="*50)
            print("⚠️ WARNING: Real email not sent because SMTP_USERNAME or SMTP_PASSWORD is not set in .env")
            print(f"📧 MOCK EMAIL FALLBACK")
            print(f"To:      {to_email}")
            print(f"Subject: {subject}")
            print("-" * 50)
            print(message)
            print("="*50 + "\n")
            logger.info(f"Simulated email sent to {to_email} (missing SMTP config)")
            return

        try:
            # Create a multipart message
            msg = MIMEMultipart()
            msg['From'] = str(smtp_user)
            msg['To'] = to_email
            msg['Subject'] = subject

            # Add body to email
            msg.attach(MIMEText(message, 'plain'))

            # Setup the SMTP server
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(str(smtp_user), str(smtp_pass))
            
            # Send the email
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Real email successfully sent to {to_email}")
            print(f"✅ Real email successfully sent to {to_email}")
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            print(f"❌ Failed to send email to {to_email}: {str(e)}")

    @staticmethod
    def send_sms(phone_number: str, message: str):
        # Run SMS in a separate thread
        threading.Thread(
            target=NotificationService._send_sms_sync,
            args=(phone_number, message),
            daemon=True
        ).start()

    @staticmethod
    def _send_sms_sync(phone_number: str, message: str):
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        twilio_from = os.getenv("TWILIO_PHONE_NUMBER")

        # Validate phone number is real before attempting
        if not phone_number or phone_number in ("+0000000000", "+1234567890"):
            logger.info(f"Skipping SMS — no real phone number set for recipient.")
            return

        # Fallback to mock if Twilio credentials missing
        if not twilio_sid or not twilio_token or twilio_sid == "your-twilio-account-sid":
            print("\n" + "="*50)
            print("⚠️  MOCK SMS (Twilio not configured)")
            print(f"📱 To: {phone_number}")
            print(f"   {message}")
            print("="*50 + "\n")
            logger.info(f"Simulated SMS to {phone_number} (missing Twilio config)")
            return

        try:
            from twilio.rest import Client
            client = Client(twilio_sid, twilio_token)
            client.messages.create(
                body=message,
                from_=twilio_from,
                to=phone_number
            )
            logger.info(f"✅ Real SMS sent to {phone_number}")
            print(f"✅ Real SMS sent to {phone_number}")
        except Exception as e:
            logger.error(f"❌ Failed to send SMS to {phone_number}: {str(e)}")
            print(f"❌ Failed to send SMS to {phone_number}: {str(e)}")

