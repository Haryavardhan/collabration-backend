from flask import Blueprint
from controllers.connection_controller import (
    request_connection, get_pending_requests,
    respond_to_request, get_my_connections, get_connection_status
)

connection_bp = Blueprint('connection_bp', __name__)

connection_bp.route('/request/<int:target_id>', methods=['POST'])(request_connection)
connection_bp.route('/requests', methods=['GET'])(get_pending_requests)
connection_bp.route('/<int:connection_id>/respond', methods=['PATCH'])(respond_to_request)
connection_bp.route('/mine', methods=['GET'])(get_my_connections)
connection_bp.route('/status/<int:mentor_id>', methods=['GET'])(get_connection_status)
