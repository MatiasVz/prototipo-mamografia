import click
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import Case, CaseStatus, InputMode


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

    @app.cli.command("db-init")
    def db_init():
        """Create configured database tables for local development."""
        db.create_all()
        click.echo("Tablas de base de datos creadas o verificadas correctamente.")

    @app.cli.command("case-create-sample")
    def case_create_sample():
        """Create a sample case record for verification evidence."""
        sample_case = Case(
            input_mode=InputMode.MAMMOGRAM,
            original_filename="mamografia_prueba.png",
            original_file_path="storage/uploads/case_sample/original.png",
            file_type="image/png",
            file_size_bytes=1024,
            status=CaseStatus.REGISTERED,
        )

        db.session.add(sample_case)
        db.session.commit()

        click.echo(
            f"Caso de prueba creado con id={sample_case.id} y estado={sample_case.status}."
        )

    @app.cli.command("case-list")
    def case_list():
        """List registered cases for verification evidence."""
        cases = Case.query.order_by(Case.id.asc()).all()

        if not cases:
            click.echo("No existen casos registrados.")
            return

        for case in cases:
            click.echo(
                f"id={case.id} filename={case.original_filename} "
                f"type={case.file_type} status={case.status}"
            )
