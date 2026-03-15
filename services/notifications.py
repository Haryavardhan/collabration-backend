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

        if not smtp_user or not smtp_pass:
            print(f"\n📧 MOCK EMAIL: {to_email} | {subject}")
            return

        try:
            msg = MIMEMultipart()
            msg['From'] = str(smtp_user)
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(message, 'plain'))

            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(str(smtp_user), str(smtp_pass))
            server.send_message(msg)
            server.quit()
            logger.info(f"Email sent to {to_email}")
        except Exception as e:
            logger.error(f"Email error: {str(e)}")

    @staticmethod
    def send_sms(phone_number: str, message: str):
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

        if not phone_number or phone_number in ("+0000000000", "+1234567890"):
            return

        if not twilio_sid or not twilio_token or twilio_sid == "your-twilio-account-sid":
            print(f"\n📱 MOCK SMS: {phone_number} | {message}")
            return

        try:
            from twilio.rest import Client
            client = Client(twilio_sid, twilio_token)
            client.messages.create(body=message, from_=twilio_from, to=phone_number)
            logger.info(f"SMS sent to {phone_number}")
        except Exception as e:
            logger.error(f"SMS error: {str(e)}")

    @staticmethod
    def send_bulk_notifications(recipients, subject, message):
        """
        Sends notifications to a list of recipients in a single background thread.
        recipients: list of dicts like [{"email": "...", "phone": "...", "name": "..."}]
        """
        threading.Thread(
            target=NotificationService._send_bulk_sync,
            args=(recipients, subject, message),
            daemon=True
        ).start()

    @staticmethod
    def _send_bulk_sync(recipients, subject, message):
        print(f">>> NotificationService: Starting bulk notification for {len(recipients)} recipients...")
        for r in recipients:
            email = r.get('email')
            phone = r.get('phone')
            name = r.get('name', 'User')
            
            personalized_msg = message.replace("{name}", name)
            
            if email:
                NotificationService._send_email_sync(email, subject, personalized_msg)
            if phone:
                NotificationService._send_sms_sync(phone, personalized_msg)
        
        print(f">>> NotificationService: Bulk notification finished.")
