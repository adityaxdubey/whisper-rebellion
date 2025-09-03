from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    name: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class MessageBase(BaseModel):
    message: str

class MessageCreate(MessageBase):
    receiver_id: int

class MessageResponse(MessageBase):
    id: int
    sender_id: int
    receiver_id: int
    created_at: datetime
    sender_name: str
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
