from fastapi import APIRouter, Depends, HTTPException, Response, status       # type: ignore
from sqlalchemy import text                                                     # type: ignore
from app.db import engine
from app.auth.jwt import create_access_token
from app.auth.jwt import verify_password
from app.auth.dependencies import get_current_user
from app.models.credentials import LoginRequest, UserModel as User

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
def login(payload: LoginRequest, response: Response):
    # 1️⃣ Validate user
    with engine.connect() as conn:
        user = conn.execute(
            text("""
                SELECT username, password_hash, role, is_active
                FROM api_users
                WHERE username = :username
            """),
            {"username": payload.username}
        ).mappings().first()

    if not user or not user["is_active"]:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 2️⃣ Create JWT
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "role": user["role"]
        }
    )

    # 3️⃣ 🔥 SET HTTP-ONLY COOKIE (IMPORTANT PART)
    response.set_cookie(
        key="token",
        value=access_token,
        httponly=True,        
        samesite="lax",
        secure=False,         # True in production (HTTPS)
        path="/",
        max_age=3600,
    )

    # 4️⃣ Optional body response
    return {
        "message": "Login successful",
        "role": user["role"]
    }

@router.post("/logout")
def logout(response: Response): # Clear the cookie by setting it to expire immediately 
    response.delete_cookie("token")
    return {"message": "Logged out"}

@router.get("/is_authenticated")
def is_authenticated(current_user: User = Depends(get_current_user)):
    return {"authenticated": True, "username": current_user.username, "role": current_user.role}