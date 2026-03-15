import razorpay
import hmac
import hashlib
import os
from datetime import datetime, timedelta
from flask import jsonify, request
import requests
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import User, MentorConnection, Payment

def get_razorpay_client():
    key_id     = os.getenv('RAZORPAY_KEY_ID', '')
    key_secret = os.getenv('RAZORPAY_KEY_SECRET', '')
    return razorpay.Client(auth=(key_id, key_secret))

@jwt_required()
def create_razorpay_account():
    """
    Mentor calls this to create a linked Razorpay Route account.
    """
    mentor_id = int(get_jwt_identity())
    mentor = User.query.get(mentor_id)
    
    if not mentor or mentor.role != 'mentor':
        return jsonify({"error": "Only mentors can connect bank accounts"}), 403
        
    if mentor.razorpay_account_id:
        return jsonify({"message": "Account already connected", "account_id": mentor.razorpay_account_id}), 200

    # In a real production setup, you would direct the user to a Razorpay hosted onboarding URL,
    # or collect bank details securely and use the Accounts API.
    # For this simplified integration, we will create a 'route' account via API
    # Note: Requires correct API keys and Razorpay Route activated.
    
    key_id = os.getenv('RAZORPAY_KEY_ID', '')
    key_secret = os.getenv('RAZORPAY_KEY_SECRET', '')
    
    # Razorpay v2 Accounts API endpoint
    url = "https://api.razorpay.com/v2/accounts"
    
    payload = {
        "email": mentor.email,
        "phone": mentor.phone_number or "9999999999",
        "legal_business_name": mentor.name,
        "business_type": "individual",
        "profile": {
            "category": "education",
            "subcategory": "other_educational_services",
            "addresses": {
                "registered": {
                    "street1": "Mentor Street",
                    "city": "Bengaluru",
                    "state": "KA",
                    "postal_code": "560001",
                    "country": "IN"
                }
            }
        }
    }
    
    try:
        response = requests.post(url, json=payload, auth=(key_id, key_secret))
        response_data = response.json()
        
        if response.status_code in [200, 201] and 'id' in response_data:
            mentor.razorpay_account_id = response_data['id']
            mentor.razorpay_account_status = 'active' # normally 'created' then verify KYC, using 'active' for simplicity
            db.session.commit()
            return jsonify({
                "message": "Account created successfully",
                "account_id": mentor.razorpay_account_id,
                "status": mentor.razorpay_account_status
            }), 200
        else:
            return jsonify({
                "error": "Failed to create Razorpay account",
                "details": response_data
            }), 400
            
    except Exception as e:
        return jsonify({"error": "Server error while connecting to Razorpay", "details": str(e)}), 500


@jwt_required()
def create_order(mentor_id):
    """
    Student calls this to create a Razorpay order before opening the checkout.
    Body: { "minutes": <float> }
    """
    student_id = int(get_jwt_identity())

    # Validate mentor
    mentor = User.query.get(mentor_id)
    if not mentor or mentor.role != 'mentor':
        return jsonify({"error": "Mentor not found"}), 404

    # Validate connection is approved
    conn = MentorConnection.query.filter_by(
        student_id=student_id, mentor_id=mentor_id, status='approved'
    ).first()
    if not conn:
        return jsonify({"error": "You must have an approved connection with this mentor to pay"}), 403

    if not mentor.charge_per_min:
        return jsonify({"error": "This mentor has not set a rate"}), 400

    data = request.json or {}
    minutes = float(data.get('minutes', 0))
    if minutes <= 0:
        return jsonify({"error": "minutes must be greater than 0"}), 400

    # Calculate amount
    rate = mentor.charge_per_min
    discount = mentor.discount_percent or 0
    amount_inr = rate * minutes * (1 - discount / 100)
    amount_paise = int(round(amount_inr * 100))  # Razorpay needs amount in paise

    if amount_paise < 100:  # Razorpay minimum is ₹1
        return jsonify({"error": "Amount too small (minimum ₹1)"}), 400

    client = get_razorpay_client()
    
    # Setup transferring
    platform_fee_percent = 10.0 # 10% platform commission
    mentor_share = amount_paise * (1 - (platform_fee_percent / 100))
    
    order_data = {
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": 1,
        "notes": {
            "student_id": str(student_id),
            "mentor_id": str(mentor_id),
            "minutes": str(minutes),
        }
    }
    
    # If mentor has a connected account, split the payment
    if mentor.razorpay_account_id:
        order_data["transfers"] = [
            {
                "account": mentor.razorpay_account_id,
                "amount": int(mentor_share),
                "currency": "INR",
                "notes": {
                    "reason": f"Mentorship session payout: {minutes} mins"
                },
                "on_hold": 1, # Escrow: Hold funds until session is released
                "on_hold_until": int((datetime.utcnow() + timedelta(days=7)).timestamp()) # Hold up to 7 days
            }
        ]
        
    rz_order = client.order.create(data=order_data)

    # Save pending payment record
    payment = Payment(
        student_id=student_id,
        mentor_id=mentor_id,
        minutes_booked=minutes,
        amount_paise=amount_paise,
        razorpay_order_id=rz_order['id'],
        status='created'
    )
    db.session.add(payment)
    db.session.commit()

    return jsonify({
        "order_id": rz_order['id'],
        "amount_paise": amount_paise,
        "amount_inr": amount_inr,
        "currency": "INR",
        "key_id": os.getenv('RAZORPAY_KEY_ID', ''),
        "mentor_name": mentor.name,
        "payment_db_id": payment.id,
    }), 201


