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
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))
    UPLOAD_FOLDER = build_upload_folder()
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", build_database_url())
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JULIA_EXECUTABLE = os.getenv("JULIA_EXECUTABLE", "julia")
    SIMULATOR_PROJECT_PATH = build_repo_path("SIMULATOR_PROJECT_PATH", "simulator")
    SIMULATOR_RUN_SCRIPT_PATH = build_repo_path(
        "SIMULATOR_RUN_SCRIPT_PATH",
        "simulator/scripts/run_case.jl",
    )
    SIMULATION_DEFAULT_SEED = int(os.getenv("SIMULATION_DEFAULT_SEED", "1234"))
    SIMULATION_DEFAULT_STEPS = int(os.getenv("SIMULATION_DEFAULT_STEPS", "500"))
    SIMULATION_DEFAULT_DENSITY = float(os.getenv("SIMULATION_DEFAULT_DENSITY", "0.25"))
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
        "0,100,500",
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
