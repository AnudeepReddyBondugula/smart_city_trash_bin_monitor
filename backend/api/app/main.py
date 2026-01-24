from fastapi import FastAPI  # type: ignore
from app.routes.health import router as health_router
from app.routes.ward import router as ward_router
from app.routes.ward_risk import router as ward_risk_router
from app.auth.auth_routes import router as auth_routes_router
from sqlalchemy import text  # type: ignore
from app.db import engine
from fastapi.middleware.cors import CORSMiddleware  # type: ignore

app = FastAPI(
    title="Smart City Trash Bin API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["set-cookie"],
)

print("🚀 Initializing FastAPI application.")
app.include_router(health_router)
app.include_router(ward_router)
app.include_router(ward_risk_router)
app.include_router(auth_routes_router)


@app.on_event("startup")
def startup_check():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✅ Database connection verified")