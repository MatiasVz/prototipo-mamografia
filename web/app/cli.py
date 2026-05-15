import click
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db


def register_cli_commands(app):
    @app.cli.command("db-check")
    def db_check():
        """Verify that Flask can connect to PostgreSQL."""
        try:
            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise click.ClickException(f"No se pudo conectar a PostgreSQL: {exc}") from exc

        click.echo("Conexion a PostgreSQL verificada correctamente.")
