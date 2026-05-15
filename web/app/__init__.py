from flask import Flask

from .cli import register_cli_commands
from .config import Config
from .extensions import db
from .routes import register_routes


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    register_routes(app)
    register_cli_commands(app)

    return app
