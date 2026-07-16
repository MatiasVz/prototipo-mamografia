import argparse
from pathlib import Path
import signal
import sys
import time

from sqlalchemy.exc import SQLAlchemyError


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = REPO_ROOT / "web"

if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Case  # noqa: E402
from app.services.simulation_queue_service import (  # noqa: E402
    SimulationQueueError,
    pop_queued_case_id,
)
from app.services.simulation_worker_service import (  # noqa: E402
    SimulationWorkerError,
    process_case_simulation,
)


class WorkerShutdownRequested(Exception):
    pass


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Worker Python para ejecutar el simulador Julia por caso.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    process_parser = subparsers.add_parser(
        "process-case",
        help="Procesa un caso con entrada PGM preparada.",
    )
    process_parser.add_argument("case_id", type=int)
    process_parser.add_argument("--seed", type=int, default=None)
    process_parser.add_argument("--steps", type=int, default=None)

    idle_parser = subparsers.add_parser(
        "idle",
        help="Mantiene el contenedor worker activo sin consumir la cola.",
    )
    idle_parser.add_argument("--interval", type=int, default=60)

    listen_parser = subparsers.add_parser(
        "listen",
        help="Escucha la cola Redis y procesa casos automaticamente.",
    )
    listen_parser.add_argument("--timeout", type=int, default=5)

    args = parser.parse_args(argv)

    if args.command == "process-case":
        return process_case(args)

    if args.command == "idle":
        return idle(args)

    if args.command == "listen":
        return listen(args)

    parser.error("Comando no reconocido.")
    return 1


def process_case(args):
    flask_app = create_app()

    with flask_app.app_context():
        return _process_case_id(
            args.case_id,
            flask_app,
            seed=args.seed,
            steps=args.steps,
        )


def _process_case_id(case_id, flask_app, *, seed=None, steps=None):
    case = db.session.get(Case, case_id)

    if case is None:
        print(f"No existe un caso registrado con id={case_id}.", file=sys.stderr)
        return 1

    try:
        result = process_case_simulation(
            case,
            flask_app.config,
            seed=seed,
            steps=steps,
        )
    except SimulationWorkerError as exc:
        print(f"Error de procesamiento: {exc}", file=sys.stderr)
        return 1
    except SQLAlchemyError as exc:
        db.session.rollback()
        print(f"No se pudo actualizar el caso: {exc}", file=sys.stderr)
        return 1

    print(f"Caso {result.case_id} procesado correctamente.", flush=True)
    print(f"status={result.status}", flush=True)
    print(f"output_dir={result.output_dir}", flush=True)
    print(f"diffusion_metrics_path={result.diffusion_metrics_path}", flush=True)
    print(f"domain_mask_path={result.domain_mask_path}", flush=True)
    print(f"concentration_map_path={result.concentration_map_path}", flush=True)
    print(f"mpc_config_path={result.mpc_config_path}", flush=True)
    print(f"obstacle_radius_matrix_path={result.obstacle_radius_matrix_path}", flush=True)
    print(f"obstacle_radius_map_path={result.obstacle_radius_map_path}", flush=True)
    print(f"obstacle_radius_histogram_path={result.obstacle_radius_histogram_path}", flush=True)
    print(
        f"simulation_box_visualization_path={result.simulation_box_visualization_path}",
        flush=True,
    )
    print(
        f"simulation_radius_top_view_path={result.simulation_radius_top_view_path}",
        flush=True,
    )
    print(
        "simulation_box_visualization_metadata_path="
        f"{result.simulation_box_visualization_metadata_path}",
        flush=True,
    )
    print(f"mpc_initial_particles_path={result.mpc_initial_particles_path}", flush=True)
    print(f"mpc_streamed_particles_path={result.mpc_streamed_particles_path}", flush=True)
    print(f"mpc_streaming_summary_path={result.mpc_streaming_summary_path}", flush=True)
    print(f"mpc_collided_particles_path={result.mpc_collided_particles_path}", flush=True)
    print(f"mpc_collision_summary_path={result.mpc_collision_summary_path}", flush=True)
    print(f"mpc_cell_collisions_path={result.mpc_cell_collisions_path}", flush=True)
    print(f"mpc_concentration_summary_path={result.mpc_concentration_summary_path}", flush=True)
    print(f"mpc_concentration_times_path={result.mpc_concentration_times_path}", flush=True)
    print(
        "mpc_concentration_representative_initial_map_path="
        f"{result.mpc_concentration_representative_initial_map_path}",
        flush=True,
    )
    print(
        "mpc_concentration_representative_final_map_path="
        f"{result.mpc_concentration_representative_final_map_path}",
        flush=True,
    )
    print(
        f"mpc_concentration_mean_initial_map_path={result.mpc_concentration_mean_initial_map_path}",
        flush=True,
    )
    print(
        f"mpc_concentration_mean_final_map_path={result.mpc_concentration_mean_final_map_path}",
        flush=True,
    )
    print(
        "mpc_high_concentration_mean_initial_map_path="
        f"{result.mpc_high_concentration_mean_initial_map_path}",
        flush=True,
    )
    print(
        "mpc_high_concentration_mean_final_map_path="
        f"{result.mpc_high_concentration_mean_final_map_path}",
        flush=True,
    )
    print(f"velocity_autocorrelation_path={result.velocity_autocorrelation_path}", flush=True)
    print(
        "velocity_autocorrelation_summary_path="
        f"{result.velocity_autocorrelation_summary_path}",
        flush=True,
    )
    print(
        "velocity_autocorrelation_realizations_path="
        f"{result.velocity_autocorrelation_realizations_path}",
        flush=True,
    )
    print(f"diffusion_metrics_json_path={result.diffusion_metrics_json_path}", flush=True)
    print(f"diffusion_metrics_tsv_path={result.diffusion_metrics_tsv_path}", flush=True)
    print(
        f"diffusion_metrics_summary_path={result.diffusion_metrics_summary_path}",
        flush=True,
    )
    print(f"simulation_log_path={result.simulation_log_path}", flush=True)
    print(f"worker_log_path={result.worker_log_path}", flush=True)
    return 0


