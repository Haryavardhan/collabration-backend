from flask import Blueprint
from controllers.user_controller import get_user_profile, update_user_profile, get_mentors, get_suggested_mentors_for_room

user_bp = Blueprint('user_bp', __name__)

user_bp.route('/mentors', methods=['GET'])(get_mentors)
user_bp.route('/mentors/suggest/<int:room_id>', methods=['GET'])(get_suggested_mentors_for_room)
user_bp.route('/<user_id>', methods=['GET'])(get_user_profile)
user_bp.route('/<user_id>', methods=['PUT'])(update_user_profile)
