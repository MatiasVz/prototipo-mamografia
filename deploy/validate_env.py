from pathlib import Path
import os
import sys
from urllib.parse import urlsplit


REQUIRED_KEYS = (
    "PUBLIC_BASE_URL",
    "SECRET_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "STORAGE_BACKEND",
    "R2_BUCKET_NAME",
    "R2_ENDPOINT_URL",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "MAIL_BACKEND",
    "BREVO_API_KEY",
    "BREVO_SENDER_NAME",
    "BREVO_SENDER_EMAIL",
)

EXPECTED_WORKER_VALUES = {
    "SIMULATION_DEFAULT_STEPS": "200",
    "SIMULATION_DEFAULT_REALIZATIONS": "3",
    "SIMULATION_DEFAULT_LABELED_PARTICLES": "500",
    "SIMULATION_DEFAULT_OUTPUT_TIMES": "0,200",
    "SIMULATION_TIMEOUT_SECONDS": "0",
    "SIMULATION_CPU_THREADS": "30",
    "WORKER_CPU_LIMIT": "30",
}


def load_environment(path):
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized = value.strip()
        if len(normalized) >= 2 and normalized[0] == normalized[-1] in {"'", '"'}:
            normalized = normalized[1:-1]
        values[key.strip()] = normalized
    return values


def validate_environment(values):
    errors = []
    missing = [key for key in REQUIRED_KEYS if not values.get(key)]
    if missing:
        errors.append("Faltan variables requeridas: " + ", ".join(sorted(missing)))

    if values.get("STORAGE_BACKEND", "").lower() != "r2":
        errors.append("STORAGE_BACKEND debe ser r2 en produccion.")
    if values.get("MAIL_BACKEND", "").lower() != "brevo":
        errors.append("MAIL_BACKEND debe ser brevo en produccion.")

    _validate_url(values, "PUBLIC_BASE_URL", {"http", "https"}, errors)
    _validate_url(values, "DATABASE_URL", {"postgres", "postgresql"}, errors)
    _validate_url(values, "REDIS_URL", {"rediss"}, errors)
    _validate_url(values, "R2_ENDPOINT_URL", {"https"}, errors)

    for key, expected in EXPECTED_WORKER_VALUES.items():
        if values.get(key) != expected:
            errors.append(f"{key} debe ser {expected} para el despliegue acordado.")

    return errors


def _validate_url(values, key, allowed_schemes, errors):
    value = values.get(key, "")
    if not value:
        return
    try:
        parsed = urlsplit(value)
    except ValueError:
        parsed = None
    if parsed is None or parsed.scheme not in allowed_schemes or not parsed.netloc:
        errors.append(f"{key} no tiene un formato valido para produccion.")


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(
            "Uso: python3 deploy/validate_env.py "
            "<archivo-env|--current-environment>",
            file=sys.stderr,
        )
        return 2

    if args[0] == "--current-environment":
        values = dict(os.environ)
    else:
        path = Path(args[0]).expanduser()
        if not path.is_file():
            print(f"No existe el archivo de entorno: {path}", file=sys.stderr)
            return 2
        values = load_environment(path)

    errors = validate_environment(values)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Variables de produccion verificadas sin mostrar secretos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
