import click
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import Case, CaseStatus, InputMode
from .services.simulation_worker_service import (
    SimulationWorkerError,
    process_case_simulation,
)


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
        _ensure_case_tracking_columns()
        click.echo("Tablas de base de datos creadas o verificadas correctamente.")

    @app.cli.command("db-upgrade-roi-fields")
    def db_upgrade_roi_fields():
        """Add ROI fields to an existing local cases table."""
        _ensure_case_tracking_columns()
        click.echo("Campos de ROI verificados correctamente en la tabla cases.")

    @app.cli.command("db-upgrade-simulation-fields")
    def db_upgrade_simulation_fields():
        """Add simulation input and result fields to an existing local cases table."""
        _ensure_case_tracking_columns()
        click.echo("Campos de simulacion verificados correctamente.")

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

    @app.cli.command("case-run-simulation")
    @click.argument("case_id", type=int)
    @click.option("--seed", type=int, default=None, help="Semilla reproducible.")
    @click.option("--steps", type=int, default=None, help="Numero de pasos.")
    @click.option("--density", type=float, default=None, help="Densidad de particulas.")
    def case_run_simulation(case_id, seed, steps, density):
        """Run the Julia simulator for one prepared case."""
        case = db.session.get(Case, case_id)

        if case is None:
            raise click.ClickException(f"No existe un caso registrado con id={case_id}.")

        try:
            result = process_case_simulation(
                case,
                app.config,
                seed=seed,
                steps=steps,
                density=density,
            )
        except SimulationWorkerError as exc:
            raise click.ClickException(str(exc)) from exc
        except SQLAlchemyError as exc:
            db.session.rollback()
            raise click.ClickException(
                f"No se pudo actualizar el estado del caso: {exc}"
            ) from exc

        click.echo(f"Caso {result.case_id} procesado correctamente.")
        click.echo(f"status={result.status}")
        click.echo(f"output_dir={result.output_dir}")
        click.echo(f"metrics_path={result.metrics_path}")
        click.echo(f"domain_mask_path={result.domain_mask_path}")
        click.echo(f"density_map_path={result.density_map_path}")
        click.echo(f"mpc_config_path={result.mpc_config_path}")
        click.echo(f"obstacle_radius_matrix_path={result.obstacle_radius_matrix_path}")
        click.echo(f"obstacle_radius_map_path={result.obstacle_radius_map_path}")
        click.echo(f"obstacle_radius_histogram_path={result.obstacle_radius_histogram_path}")
        click.echo(f"mpc_initial_particles_path={result.mpc_initial_particles_path}")
        click.echo(f"mpc_streamed_particles_path={result.mpc_streamed_particles_path}")
        click.echo(f"mpc_streaming_summary_path={result.mpc_streaming_summary_path}")
        click.echo(f"mpc_collided_particles_path={result.mpc_collided_particles_path}")
        click.echo(f"mpc_collision_summary_path={result.mpc_collision_summary_path}")
        click.echo(f"mpc_cell_collisions_path={result.mpc_cell_collisions_path}")
        click.echo(f"simulation_log_path={result.simulation_log_path}")
        click.echo(f"worker_log_path={result.worker_log_path}")


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
        f"simulation_input_path={case.simulation_input_file_path or ''} "
        f"simulation_input_size_bytes={case.simulation_input_size_bytes or ''} "
        f"simulation_results_path={case.simulation_results_path or ''} "
        f"simulation_metrics_path={case.simulation_metrics_file_path or ''} "
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
        ("simulation_input_filename", case.simulation_input_filename or ""),
        ("simulation_input_file_path", case.simulation_input_file_path or ""),
        ("simulation_input_file_type", case.simulation_input_file_type or ""),
        ("simulation_input_size_bytes", case.simulation_input_size_bytes or ""),
        ("simulation_results_path", case.simulation_results_path or ""),
        ("simulation_metrics_file_path", case.simulation_metrics_file_path or ""),
        ("simulation_density_map_file_path", case.simulation_density_map_file_path or ""),
        ("simulation_log_file_path", case.simulation_log_file_path or ""),
        ("status", case.status),
        ("error_message", case.error_message or ""),
    )


def _format_timestamp(value):
    if value is None:
        return ""

    return value.isoformat()


def _ensure_case_tracking_columns():
    case_columns = {
        "roi_filename": "VARCHAR(255)",
        "roi_file_path": "VARCHAR(500)",
        "roi_file_type": "VARCHAR(50)",
        "roi_size_bytes": "BIGINT",
        "simulation_input_filename": "VARCHAR(255)",
        "simulation_input_file_path": "VARCHAR(500)",
        "simulation_input_file_type": "VARCHAR(50)",
        "simulation_input_size_bytes": "BIGINT",
        "simulation_results_path": "VARCHAR(500)",
        "simulation_metrics_file_path": "VARCHAR(500)",
        "simulation_density_map_file_path": "VARCHAR(500)",
        "simulation_log_file_path": "VARCHAR(500)",
    }

    with db.engine.begin() as connection:
        existing_columns = {
            column["name"] for column in inspect(connection).get_columns("cases")
        }

        for column_name, column_type in case_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(f"ALTER TABLE cases ADD COLUMN {column_name} {column_type}")
                )
