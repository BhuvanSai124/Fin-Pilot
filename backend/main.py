import datetime
from typing import List, Dict
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.database import engine, get_db
from backend.models import Base, User, LessonCompletion, UserGoal, AssetHolding
from backend.auth import get_password_hash, verify_password, create_access_token, get_current_user
from backend.schemas import (
    UserRegister, UserLogin, Token, UserResponse,
    LessonCompletionRequest, LessonCompletionResponse,
    GoalSaveRequest, GoalResponse, RebalanceRequest, RebalanceResponse, AssetHoldingResponse
)

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="FinPilot AI Core API", version="1.0.0")

# Enable CORS for frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for local preview
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- AUTH ENDPOINTS ---

@app.post("/api/auth/signup", response_model=Token)
def signup(user_data: UserRegister, db: Session = Depends(get_db)):
    # Check if email is already taken
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )
    
    # Hash password and create user
    hashed_pwd = get_password_hash(user_data.password)
    new_user = User(
        name=user_data.name,
        email=user_data.email,
        hashed_password=hashed_pwd,
        financial_iq=340
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Return JWT token
    access_token = create_access_token(data={"sub": new_user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/auth/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )
    
    # Return JWT token
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


# --- USER PROFILE & ACADEMY ---

@app.get("/api/user/profile")
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    completions = db.query(LessonCompletion).filter(LessonCompletion.user_id == current_user.id).all()
    completed_ids = [c.lesson_id for c in completions]
    
    goal_data = None
    if current_user.goals:
        goal_data = {
            "goal_type": current_user.goals.goal_type,
            "target_amount": current_user.goals.target_amount,
            "duration_years": current_user.goals.duration_years,
            "monthly_capacity": current_user.goals.monthly_capacity,
            "savings_amount": current_user.goals.savings_amount,
            "risk_appetite": current_user.goals.risk_appetite
        }
        
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "financial_iq": current_user.financial_iq,
        "completed_lessons": completed_ids,
        "goals": goal_data
    }


@app.post("/api/user/lesson")
def complete_lesson(req: LessonCompletionRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Check if already completed
    existing = db.query(LessonCompletion).filter(
        LessonCompletion.user_id == current_user.id,
        LessonCompletion.lesson_id == req.lesson_id
    ).first()
    
    if existing:
        return {"message": "Lesson already marked completed.", "financial_iq": current_user.financial_iq}
        
    # Record completion
    completion = LessonCompletion(user_id=current_user.id, lesson_id=req.lesson_id)
    db.add(completion)
    
    # Increment Financial IQ
    current_user.financial_iq = min(1000, current_user.financial_iq + 50)
    db.commit()
    db.refresh(current_user)
    
    return {
        "message": "Lesson marked completed. Financial IQ increased!",
        "financial_iq": current_user.financial_iq,
        "lesson_id": req.lesson_id
    }


# --- FINANCIAL GOALS & WEALTH RECOMMENDATIONS ---

@app.post("/api/user/goal", response_model=GoalResponse)
def save_goal(goal_data: GoalSaveRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Check if goals already exist
    existing_goal = db.query(UserGoal).filter(UserGoal.user_id == current_user.id).first()
    
    if existing_goal:
        existing_goal.goal_type = goal_data.goal_type
        existing_goal.target_amount = goal_data.target_amount
        existing_goal.duration_years = goal_data.duration_years
        existing_goal.monthly_capacity = goal_data.monthly_capacity
        existing_goal.savings_amount = goal_data.savings_amount
        existing_goal.risk_appetite = goal_data.risk_appetite
        goal = existing_goal
    else:
        goal = UserGoal(
            user_id=current_user.id,
            goal_type=goal_data.goal_type,
            target_amount=goal_data.target_amount,
            duration_years=goal_data.duration_years,
            monthly_capacity=goal_data.monthly_capacity,
            savings_amount=goal_data.savings_amount,
            risk_appetite=goal_data.risk_appetite
        )
        db.add(goal)

    # Re-calculate default asset holdings for the user
    # Delete old holdings first
    db.query(AssetHolding).filter(AssetHolding.user_id == current_user.id).delete()
    
    allocations = []
    initial_value = goal_data.savings_amount + goal_data.monthly_capacity
    
    if goal_data.risk_appetite == "conservative":
        allocations = [
            {"asset_class": "Debt Mutual Funds", "weight": 70.0},
            {"asset_class": "Index Funds (Equity)", "weight": 20.0},
            {"asset_class": "Sovereign Gold Bonds", "weight": 10.0}
        ]
    elif goal_data.risk_appetite == "moderate":
        allocations = [
            {"asset_class": "Equity Index Funds", "weight": 50.0},
            {"asset_class": "Large Cap Stocks", "weight": 30.0},
            {"asset_class": "Gold / Commodities", "weight": 10.0},
            {"asset_class": "Liquid Cash / Debt Reserve", "weight": 10.0}
        ]
    else: # aggressive
        allocations = [
            {"asset_class": "Large & Mid-Cap Equity Funds", "weight": 70.0},
            {"asset_class": "Direct Growth Stocks", "weight": 20.0},
            {"asset_class": "Alternative Assets / Smallcap", "weight": 10.0}
        ]

    for alloc in allocations:
        holding = AssetHolding(
            user_id=current_user.id,
            asset_class=alloc["asset_class"],
            weight=alloc["weight"],
            current_value=(alloc["weight"] / 100.0) * initial_value
        )
        db.add(holding)

    db.commit()
    db.refresh(goal)
    return goal


# --- SIMULATION & PORTFOLIO ENGINE ---

@app.post("/api/portfolio/rebalance", response_model=RebalanceResponse)
def rebalance_portfolio(req: RebalanceRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Real DB modification - shifts 5% from stock risk categories to Gold / Cash safety assets
    holdings = db.query(AssetHolding).filter(AssetHolding.user_id == current_user.id).all()
    
    if not holdings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No portfolio holdings found. Please build a goal strategy first."
        )

    # Shift 5% from direct stocks or index equity to Gold/Cash
    reallocated_value = req.current_value * 1.012 # simulated 1.2% recovery
    
    # Adjust weights and values
    for h in holdings:
        if "Equity" in h.asset_class or "Stocks" in h.asset_class:
            h.weight = max(10, h.weight - 5)
        elif "Gold" in h.asset_class or "Cash" in h.asset_class or "Debt" in h.asset_class:
            h.weight += 5
            
        # Recalculate values based on new weights
        h.current_value = (h.weight / 100.0) * reallocated_value
        
    db.commit()
    
    # Query updated holdings
    updated_holdings = db.query(AssetHolding).filter(AssetHolding.user_id == current_user.id).all()
    response_holdings = [
        AssetHoldingResponse(
            asset_class=h.asset_class,
            weight=h.weight,
            current_value=h.current_value
        ) for h in updated_holdings
    ]
    
    return {
        "total_value": reallocated_value,
        "holdings": response_holdings,
        "message": "AI Rebalancing successful. Adjusted tech holdings into debt and gold."
    }


@app.get("/api/market/news")
def get_market_news(current_user: User = Depends(get_current_user)):
    # Generates custom alerts based on risk appetite
    try:
        risk = "moderate"
        if current_user.goals:
            risk = current_user.goals.risk_appetite
            
        alerts = [
            {
                "id": 1,
                "type": "info",
                "title": "Guardian Scan Completed",
                "desc": "Portfolio allocations are in line with risk parameters."
            }
        ]
        
        if risk == "aggressive" or risk == "moderate":
            alerts.insert(0, {
                "id": 2,
                "type": "warning",
                "title": "IT Sector Heavy Drag Detected",
                "desc": "Tech stocks index drops 6.2% on global correction. Rebalancing recommended."
            })
        elif risk == "conservative":
            alerts.insert(0, {
                "id": 3,
                "type": "info",
                "title": "Yield Spike Notice",
                "desc": "Short term debt yields have increased by 0.25%. Stabilizing portfolios."
            })
            
        return alerts
    except Exception:
        return [
            {
                "id": 0,
                "type": "info",
                "title": "Guardian Online",
                "desc": "Market monitoring is active. No critical alerts at this time."
            }
        ]


# --- HEALTH CHECK ---

@app.get("/api/health")
def health_check():
    """Simple health/ping endpoint for frontend connectivity checks."""
    return {
        "status": "ok",
        "service": "FinPilot AI Core API",
        "version": "1.1.0",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }

