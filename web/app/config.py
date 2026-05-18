import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def build_database_url():
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "1234")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "mamografias_db")

    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


def build_upload_folder():
    upload_folder = Path(os.getenv("UPLOAD_FOLDER", "storage/uploads"))

    if upload_folder.is_absolute():
        return str(upload_folder)

    return str(BASE_DIR / upload_folder)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    APP_NAME = os.getenv("APP_NAME", "Prototipo de Analisis Mamografico")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))
    UPLOAD_FOLDER = build_upload_folder()
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", build_database_url())
    SQLALCHEMY_TRACK_MODIFICATIONS = False
