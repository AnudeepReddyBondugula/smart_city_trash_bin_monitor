from fastapi import Request, HTTPException, status, Depends         # type: ignore
from jose import jwt, JWTError                        # type: ignore
from sqlalchemy import text                            # type: ignore
from app.db import engine
from app.auth.jwt import SECRET_KEY, ALGORITHM
from app.middleware.rate_limit import rate_limiter

def get_current_user(request: Request):
    token = request.cookies.get("token")
    if not token:
        print("No JWT token found in cookies")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            print("JWT token missing 'sub' claim")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        print("JWT decoding error for token:", token)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    with engine.connect() as conn:
        user = conn.execute(
            text("""
                SELECT username, role, is_active
                FROM api_users
                WHERE username = :username
            """),
            {"username": username}
        ).mappings().first()

    if not user or not user["is_active"]:
        print("Inactive or non-existent user attempted access:", username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")

    request.state.user = user
    return user



def require_role(required_roles: list):
    async def role_checker(request: Request, user=Depends(get_current_user)):
        if user["role"] not in required_roles:
            print(f"User '{user['username']}' with role '{user['role']}' attempted unauthorized access.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        # RATE LIMIT AFTER AUTH
        await rate_limiter(request)
        return user
    return role_checker

