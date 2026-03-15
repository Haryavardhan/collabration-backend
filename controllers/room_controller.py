from flask import jsonify, request
from extensions import db
from models import Room, RoomMember, User, Task, Message
from services.notifications import NotificationService
from flask_jwt_extended import get_jwt_identity, jwt_required

@jwt_required()
def create_room():
    data = request.json
    subject = data.get('subject')
    description = data.get('description', '')
    
    if not subject:
        return jsonify({"error": "Subject is required"}), 400
        
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Create Room
    new_room = Room(subject=subject, description=description, creator_id=user_id)
    db.session.add(new_room)
    db.session.flush() # get new_room.id

    # Add creator as 'admin' and 'approved'
    member = RoomMember(room_id=new_room.id, user_id=user_id, role='admin', status='approved')
    db.session.add(member)
    db.session.commit()

    return jsonify({
        "status": "success", 
        "message": "Room created successfully",
        "room": new_room.to_dict()
    }), 201

@jwt_required()
def get_rooms():
    # Returns all rooms, indicating if current user is a member
    user_id = get_jwt_identity()
    rooms = Room.query.order_by(Room.created_at.desc()).all()
    
    result = []
    for r in rooms:
        r_dict = r.to_dict()
        
        # Check membership status for current user
        membership = RoomMember.query.filter_by(room_id=r.id, user_id=user_id).first()
        if membership:
            r_dict['membership_status'] = membership.status
            r_dict['role'] = membership.role
        else:
            r_dict['membership_status'] = 'none'
            
        # Count approved members
        r_dict['member_count'] = RoomMember.query.filter_by(room_id=r.id, status='approved').count()
        result.append(r_dict)
        
    return jsonify({"rooms": result}), 200

@jwt_required()
def request_join_room(room_id):
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    room = db.session.get(Room, room_id)
    
    if not room:
        return jsonify({"error": "Room not found"}), 404
        
    # Check if already a member or pending
    existing = RoomMember.query.filter_by(room_id=room_id, user_id=user_id).first()
    if existing:
        return jsonify({"error": f"You already have {existing.status} status for this room"}), 400
        
    # Mentors might get auto-approved, students get pending. Let's make everyone pending for now.
    new_member = RoomMember(room_id=room_id, user_id=user_id, role=user.role, status='pending')
    db.session.add(new_member)
    db.session.commit()
    
    # --- NOTIFICATION SYSTEM ---
    # Notify room admins and mentors
    admins_and_mentors = RoomMember.query.filter(
        RoomMember.room_id == room_id,
        RoomMember.status == 'approved',
        RoomMember.role.in_(['admin', 'mentor'])
    ).all()
    
    for am in admins_and_mentors:
        target_user = db.session.get(User, am.user_id)
        if target_user:
            # Send Email
            NotificationService.send_email(
                to_email=target_user.email,
                subject=f"New Join Request for {room.subject}",
                message=f"Hello {target_user.name},\n\n{user.name} ({user.role}) has requested to join your room '{room.subject}'.\nPlease log in to approve or deny the request."
            )
            # Send SMS Mock
            NotificationService.send_sms(
                phone_number="+1234567890", # Mock phone number
                message=f"CollabSphere: {user.name} wants to join {room.subject}. Check your dashboard to approve."
            )

    return jsonify({"status": "success", "message": "Join request sent. Waiting for approval."}), 200

@jwt_required()
def approve_join_request(room_id, target_user_id):
    current_user_id = int(get_jwt_identity())
    
    # Any approved member can approve a join request (not just admin/mentor)
    approver = RoomMember.query.filter_by(room_id=room_id, user_id=current_user_id, status='approved').first()
    if not approver:
        return jsonify({"error": "Unauthorized. You must be an approved member of this room."}), 403
        
    target_member = RoomMember.query.filter_by(room_id=room_id, user_id=target_user_id).first()
    if not target_member:
        return jsonify({"error": "Join request not found"}), 404
        
    target_member.status = 'approved'
    db.session.commit()
    
    # Notify the user they were approved
    target_user = db.session.get(User, target_user_id)
    room = db.session.get(Room, room_id)
    if target_user and room:
        NotificationService.send_email(
            to_email=target_user.email,
            subject=f"Request Approved: {room.subject}",
            message=f"Hello {target_user.name},\n\nYour request to join '{room.subject}' has been approved! You can now participate in chat and tasks."
        )
    
    return jsonify({"status": "success", "message": "User approved successfully"}), 200

