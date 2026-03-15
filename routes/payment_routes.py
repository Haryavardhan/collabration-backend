from flask import Blueprint
from controllers.payment_controller import (
    create_order, verify_payment, get_payment_history, create_razorpay_account, release_payment, razorpay_webhook
)

payment_bp = Blueprint('payment_bp', __name__)

payment_bp.route('/create-order/<int:mentor_id>', methods=['POST'])(create_order)
payment_bp.route('/verify', methods=['POST'])(verify_payment)
payment_bp.route('/history', methods=['GET'])(get_payment_history)
payment_bp.route('/onboard-mentor', methods=['POST'])(create_razorpay_account)

# Webhooks and Escrow
payment_bp.route('/webhook', methods=['POST'])(razorpay_webhook)
payment_bp.route('/release/<int:payment_id>', methods=['POST'])(release_payment)