@jwt_required()
def verify_payment():
    """
    After Razorpay checkout succeeds on frontend, this verifies the signature
    and marks the payment as paid.
    Body: {
        "razorpay_order_id": ...,
        "razorpay_payment_id": ...,
        "razorpay_signature": ...,
        "payment_db_id": ...
    }
    """
    student_id = int(get_jwt_identity())
    data = request.json or {}

    order_id   = data.get('razorpay_order_id')
    payment_id = data.get('razorpay_payment_id')
    signature  = data.get('razorpay_signature')
    db_id      = data.get('payment_db_id')

    if not all([order_id, payment_id, signature, db_id]):
        return jsonify({"error": "Missing payment details"}), 400

    # Verify signature
    key_secret = os.getenv('RAZORPAY_KEY_SECRET', '').encode('utf-8')
    msg = f"{order_id}|{payment_id}".encode('utf-8')
    expected = hmac.new(key_secret, msg, hashlib.sha256).hexdigest()

    payment = Payment.query.get(db_id)
    if not payment or payment.student_id != student_id:
        return jsonify({"error": "Payment record not found"}), 404

    if expected != signature:
        payment.status = 'failed'
        db.session.commit()
        return jsonify({"error": "Payment signature verification failed"}), 400

    payment.razorpay_payment_id = payment_id
    payment.razorpay_signature  = signature
    payment.status = 'paid'
    
    # If there's a mentor account, find the transfer ID related to this payment
    if payment.mentor.razorpay_account_id:
        try:
            client = get_razorpay_client()
            # We fetch transfers for this specific payment
            transfers = client.payment.transfers(payment_id)
            if transfers and transfers.get('count', 0) > 0:
                # Assuming one transfer (to the mentor)
                payment.razorpay_transfer_id = transfers['items'][0]['id']
        except Exception as e:
            print(f"Error fetching transfer ID: {e}")
            
    db.session.commit()

    return jsonify({"status": "success", "payment": payment.to_dict()}), 200

@jwt_required()
def release_payment(payment_id):
    """
    Called after a session is successfully completed to release funds to the mentor.
    Only the student who paid or an admin should be able to call this.
    """
    student_id = int(get_jwt_identity())
    payment = Payment.query.get(payment_id)
    
    if not payment:
        return jsonify({"error": "Payment not found"}), 404
        
    if payment.student_id != student_id:
        return jsonify({"error": "Unauthorized"}), 403
        
    if payment.status != 'paid':
        return jsonify({"error": "Payment is not in a releasable state"}), 400
        
    if not payment.razorpay_transfer_id:
        # If there's no transfer ID, either it wasn't split, or error
        payment.status = 'settled'
        db.session.commit()
        return jsonify({"message": "Payment marked completed. No external transfer release needed."}), 200
        
    try:
        client = get_razorpay_client()
        # Patch the transfer to remove the hold
        response = client.transfer.edit(payment.razorpay_transfer_id, {"on_hold": 0})
        
        payment.status = 'settled'
        db.session.commit()
        
        return jsonify({"message": "Funds successfully released to mentor", "details": response}), 200
    except Exception as e:
        return jsonify({"error": "Failed to release funds", "details": str(e)}), 500

def razorpay_webhook():
    """
    Listens to asynchronous events from Razorpay (e.g. payment.captured, transfer.processed).
    """
    webhook_secret = os.getenv('RAZORPAY_WEBHOOK_SECRET', '')
    webhook_signature = request.headers.get('X-Razorpay-Signature')
    payload = request.get_data(as_text=True)
    
    # For local testing without a proper webhook secret, we bypass verification if secret is empty
    if webhook_secret and webhook_signature:
        try:
            get_razorpay_client().utility.verify_webhook_signature(payload, webhook_signature, webhook_secret)
        except razorpay.errors.SignatureVerificationError:
            return jsonify({"error": "Invalid signature"}), 400
            
    data = request.json
    if not data:
        return jsonify({"error": "No data"}), 400
        
    event = data.get('event')
    
    if event == 'payment.captured':
        payment_entity = data['payload']['payment']['entity']
        order_id = payment_entity.get('order_id')
        payment_id = payment_entity.get('id')
        
        # We can find the payment by order
        payment = Payment.query.filter_by(razorpay_order_id=order_id).first()
        if payment and payment.status == 'created':
            payment.status = 'paid'
            payment.razorpay_payment_id = payment_id
            db.session.commit()
            
    elif event == 'transfer.processed':
        transfer_entity = data['payload']['transfer']['entity']
        transfer_id = transfer_entity.get('id')
        
        payment = Payment.query.filter_by(razorpay_transfer_id=transfer_id).first()
        if payment and payment.status == 'paid':
            payment.status = 'settled'
            db.session.commit()
            
    return jsonify({"status": "ok"}), 200


@jwt_required()
def get_payment_history():
    """Returns payments for the logged-in user (as student or mentor)."""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.role == 'mentor':
        payments = Payment.query.filter_by(mentor_id=user_id).order_by(Payment.created_at.desc()).all()
    else:
        payments = Payment.query.filter_by(student_id=user_id).order_by(Payment.created_at.desc()).all()

    return jsonify({"payments": [p.to_dict() for p in payments]}), 200
