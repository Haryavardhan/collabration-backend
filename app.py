from flask import Flask, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
import datetime

from extensions import db, jwt
from routes.user_routes import user_bp
from routes.room_routes import room_bp

load_dotenv()

app = Flask(__name__)
CORS(app)

# Database Configuration (PostgreSQL/SQLite fallback)
# For local easy testing without pgAdmin, we'll default to SQLite. Easy to swap to PostgreSQL later via .env
db_url = os.getenv('DATABASE_URL', 'sqlite:///collab.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# JWT Configuration
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'super-secret-key') # Change this in production
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(hours=24)

print(">>> Backend: Initializing extensions...")
db.init_app(app)
jwt.init_app(app)

print(">>> Backend: Creating database tables (create_all)...")
# Create tables
with app.app_context():
    import models  # Ensure models are known to SQLAlchemy
    db.create_all()
print(">>> Backend: Database initialized.")

from routes.auth_routes import auth_bp
from routes.chat_routes import chat_bp

print(">>> Backend: Registering blueprints...")
app.register_blueprint(user_bp, url_prefix='/api/users')
app.register_blueprint(room_bp, url_prefix='/api/rooms')
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(chat_bp, url_prefix='/api/chat')

from routes.connection_routes import connection_bp
app.register_blueprint(connection_bp, url_prefix='/api/connections')

from routes.payment_routes import payment_bp
app.register_blueprint(payment_bp, url_prefix='/api/payments')

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
