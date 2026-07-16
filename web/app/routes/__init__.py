from .auth import auth_bp
from .health import health_bp
from .main import main_bp
from .upload import upload_bp


def register_routes(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(health_bp)
