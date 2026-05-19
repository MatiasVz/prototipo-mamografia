import click
from sqlalchemy import inspect, text
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
        _ensure_case_roi_columns()
        click.echo("Tablas de base de datos creadas o verificadas correctamente.")

    @app.cli.command("db-upgrade-roi-fields")
    def db_upgrade_roi_fields():
        """Add ROI fields to an existing local cases table."""
        _ensure_case_roi_columns()
        click.echo("Campos de ROI verificados correctamente en la tabla cases.")

    @app.cli.command("case-create-sample")
    def case_create_sample():
        """Create a sample case record for verification evidence."""
        sample_case = Case(
            input_mode=InputMode.MAMMOGRAM,
            original_filename="mamografia_prueba.png",
            original_file_path="storage/uploads/case_sample/original.png",
            file_type="image",
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
            click.echo(_format_case_summary(case))

    @app.cli.command("case-show")
    @click.argument("case_id", type=int)
    def case_show(case_id):
        """Show one registered case by ID for verification evidence."""
        case = db.session.get(Case, case_id)

        if case is None:
            raise click.ClickException(f"No existe un caso registrado con id={case_id}.")

        for field_name, value in _case_detail_rows(case):
            click.echo(f"{field_name}: {value}")


def _format_case_summary(case):
    return (
        f"id={case.id} "
        f"fecha={_format_timestamp(case.created_at)} "
        f"modalidad={case.input_mode} "
        f"filename={case.original_filename} "
        f"path={case.original_file_path} "
        f"type={case.file_type} "
        f"size_bytes={case.file_size_bytes} "
        f"roi_path={case.roi_file_path or ''} "
        f"roi_size_bytes={case.roi_size_bytes or ''} "
        f"status={case.status}"
    )


def _case_detail_rows(case):
    return (
        ("id", case.id),
        ("created_at", _format_timestamp(case.created_at)),
        ("updated_at", _format_timestamp(case.updated_at)),
        ("input_mode", case.input_mode),
        ("original_filename", case.original_filename),
        ("original_file_path", case.original_file_path),
        ("file_type", case.file_type),
        ("file_size_bytes", case.file_size_bytes),
        ("roi_filename", case.roi_filename or ""),
        ("roi_file_path", case.roi_file_path or ""),
        ("roi_file_type", case.roi_file_type or ""),
        ("roi_size_bytes", case.roi_size_bytes or ""),
        ("status", case.status),
        ("error_message", case.error_message or ""),
    )


def _format_timestamp(value):
    if value is None:
        return ""

    return value.isoformat()


def _ensure_case_roi_columns():
    roi_columns = {
        "roi_filename": "VARCHAR(255)",
        "roi_file_path": "VARCHAR(500)",
        "roi_file_type": "VARCHAR(50)",
        "roi_size_bytes": "BIGINT",
    }

    with db.engine.begin() as connection:
        existing_columns = {
            column["name"] for column in inspect(connection).get_columns("cases")
        }

        for column_name, column_type in roi_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(f"ALTER TABLE cases ADD COLUMN {column_name} {column_type}")
                )
