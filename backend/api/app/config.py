import os

class Settings:
    DB_HOST = os.getenv("DB_HOST") or "postgres"
    DB_PORT = int(os.getenv("DB_PORT") or 5432)
    DB_NAME = os.getenv("DB_NAME") or "trash_bin_db"
    DB_USER = os.getenv("DB_USER") or "admin"
    DB_PASSWORD = os.getenv("DB_PASSWORD") or "admin"

settings = Settings()
