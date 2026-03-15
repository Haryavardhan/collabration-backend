from flask import Blueprint
from controllers.room_controller import (
    create_room, get_rooms, request_join_room, 
    approve_join_request, get_room_details,
    add_room_task, update_task_status, send_room_message, start_meet
)

room_bp = Blueprint('room_bp', __name__)

room_bp.route('/', methods=['POST'])(create_room)
room_bp.route('/', methods=['GET'])(get_rooms)
room_bp.route('/<int:room_id>/join', methods=['POST'])(request_join_room)
room_bp.route('/<int:room_id>/approve/<int:target_user_id>', methods=['POST'])(approve_join_request)
room_bp.route('/<int:room_id>', methods=['GET'])(get_room_details)
room_bp.route('/<int:room_id>/tasks', methods=['POST'])(add_room_task)
room_bp.route('/<int:room_id>/tasks/<int:task_id>', methods=['PATCH'])(update_task_status)
room_bp.route('/<int:room_id>/messages', methods=['POST'])(send_room_message)
room_bp.route('/<int:room_id>/start-meet', methods=['POST'])(start_meet)
