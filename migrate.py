from app import create_app
from extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        db.session.execute(text('ALTER TABLE payments ADD COLUMN razorpay_transfer_id VARCHAR(100)'))
        db.session.commit()
        print('Migration successful')
    except Exception as e:
        print(f"Migration failed or column already exists: {e}")