def listen(args):
    flask_app = create_app()
    stop_requested = False
    processing_case = False

    def request_stop(signum, _frame):
        nonlocal stop_requested, processing_case
        stop_requested = True
        print(
            f"Senal {signum} recibida. El worker terminara al concluir el caso activo.",
            flush=True,
        )
        if not processing_case:
            raise WorkerShutdownRequested

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    print("Worker listo. Escuchando cola Redis de simulaciones.", flush=True)
    print(
        "Configuracion: "
        f"storage={flask_app.config['STORAGE_BACKEND']} "
        f"steps={flask_app.config['SIMULATION_DEFAULT_STEPS']} "
        f"realizations={flask_app.config['SIMULATION_DEFAULT_REALIZATIONS']} "
        f"labeled_particles={flask_app.config['SIMULATION_DEFAULT_LABELED_PARTICLES']} "
        f"cpu_threads={flask_app.config['SIMULATION_CPU_THREADS']} "
        f"timeout={'unlimited' if flask_app.config['SIMULATION_TIMEOUT_SECONDS'] is None else flask_app.config['SIMULATION_TIMEOUT_SECONDS']}",
        flush=True,
    )

    try:
        with flask_app.app_context():
            while not stop_requested:
                try:
                    case_id = pop_queued_case_id(
                        flask_app.config,
                        timeout_seconds=args.timeout,
                    )
                except SimulationQueueError as exc:
                    print(f"Error de cola: {exc}", file=sys.stderr, flush=True)
                    time.sleep(max(1, args.timeout))
                    continue

                if case_id is None:
                    continue

                print(f"Caso recibido desde Redis. case_id={case_id}", flush=True)
                processing_case = True
                try:
                    _process_case_id(case_id, flask_app)
                finally:
                    processing_case = False
                    db.session.remove()
    except WorkerShutdownRequested:
        pass
    finally:
        with flask_app.app_context():
            db.session.remove()

    print("Worker detenido de forma controlada.", flush=True)
    return 0


def idle(args):
    print(
        "Worker listo. Modo idle activo.",
        flush=True,
    )

    while True:
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
