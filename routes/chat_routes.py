from flask import Blueprint, jsonify, request
from services.ai_bot import ask_career_bot

chat_bp = Blueprint('chat_bp', __name__)

@chat_bp.route('/ask', methods=['POST'])
def ask_bot():
    data = request.get_json() or {}
    question = data.get('question', '').strip()
    history  = data.get('history', [])   # list of {role, content}

    if not question:
        return jsonify({"error": "Question is required"}), 400

    result = ask_career_bot(question, history=history)
    return jsonify(result), 200