@jwt_required()
def get_room_details(room_id):
    user_id = get_jwt_identity()
    
    room = db.session.get(Room, room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
        
    # Verify the user is actually an approved member of this room
    membership = RoomMember.query.filter_by(room_id=room_id, user_id=user_id, status='approved').first()
    if not membership:
        return jsonify({"error": "Unauthorized. You are not an approved member of this room."}), 403
        
    # Fetch Room Data
    room_data = room.to_dict()
    
    # Fetch Members
    members = [m.to_dict() for m in room.members]
    
    # Fetch Tasks
    tasks = [t.to_dict() for t in room.tasks.order_by(Task.created_at.desc())]
    
    # Fetch Messages (Chat)
    messages = [m.to_dict() for m in room.messages.order_by(Message.created_at.asc())]

    return jsonify({
        "room": room_data,
        "members": members,
        "tasks": tasks,
        "messages": messages,
        "current_user_role": membership.role
    }), 200

@jwt_required()
def add_room_task(room_id):
    user_id = get_jwt_identity()
    data = request.json
    
    room = db.session.get(Room, room_id)
    if not room: return jsonify({"error": "Room not found"}), 404
        
    new_task = Task(
        room_id=room_id,
        title=data.get('title'),
        description=data.get('description', ''),
        assigned_to=data.get('assigned_to')
    )
    db.session.add(new_task)
    db.session.commit()
    
    return jsonify({"status": "success", "task": new_task.to_dict()}), 201

@jwt_required()
def update_task_status(room_id, task_id):
    task = Task.query.filter_by(id=task_id, room_id=room_id).first()
    if not task:
        return jsonify({"error": "Task not found"}), 404
    data = request.json
    new_status = data.get('status')
    valid = ['todo', 'in_progress', 'done']
    if new_status not in valid:
        return jsonify({"error": f"Status must be one of {valid}"}), 400
    task.status = new_status
    db.session.commit()
    return jsonify({"status": "success", "task": task.to_dict()}), 200


@jwt_required()
def send_room_message(room_id):
    user_id = get_jwt_identity()
    data = request.json
    content = data.get('content')
    
    if not content: return jsonify({"error": "Content required"}), 400
        
    msg = Message(room_id=room_id, user_id=user_id, content=content)
    db.session.add(msg)
    db.session.commit()
    
    return jsonify({"status": "success", "message": msg.to_dict()}), 201

@jwt_required()
def start_meet(room_id):
    """Notify all approved room members via email and SMS that a meet has been initiated."""
    user_id = get_jwt_identity()
    initiator = db.session.get(User, user_id)
    room = db.session.get(Room, room_id)
    
    if not room:
        return jsonify({"error": "Room not found"}), 404
    
    # Verify the initiator is an approved member
    membership = RoomMember.query.filter_by(room_id=room_id, user_id=user_id, status='approved').first()
    if not membership:
        return jsonify({"error": "Unauthorized. You must be an approved member."}), 403
    
    # Get ALL approved members of the room
    approved_members = RoomMember.query.filter_by(room_id=room_id, status='approved').all()
    
    meet_link = f"https://meet.jit.si/CollabSphere_Room_{room_id}"
    notified_count = 0
    
    for mem in approved_members:
        if str(mem.user_id) == str(user_id):
            continue  # Skip notifying the person who started the meet
        
        target_user = db.session.get(User, mem.user_id)
        if not target_user:
            continue
        
        # Send Email notification
        NotificationService.send_email(
            to_email=target_user.email,
            subject=f"🎥 Meet Started in {room.subject}",
            message=(
                f"Hello {target_user.name},\n\n"
                f"{initiator.name} has just started a video meet in the room '{room.subject}'!\n\n"
                f"Join the meet here: {meet_link}\n\n"
                f"Or log in to CollabSphere and open the Meet tab in the '{room.subject}' room."
            )
        )
        
        # Send SMS notification — use real phone number if available
        phone = target_user.phone_number if target_user.phone_number else "+0000000000"
        NotificationService.send_sms(
            phone_number=phone,
            message=f"CollabSphere: {initiator.name} started a meet in '{room.subject}'! Join: {meet_link}"
        )
        notified_count += 1
    
    return jsonify({
        "status": "success",
        "message": f"Meet started! {notified_count} member(s) have been notified via email.",
        "meet_link": meet_link
    }), 200
