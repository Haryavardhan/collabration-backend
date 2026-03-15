from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import User


@jwt_required()
def get_user_profile(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.to_dict()), 200


@jwt_required()
def update_user_profile(user_id):
    current_user_id = get_jwt_identity()

    # Only allow the user to edit their own profile
    if str(current_user_id) != str(user_id):
        return jsonify({"error": "Unauthorized"}), 403

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.json

    if 'name' in data and data['name'].strip():
        user.name = data['name'].strip()

    if 'phone_number' in data:
        user.phone_number = data['phone_number'].strip() or None

    if 'interests' in data:
        interests = data['interests']
        if isinstance(interests, list):
            user.interests = ','.join([i.strip() for i in interests if i.strip()])
        else:
            user.interests = interests.strip()

    if 'bio' in data:
        user.bio = data['bio'].strip() or None

    if 'charge_per_min' in data:
        try:
            user.charge_per_min = float(data['charge_per_min']) if data['charge_per_min'] not in (None, '') else None
        except (ValueError, TypeError):
            pass

    if 'discount_percent' in data:
        try:
            user.discount_percent = float(data['discount_percent']) if data['discount_percent'] not in (None, '') else None
        except (ValueError, TypeError):
            pass

    db.session.commit()
    return jsonify({"status": "success", "message": "Profile updated successfully", "user": user.to_dict()}), 200


@jwt_required()
def get_mentors():
    """Return all users with role=mentor for the Find a Mentor tab."""
    mentors = User.query.filter_by(role='mentor').all()
    return jsonify({"mentors": [m.to_dict() for m in mentors]}), 200


@jwt_required()
def get_suggested_mentors_for_room(room_id):
    """Return mentors ranked by keyword overlap with the room's subject/description."""
    from models import Room
    room = db.session.get(Room, room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404

    # Build room keyword set from subject + description
    room_text = f"{room.subject} {room.description or ''}".lower()
    # Split into words, remove short/common words
    stop_words = {'a','an','the','and','or','for','in','on','of','to','is','are','with','this','that','by','as','at','be','it'}
    room_keywords = set(w.strip('.,!?') for w in room_text.split() if len(w) > 2 and w not in stop_words)

    # Gather current member IDs to exclude them from suggestions
    from models import RoomMember
    existing_member_ids = [rm.user_id for rm in RoomMember.query.filter_by(room_id=room_id).all()]

    mentors = User.query.filter(
        User.role == 'mentor',
        ~User.id.in_(existing_member_ids)
    ).all()
    scored = []
    for m in mentors:
        mentor_text = f"{' '.join(m.interests.split(',') if m.interests else [])} {m.bio or ''}".lower()
        score = sum(1 for kw in room_keywords if kw in mentor_text)
        scored.append({**m.to_dict(), 'match_score': score})

    # Sort by score descending, keep all (frontend can decide how many to show)
    scored.sort(key=lambda x: x['match_score'], reverse=True)
    # Only return mentors with at least 1 keyword match, or all if none match
    relevant = [m for m in scored if m['match_score'] > 0] or scored[:3]
    return jsonify({"mentors": relevant[:5]}), 200
