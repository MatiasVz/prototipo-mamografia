import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ENV_NAMES = {".env.example", "production.env.example"}
SECRET_ASSIGNMENTS = {
    "BREVO_API_KEY",
    "DATABASE_URL",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "REDIS_URL",
    "SECRET_KEY",
}
TOKEN_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"xkeysib-[A-Za-z0-9_-]{32,}"),
    re.compile(r"cfat_[A-Za-z0-9_-]{24,}"),
    re.compile(r"rediss?://[^:\s]+:[^@\s]{12,}@"),
    re.compile(r"postgres(?:ql)?://[^:\s]+:[^@\s]{12,}@"),
)
PLACEHOLDER_MARKERS = (
    "127.0.0.1",
    "change-me",
    "dev-",
    "example",
    "invalid",
    "localhost",
    "password",
    "replace",
    "secret-key",
    "sqlite",
    "test-",
    "${",
)


def repository_files(root=ROOT):
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        cwd=root,
        check=True,
        capture_output=True,
    )
    for raw_path in result.stdout.split(b"\0"):
        if raw_path:
            yield root / raw_path.decode("utf-8")


def is_forbidden_environment_file(path):
    name = path.name.lower()
    if name in ALLOWED_ENV_NAMES:
        return False
    return name == ".env" or name.startswith(".env.") or name.endswith(".env")


def scan_text(path, text):
    findings = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        if any(pattern.search(line) for pattern in TOKEN_PATTERNS):
            if not any(marker in lowered for marker in PLACEHOLDER_MARKERS):
                findings.append((line_number, "posible credencial o clave privada"))

        stripped = line.strip()
        assignment = re.match(r"^([A-Z][A-Z0-9_]*)=(.*)$", stripped)
        if assignment is None:
            continue
        key, value = assignment.groups()
        if key not in SECRET_ASSIGNMENTS:
            continue
        normalized = value.strip().strip("'\"")
        if normalized and not any(
            marker in normalized.lower() for marker in PLACEHOLDER_MARKERS
        ):
            findings.append((line_number, f"valor real asignado a {key}"))
    return findings


def main():
    findings = []
    for path in repository_files():
        relative_path = path.relative_to(ROOT)
        if is_forbidden_environment_file(path):
            findings.append((relative_path, 0, "archivo de entorno no permitido"))
            continue
        try:
            content = path.read_bytes()
        except OSError as exc:
            findings.append((relative_path, 0, f"no se pudo leer: {exc}"))
            continue
        if b"\0" in content:
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(
            (relative_path, line_number, reason)
            for line_number, reason in scan_text(path, text)
        )

    if findings:
        for path, line_number, reason in findings:
            location = f"{path}:{line_number}" if line_number else str(path)
            print(f"ERROR: {location}: {reason}", file=sys.stderr)
        return 1

    print("Repositorio verificado: no se detectaron secretos versionados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
