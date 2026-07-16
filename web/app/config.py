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


def normalize_database_url(value):
    """Select psycopg 3 when providers publish a generic PostgreSQL URL."""
    database_url = str(value or "").strip()
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return database_url


def build_redis_url():
    host = os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("REDIS_PORT", "6379")

    return f"redis://{host}:{port}/0"


def build_upload_folder():
    upload_folder = Path(os.getenv("UPLOAD_FOLDER", "storage/uploads"))

    if upload_folder.is_absolute():
        return str(upload_folder)

    return str(BASE_DIR / upload_folder)


def build_repo_path(value, default_relative_path):
    configured_path = Path(os.getenv(value, default_relative_path))

    if configured_path.is_absolute():
        return str(configured_path)

    return str(BASE_DIR / configured_path)


def build_optional_positive_int(value, default="0"):
    raw_value = os.getenv(value, default)

    if raw_value is None:
        return None

    normalized_value = str(raw_value).strip().lower()

    if normalized_value in {"", "0", "none", "null", "false", "unlimited"}:
        return None

    parsed_value = int(normalized_value)

    if parsed_value <= 0:
        return None

    return parsed_value


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    APP_NAME = os.getenv("APP_NAME", "Prototipo de Analisis Mamografico")
    APP_VERSION = os.getenv(
        "APP_VERSION",
        os.getenv("RENDER_GIT_COMMIT", "development"),
    )
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))
    UPLOAD_FOLDER = build_upload_folder()
    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.getenv("DATABASE_URL", build_database_url())
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": int(os.getenv("DATABASE_POOL_RECYCLE_SECONDS", "300")),
    }
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "")
    R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL", "")
    R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
    R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
    R2_REGION = os.getenv("R2_REGION", "auto")
    R2_PRESIGNED_URL_TTL_SECONDS = int(
        os.getenv("R2_PRESIGNED_URL_TTL_SECONDS", "300")
    )
    JULIA_EXECUTABLE = os.getenv("JULIA_EXECUTABLE", "julia")
    SIMULATOR_PROJECT_PATH = build_repo_path("SIMULATOR_PROJECT_PATH", "simulator")
    SIMULATOR_RUN_SCRIPT_PATH = build_repo_path(
        "SIMULATOR_RUN_SCRIPT_PATH",
        "simulator/scripts/run_case.jl",
    )
    # Threads de CPU con los que se lanza Julia (paraleliza el loop de particulas del
    # simulador). Acepta un numero o "auto". Se ajusta segun la maquina: pocos threads en
    # la PC de desarrollo, muchos en el servidor. Por defecto 1 (serial) si no se define.
    SIMULATION_CPU_THREADS = os.getenv("SIMULATION_CPU_THREADS", "1")
    SIMULATION_DEFAULT_SEED = int(os.getenv("SIMULATION_DEFAULT_SEED", "1234"))
    SIMULATION_DEFAULT_STEPS = int(os.getenv("SIMULATION_DEFAULT_STEPS", "100"))
    SIMULATION_DEFAULT_N0 = float(os.getenv("SIMULATION_DEFAULT_N0", "10"))
    SIMULATION_DEFAULT_MASS = float(os.getenv("SIMULATION_DEFAULT_MASS", "1"))
    SIMULATION_DEFAULT_KBT = float(os.getenv("SIMULATION_DEFAULT_KBT", "1"))
    SIMULATION_DEFAULT_TAU = float(os.getenv("SIMULATION_DEFAULT_TAU", "1"))
    SIMULATION_DEFAULT_ROTATION_ANGLE = float(
        os.getenv("SIMULATION_DEFAULT_ROTATION_ANGLE", "1.5707963267948966"),
    )
    SIMULATION_DEFAULT_REALIZATIONS = int(
        os.getenv("SIMULATION_DEFAULT_REALIZATIONS", "3"),
    )
    SIMULATION_DEFAULT_LABELED_PARTICLES = int(
        os.getenv("SIMULATION_DEFAULT_LABELED_PARTICLES", "500"),
    )
    SIMULATION_CORRELATION_INITIAL_TIMES = int(
        os.getenv("SIMULATION_CORRELATION_INITIAL_TIMES", "50"),
    )
    SIMULATION_DEFAULT_OUTPUT_TIMES = os.getenv(
        "SIMULATION_DEFAULT_OUTPUT_TIMES",
        "0,100",
    )
    SIMULATION_GRID_SHIFT_ENABLED = os.getenv(
        "SIMULATION_GRID_SHIFT_ENABLED",
        "false",
    )
    SIMULATION_TIMEOUT_SECONDS = build_optional_positive_int(
        "SIMULATION_TIMEOUT_SECONDS",
    )
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_URL = os.getenv("REDIS_URL", build_redis_url())
    SIMULATION_QUEUE_NAME = os.getenv("SIMULATION_QUEUE_NAME", "simulation_jobs")
    # Envio de correo. Agnostico al proveedor: "console" (por defecto) escribe el
    # correo en el log (desarrollo/demo, sin credenciales); "smtp" entrega via un
    # servidor SMTP (p. ej. una cuenta de Gmail dedicada) en produccion.
    MAIL_BACKEND = os.getenv("MAIL_BACKEND", "console")
    MAIL_SMTP_HOST = os.getenv("MAIL_SMTP_HOST", "")
    MAIL_SMTP_PORT = int(os.getenv("MAIL_SMTP_PORT", "587"))
    MAIL_SMTP_USERNAME = os.getenv("MAIL_SMTP_USERNAME", "")
    MAIL_SMTP_PASSWORD = os.getenv("MAIL_SMTP_PASSWORD", "")
    MAIL_SMTP_USE_TLS = os.getenv("MAIL_SMTP_USE_TLS", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    MAIL_SENDER = os.getenv("MAIL_SENDER", "")
    BREVO_API_URL = os.getenv(
        "BREVO_API_URL",
        "https://api.brevo.com/v3/smtp/email",
    )
    BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
    BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "")
    BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "")
    # Validez del enlace de recuperacion de contraseña, en segundos (1 hora).
    PASSWORD_RESET_TOKEN_MAX_AGE = int(
        os.getenv("PASSWORD_RESET_TOKEN_MAX_AGE", "3600")
    )
