from extensions import db
from datetime import datetime

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False) # Hashed
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'student' or 'mentor'
    interests = db.Column(db.String(255), nullable=True)
    phone_number = db.Column(db.String(30), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    charge_per_min = db.Column(db.Float, nullable=True)        # ₹ per minute (mentor only)
    discount_percent = db.Column(db.Float, nullable=True)      # % discount offered (mentor only)
    
    # Razorpay Route Fields
    razorpay_account_id = db.Column(db.String(100), nullable=True)
    razorpay_account_status = db.Column(db.String(20), default='pending') # 'pending', 'active'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    room_memberships = db.relationship('RoomMember', back_populates='user', lazy='dynamic')

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "phone_number": self.phone_number or "",
            "bio": self.bio or "",
            "interests": self.interests.split(',') if self.interests else [],
            "charge_per_min": self.charge_per_min,
            "discount_percent": self.discount_percent,
            "razorpay_account_id": self.razorpay_account_id,
            "razorpay_account_status": self.razorpay_account_status,
        }


class Room(db.Model):
    __tablename__ = 'rooms'
    
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    members = db.relationship('RoomMember', back_populates='room', lazy='dynamic', cascade='all, delete-orphan')
    tasks = db.relationship('Task', back_populates='room', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('Message', back_populates='room', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            "id": self.id,
            "subject": self.subject,
            "description": self.description,
            "creator_id": self.creator_id,
            "created_at": self.created_at.isoformat()
        }

class RoomMember(db.Model):
    __tablename__ = 'room_members'
    
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # role can be 'admin', 'member', 'mentor'
    role = db.Column(db.String(20), default='member')
    # status can be 'pending', 'approved', 'rejected'
    status = db.Column(db.String(20), default='pending')
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    room = db.relationship('Room', back_populates='members')
    user = db.relationship('User', back_populates='room_memberships')

    def to_dict(self):
        return {
            "id": self.id,
            "room_id": self.room_id,
            "user_id": self.user_id,
            "user_name": self.user.name if self.user else "Unknown",
            "user_email": self.user.email if self.user else "Unknown",
            "role": self.role,
            "status": self.status,
            "joined_at": self.joined_at.isoformat(),
            "mentor_charge_per_min": self.user.charge_per_min if self.user and self.role == 'mentor' else None,
            "mentor_discount_percent": self.user.discount_percent if self.user and self.role == 'mentor' else None
        }

class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    # status can be 'todo', 'in_progress', 'done'
    status = db.Column(db.String(20), default='todo')
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    room = db.relationship('Room', back_populates='tasks')
    assignee = db.relationship('User')

    def to_dict(self):
        return {
            "id": self.id,
            "room_id": self.room_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "assignee_name": self.assignee.name if self.assignee else None,
            "created_at": self.created_at.isoformat()
        }

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    room = db.relationship('Room', back_populates='messages')
    user = db.relationship('User')

    def to_dict(self):
        return {
            "id": self.id,
            "room_id": self.room_id,
            "user_id": self.user_id,
            "user_name": self.user.name if self.user else "Unknown",
            "content": self.content,
            "created_at": self.created_at.isoformat()
        }

class MentorConnection(db.Model):
    """Tracks a student's request to connect with a mentor."""
    __tablename__ = 'mentor_connections'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    mentor_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # status: 'pending', 'approved', 'rejected'
    status = db.Column(db.String(20), default='pending')
    message = db.Column(db.Text, nullable=True)  # optional note from student
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('User', foreign_keys=[student_id])
    mentor  = db.relationship('User', foreign_keys=[mentor_id])

    def to_dict(self):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "student_name": self.student.name if self.student else "Unknown",
            "student_email": self.student.email if self.student else "",
            "mentor_id": self.mentor_id,
            "mentor_name": self.mentor.name if self.mentor else "Unknown",
            "mentor_email": self.mentor.email if self.mentor else "",
            "mentor_charge_per_min": self.mentor.charge_per_min if self.mentor else None,
            "mentor_discount_percent": self.mentor.discount_percent if self.mentor else None,
            "status": self.status,
            "message": self.message or "",
            "created_at": self.created_at.isoformat()
        }


class Payment(db.Model):
    """Records a payment from a student to a mentor."""
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    mentor_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    minutes_booked = db.Column(db.Float, nullable=False, default=0)
    amount_paise = db.Column(db.Integer, nullable=False)  # Amount in paise (₹1 = 100 paise)
    razorpay_order_id   = db.Column(db.String(100), nullable=True)
    razorpay_payment_id = db.Column(db.String(100), nullable=True)
    razorpay_signature  = db.Column(db.String(255), nullable=True)
    razorpay_transfer_id = db.Column(db.String(100), nullable=True)
    # status: 'created' | 'paid' | 'failed'
    status = db.Column(db.String(20), default='created')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('User', foreign_keys=[student_id])
    mentor  = db.relationship('User', foreign_keys=[mentor_id])

    def to_dict(self):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "student_name": self.student.name if self.student else "Unknown",
            "mentor_id": self.mentor_id,
            "mentor_name": self.mentor.name if self.mentor else "Unknown",
            "minutes_booked": self.minutes_booked,
            "amount_inr": self.amount_paise / 100,
            "razorpay_order_id": self.razorpay_order_id,
            "razorpay_payment_id": self.razorpay_payment_id,
            "razorpay_transfer_id": self.razorpay_transfer_id,
            "status": self.status,
            "created_at": self.created_at.isoformat()
        }
