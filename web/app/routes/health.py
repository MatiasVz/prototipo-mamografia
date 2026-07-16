from flask import Blueprint, current_app, jsonify

from ..services.health_service import check_runtime_dependencies


health_bp = Blueprint("health", __name__, url_prefix="/health")


@health_bp.get("/live")
def live():
    return jsonify(
        status="ok",
        version=current_app.config.get("APP_VERSION", "development"),
    ), 200


@health_bp.get("/ready")
def ready():
    health = check_runtime_dependencies(current_app.config)
    status_code = 200 if health.ready else 503
    status = "ready" if health.ready else "unavailable"
    return jsonify(
        status=status,
        version=current_app.config.get("APP_VERSION", "development"),
        checks=health.as_dict(),
    ), status_code
