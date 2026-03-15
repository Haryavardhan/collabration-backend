from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import User, MentorConnection


@jwt_required()
def request_connection(target_id):
    """User sends a connection request to another user."""
    student_id = int(get_jwt_identity())
    target_user  = User.query.get(target_id)

    if not target_user:
        return jsonify({"error": "User not found"}), 404
    if student_id == target_id:
        return jsonify({"error": "Cannot connect with yourself"}), 400

    # Check if already requested
    existing = MentorConnection.query.filter_by(
        student_id=student_id, mentor_id=target_id
    ).first()
    if existing:
        return jsonify({"status": existing.status, "message": "Request already exists", "connection": existing.to_dict()}), 200

    data = request.json or {}
    conn = MentorConnection(
        student_id=student_id,
        mentor_id=target_id,  # using mentor_id column as generic target_id
        message=data.get('message', ''),
        status='pending'
    )
    db.session.add(conn)
    db.session.commit()
    return jsonify({"status": "success", "connection": conn.to_dict()}), 201


@jwt_required()
def get_pending_requests():
    """User fetches all pending incoming connection requests."""
    user_id = int(get_jwt_identity())
    requests_list = MentorConnection.query.filter_by(mentor_id=user_id).order_by(MentorConnection.created_at.desc()).all()
    return jsonify({"requests": [r.to_dict() for r in requests_list]}), 200


@jwt_required()
def respond_to_request(connection_id):
    """User approves or rejects a connection request."""
    user_id = int(get_jwt_identity())
    conn = MentorConnection.query.get(connection_id)
    # The current user must be the target (mentor_id) of the request to approve/reject it.
    if not conn or conn.mentor_id != user_id:
        return jsonify({"error": "Not found or unauthorized"}), 404

    data = request.json or {}
    action = data.get('action')
    if action not in ('approved', 'rejected'):
        return jsonify({"error": "action must be 'approved' or 'rejected'"}), 400

    conn.status = action
    db.session.commit()
    return jsonify({"status": "success", "connection": conn.to_dict()}), 200


@jwt_required()
def get_my_connections():
    """Student fetches their own connection requests and status."""
    student_id = int(get_jwt_identity())
    conns = MentorConnection.query.filter_by(student_id=student_id).order_by(MentorConnection.created_at.desc()).all()
    return jsonify({"connections": [c.to_dict() for c in conns]}), 200


@jwt_required()
def get_connection_status(mentor_id):
    """Student checks their connection status with a specific mentor."""
    student_id = int(get_jwt_identity())
    conn = MentorConnection.query.filter_by(student_id=student_id, mentor_id=mentor_id).first()
    if not conn:
        return jsonify({"status": "none"}), 200
    return jsonify({"status": conn.status, "connection": conn.to_dict()}), 200
