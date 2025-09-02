from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
import socketio
import uvicorn
from typing import List
from datetime import timedelta

from database import get_db, engine, Base
from models import User, Message
from schemas import UserCreate, UserResponse, MessageCreate, MessageResponse, Token, UserLogin
from auth import get_password_hash, verify_password, create_access_token, verify_token, ACCESS_TOKEN_EXPIRE_MINUTES

# Create tables
Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI(title="High School Rebellion Chat", version="1.0.0")

# Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins="*",
    logger=True
)

# Combine FastAPI and Socket.IO
socket_app = socketio.ASGIApp(sio, app)

# Serve static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Store active connections
active_connections = {}

# Security scheme
security = HTTPBearer()

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Extract user ID from JWT token"""
    return verify_token(credentials.credentials)

@app.get("/")
async def root():
    return FileResponse('frontend/index.html')

@app.get("/chat")
async def chat():
    return FileResponse('frontend/chat.html')

# User Registration
@app.post("/users", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        name=user.name,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# User Login
@app.post("/login", response_model=Token)
def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_credentials.email).first()
    
    if not user or not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

# Send Message
@app.post("/messages", response_model=MessageResponse)
def send_message(message: MessageCreate, db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    sender_id = current_user_id
    
    # Verify receiver exists
    receiver = db.query(User).filter(User.id == message.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found")
    
    # Create message
    db_message = Message(
        sender_id=sender_id,
        receiver_id=message.receiver_id,
        message=message.message
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    
    # Get sender name for response
    sender = db.query(User).filter(User.id == sender_id).first()
    response_message = MessageResponse(
        id=db_message.id,
        sender_id=db_message.sender_id,
        receiver_id=db_message.receiver_id,
        message=db_message.message,
        created_at=db_message.created_at,
        sender_name=sender.name
    )
    
    return response_message

# Get Messages
@app.get("/messages", response_model=List[MessageResponse])
def get_messages(userId: int, limit: int = 50, db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    
    # Get messages where user is either sender or receiver with the specified userId
    messages = db.query(Message).join(User, Message.sender_id == User.id).filter(
        or_(
            and_(Message.sender_id == current_user_id, Message.receiver_id == userId),
            and_(Message.sender_id == userId, Message.receiver_id == current_user_id)
        )
    ).order_by(desc(Message.created_at)).limit(limit).all()
    
    # Add sender names to messages
    response_messages = []
    for msg in messages:
        sender = db.query(User).filter(User.id == msg.sender_id).first()
        response_messages.append(MessageResponse(
            id=msg.id,
            sender_id=msg.sender_id,
            receiver_id=msg.receiver_id,
            message=msg.message,
            created_at=msg.created_at,
            sender_name=sender.name
        ))
    
    return response_messages

# Get all users (for chat selection) - FIXED VERSION
@app.get("/users", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    users = db.query(User).filter(User.id != current_user_id).all()
    return users

# Socket.IO Events
@sio.event
async def connect(sid, environ, auth):
    if auth and 'token' in auth:
        try:
            user_id = verify_token(auth['token'])
            active_connections[sid] = user_id
            await sio.emit('connected', {'message': 'Connected successfully'}, to=sid)
            print(f"User {user_id} connected with session {sid}")
        except HTTPException:
            await sio.disconnect(sid)
    else:
        await sio.disconnect(sid)

@sio.event
async def disconnect(sid):
    if sid in active_connections:
        user_id = active_connections.pop(sid)
        print(f"User {user_id} disconnected")

@sio.event
async def send_message(sid, data):
    if sid not in active_connections:
        return
    
    sender_id = active_connections[sid]
    receiver_id = data.get('receiver_id')
    message_text = data.get('message')
    
    if not receiver_id or not message_text:
        return
    
    # Save to database
    db = next(get_db())
    try:
        db_message = Message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message=message_text
        )
        db.add(db_message)
        db.commit()
        db.refresh(db_message)
        
        # Get sender name
        sender = db.query(User).filter(User.id == sender_id).first()
        
        # Emit to both sender and receiver
        message_data = {
            'id': db_message.id,
            'sender_id': sender_id,
            'receiver_id': receiver_id,
            'message': message_text,
            'sender_name': sender.name,
            'created_at': db_message.created_at.isoformat()
        }
        
        # Send to receiver if online
        for session_id, user_id in active_connections.items():
            if user_id == receiver_id:
                await sio.emit('new_message', message_data, to=session_id)
        
        # Send confirmation to sender
        await sio.emit('message_sent', message_data, to=sid)
        
    except Exception as e:
        print(f"Error saving message: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    uvicorn.run("main:socket_app", host="0.0.0.0", port=8000, reload=True)
