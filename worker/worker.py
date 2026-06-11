import argparse
from pathlib import Path
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
    process_parser.add_argument("--density", type=float, default=None)

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
            density=args.density,
        )


def _process_case_id(case_id, flask_app, *, seed=None, steps=None, density=None):
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
            density=density,
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
    print(f"metrics_path={result.metrics_path}", flush=True)
    print(f"domain_mask_path={result.domain_mask_path}", flush=True)
    print(f"density_map_path={result.density_map_path}", flush=True)
    print(f"simulation_log_path={result.simulation_log_path}", flush=True)
    print(f"worker_log_path={result.worker_log_path}", flush=True)
    return 0


def listen(args):
    flask_app = create_app()
    print("Worker listo. Escuchando cola Redis de simulaciones.", flush=True)

    with flask_app.app_context():
        while True:
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
            _process_case_id(case_id, flask_app)
            db.session.remove()


def idle(args):
    print(
        "Worker listo. Modo idle activo.",
        flush=True,
    )

    while True:
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
