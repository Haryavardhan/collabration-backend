from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, decode_token

from extensions import db
from models import User
from services.notifications import NotificationService

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    
    if User.query.filter_by(email=data.get('email')).first():
        return jsonify({"msg": "Email already exists"}), 400
        
    hashed_password = generate_password_hash(data.get('password'))
    new_user = User(
        email=data.get('email'),
        password=hashed_password,
        name=data.get('name'),
        role=data.get('role', 'student')
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({"msg": "User created successfully"}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data.get('email')).first()
    
    if not user or not check_password_hash(user.password, data.get('password')):
        return jsonify({"msg": "Bad email or password"}), 401
        
    access_token = create_access_token(identity=str(user.id))
    return jsonify(access_token=access_token, user=user.to_dict()), 200

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.json
    email = data.get('email')
    
    user = User.query.filter_by(email=email).first()
    if not user:
        # Avoid user enumeration by returning a generic success message
        return jsonify({"msg": "If your email is registered, you will receive a password reset link."}), 200
        
    # Generate a time-limited token specifically for password reset
    import datetime
    reset_token = create_access_token(identity=str(user.id), expires_delta=datetime.timedelta(minutes=15))
    
    # In a real app, this would be your frontend URL
    reset_link = f"http://localhost:5173/reset-password?token={reset_token}"
    
    NotificationService.send_email(
        to_email=user.email,
        subject="CollabSphere Password Reset",
        message=f"Hello {user.name},\n\nYou requested a password reset. Click the link below to set a new password. This link will expire in 15 minutes.\n\n{reset_link}\n\nIf you did not request this, please ignore this email."
    )
    
    return jsonify({"msg": "If your email is registered, you will receive a password reset link."}), 200

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    token = data.get('token')
    new_password = data.get('password')
    
    if not token or not new_password:
        return jsonify({"msg": "Token and new password are required"}), 400
        
    try:
        # Decode token to get user ID
        decoded = decode_token(token)
        user_id = decoded.get('sub')
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({"msg": "User not found"}), 404
            
        user.password = generate_password_hash(new_password)
        db.session.commit()
        
        return jsonify({"msg": "Password has been successfully reset. You can now login."}), 200
    except Exception as e:
        return jsonify({"msg": "Invalid or expired reset token"}), 400
