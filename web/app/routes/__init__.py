from .main import main_bp
from .upload import upload_bp


def register_routes(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(upload_bp)
