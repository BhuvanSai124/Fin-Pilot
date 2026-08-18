from pydantic import BaseModel, EmailStr
from typing import List, Optional
import datetime

# User Schemas
class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    financial_iq: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# Academy Schemas
class LessonCompletionRequest(BaseModel):
    lesson_id: str

class LessonCompletionResponse(BaseModel):
    lesson_id: str
    completed_at: datetime.datetime

    class Config:
        from_attributes = True

# Goal Schemas
class GoalSaveRequest(BaseModel):
    goal_type: str
    target_amount: float
    duration_years: int
    monthly_capacity: float
    savings_amount: float
    risk_appetite: str

class GoalResponse(BaseModel):
    goal_type: str
    target_amount: float
    duration_years: int
    monthly_capacity: float
    savings_amount: float
    risk_appetite: str

    class Config:
        from_attributes = True

# Portfolio Schemas
class AssetHoldingResponse(BaseModel):
    asset_class: str
    weight: float
    current_value: float

    class Config:
        from_attributes = True

class RebalanceRequest(BaseModel):
    current_value: float
    risk_appetite: str

class RebalanceResponse(BaseModel):
    total_value: float
    holdings: List[AssetHoldingResponse]
    message: str
