from pydantic import BaseModel  # type: ignore

class LoginRequest(BaseModel):
    username: str
    password: str

class UserModel(BaseModel):
    username: str
    role: str