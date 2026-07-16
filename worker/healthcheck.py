from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = REPO_ROOT / "web"

if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from app import create_app  # noqa: E402
from app.services.health_service import check_runtime_dependencies  # noqa: E402


def main():
    flask_app = create_app()
    with flask_app.app_context():
        health = check_runtime_dependencies(flask_app.config)

    print(
        "worker_health=" + ("ready" if health.ready else "unavailable"),
        flush=True,
    )
    return 0 if health.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
