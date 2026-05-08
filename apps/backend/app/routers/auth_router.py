"""Auth routes: login, current user."""
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user, verify_password, create_token
from app.deps import db, audit_log
from app.models import LoginRequest, LoginResponse, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    user = await db.users.find_one({"email": body.email.lower()}, {"_id": 0})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(user["id"], user["email"], user["role"])
    await audit_log(user["email"], "login", "user", user["id"])
    return {
        "token": token,
        "user": {
            "id": user["id"], "email": user["email"], "full_name": user["full_name"],
            "role": user["role"], "entity": user.get("entity"),
        },
    }


@router.get("/me", response_model=UserPublic)
async def me(current=Depends(get_current_user)):
    user = await db.users.find_one({"id": current["user_id"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
