from dataclasses import dataclass
from pathlib import Path
import subprocess

from ..extensions import db
from ..models import CaseStatus
from .storage_service import (
    get_case_simulation_results_directory,
    get_case_upload_directory,
    to_relative_storage_path,
)


class SimulationWorkerError(RuntimeError):
    pass


@dataclass
class SimulationWorkerResult:
    case_id: int
    status: str
    command: list[str]
    return_code: int
    output_dir: Path
    metrics_path: Path
    domain_mask_path: Path
    density_map_path: Path
    mpc_config_path: Path
    obstacle_radius_matrix_path: Path
    obstacle_radius_map_path: Path
    obstacle_radius_histogram_path: Path
    mpc_initial_particles_path: Path
    mpc_streamed_particles_path: Path
    mpc_streaming_summary_path: Path
    mpc_collided_particles_path: Path
    mpc_collision_summary_path: Path
    mpc_cell_collisions_path: Path
    mpc_concentration_summary_path: Path
    mpc_concentration_times_path: Path
    mpc_concentration_initial_map_path: Path
    mpc_concentration_final_map_path: Path
    mpc_high_concentration_initial_map_path: Path
    mpc_high_concentration_final_map_path: Path
    simulation_log_path: Path
    worker_log_path: Path
    stdout: str
    stderr: str


def process_case_simulation(
    case,
    app_config,
    *,
    seed=None,
    steps=None,
    density=None,
):
    upload_folder = app_config["UPLOAD_FOLDER"]
    input_path = _resolve_simulation_input_path(case, upload_folder)
    output_dir = get_case_simulation_results_directory(case.id, upload_folder)
    output_dir.mkdir(parents=True, exist_ok=True)

    worker_log_path = output_dir / "worker_execution.log"
    command = _build_julia_command(
        app_config,
        input_path,
        output_dir,
        seed=seed,
        steps=steps,
        density=density,
    )

    _mark_case_processing(case)
    db.session.commit()

    try:
        completed_process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=int(app_config["SIMULATION_TIMEOUT_SECONDS"]),
            check=False,
        )
    except FileNotFoundError as exc:
        message = "No se encontro el ejecutable de Julia configurado."
        _write_worker_log(worker_log_path, command, None, "", message)
        _mark_case_error(case, message)
        db.session.commit()
        raise SimulationWorkerError(message) from exc
    except subprocess.TimeoutExpired as exc:
        message = "La ejecucion del simulador Julia supero el tiempo maximo configurado."
        stdout = _safe_process_output(exc.stdout)
        stderr = _safe_process_output(exc.stderr)
        _write_worker_log(worker_log_path, command, None, stdout, message + "\n" + stderr)
        _mark_case_error(case, message)
        db.session.commit()
        raise SimulationWorkerError(message) from exc

    _write_worker_log(
        worker_log_path,
        command,
        completed_process.returncode,
        completed_process.stdout,
        completed_process.stderr,
    )

    if completed_process.returncode != 0:
        message = (
            "El simulador Julia finalizo con codigo "
            f"{completed_process.returncode}. Revisa worker_execution.log."
        )
        _mark_case_error(case, message)
        db.session.commit()
        raise SimulationWorkerError(message)

    result_paths = _get_expected_result_paths(output_dir)
    try:
        _ensure_result_files_exist(result_paths)
    except SimulationWorkerError as exc:
        _mark_case_error(case, str(exc))
        db.session.commit()
        raise

    _update_case_simulation_results(case, output_dir, result_paths)
    db.session.commit()

    return SimulationWorkerResult(
        case_id=case.id,
        status=case.status,
        command=command,
        return_code=completed_process.returncode,
        output_dir=output_dir,
        metrics_path=result_paths["metrics"],
        domain_mask_path=result_paths["domain_mask"],
        density_map_path=result_paths["density_map"],
        mpc_config_path=result_paths["mpc_config"],
        obstacle_radius_matrix_path=result_paths["obstacle_radius_matrix"],
        obstacle_radius_map_path=result_paths["obstacle_radius_map"],
        obstacle_radius_histogram_path=result_paths["obstacle_radius_histogram"],
        mpc_initial_particles_path=result_paths["mpc_initial_particles"],
        mpc_streamed_particles_path=result_paths["mpc_streamed_particles"],
        mpc_streaming_summary_path=result_paths["mpc_streaming_summary"],
        mpc_collided_particles_path=result_paths["mpc_collided_particles"],
        mpc_collision_summary_path=result_paths["mpc_collision_summary"],
        mpc_cell_collisions_path=result_paths["mpc_cell_collisions"],
        mpc_concentration_summary_path=result_paths["mpc_concentration_summary"],
        mpc_concentration_times_path=result_paths["mpc_concentration_times"],
        mpc_concentration_initial_map_path=result_paths["mpc_concentration_initial_map"],
        mpc_concentration_final_map_path=result_paths["mpc_concentration_final_map"],
        mpc_high_concentration_initial_map_path=result_paths[
            "mpc_high_concentration_initial_map"
        ],
        mpc_high_concentration_final_map_path=result_paths[
            "mpc_high_concentration_final_map"
        ],
        simulation_log_path=result_paths["simulation_log"],
        worker_log_path=worker_log_path,
        stdout=completed_process.stdout,
        stderr=completed_process.stderr,
    )


def _build_julia_command(app_config, input_path, output_dir, *, seed, steps, density):
    simulation_seed = app_config["SIMULATION_DEFAULT_SEED"] if seed is None else seed
    simulation_steps = app_config["SIMULATION_DEFAULT_STEPS"] if steps is None else steps
    simulation_density = (
        app_config["SIMULATION_DEFAULT_DENSITY"] if density is None else density
    )

    return [
        app_config["JULIA_EXECUTABLE"],
        f"--project={app_config['SIMULATOR_PROJECT_PATH']}",
        app_config["SIMULATOR_RUN_SCRIPT_PATH"],
        "--input",
        str(input_path),
        "--output",
        str(output_dir),
        "--seed",
        str(simulation_seed),
        "--steps",
        str(simulation_steps),
        "--density",
        str(simulation_density),
        "--n0",
        str(app_config["SIMULATION_DEFAULT_N0"]),
        "--mass",
        str(app_config["SIMULATION_DEFAULT_MASS"]),
        "--kbt",
        str(app_config["SIMULATION_DEFAULT_KBT"]),
        "--tau",
        str(app_config["SIMULATION_DEFAULT_TAU"]),
        "--rotation-angle",
        str(app_config["SIMULATION_DEFAULT_ROTATION_ANGLE"]),
        "--realizations",
        str(app_config["SIMULATION_DEFAULT_REALIZATIONS"]),
        "--labeled-particles",
        str(app_config["SIMULATION_DEFAULT_LABELED_PARTICLES"]),
        "--output-times",
        app_config["SIMULATION_DEFAULT_OUTPUT_TIMES"],
        "--grid-shift",
        app_config["SIMULATION_GRID_SHIFT_ENABLED"],
    ]


def _resolve_simulation_input_path(case, upload_folder):
    _ensure_case_can_be_processed(case)

    stored_path = Path(case.simulation_input_file_path)

    if stored_path.is_absolute():
        input_path = stored_path
    else:
        direct_path = Path.cwd() / stored_path
        if direct_path.exists():
            input_path = direct_path
        else:
            input_path = get_case_upload_directory(case.id, upload_folder) / stored_path.name

    if not input_path.exists():
        raise SimulationWorkerError(
            "No se encontro el archivo PGM de entrada para la simulacion."
        )

    return input_path


def _ensure_case_can_be_processed(case):
    if case.status == CaseStatus.PROCESSING:
        raise SimulationWorkerError("El caso ya se encuentra en procesamiento.")

    if not case.simulation_input_file_path:
        raise SimulationWorkerError(
            "El caso no tiene archivo PGM preparado para la simulacion."
        )


def _mark_case_processing(case):
    case.status = CaseStatus.PROCESSING
    case.error_message = None
    case.simulation_results_path = None
    case.simulation_metrics_file_path = None
    case.simulation_density_map_file_path = None
    case.simulation_log_file_path = None


def _mark_case_error(case, message):
    case.status = CaseStatus.ERROR
    case.error_message = message


def _update_case_simulation_results(case, output_dir, result_paths):
    case.status = CaseStatus.COMPLETED
    case.error_message = None
    case.simulation_results_path = to_relative_storage_path(output_dir)
    case.simulation_metrics_file_path = to_relative_storage_path(result_paths["metrics"])
    case.simulation_density_map_file_path = to_relative_storage_path(
        result_paths["density_map"],
    )
    case.simulation_log_file_path = to_relative_storage_path(
        result_paths["simulation_log"],
    )


def _get_expected_result_paths(output_dir):
    return {
        "metrics": output_dir / "metrics.json",
        "domain_mask": output_dir / "domain_mask.pgm",
        "density_map": output_dir / "density_map.pgm",
        "mpc_config": output_dir / "mpc_config.json",
        "obstacle_radius_matrix": output_dir / "obstacle_radius_matrix.tsv",
        "obstacle_radius_map": output_dir / "obstacle_radius_map.pgm",
        "obstacle_radius_histogram": output_dir / "obstacle_radius_histogram.tsv",
        "mpc_initial_particles": output_dir / "mpc_initial_particles.tsv",
        "mpc_streamed_particles": output_dir / "mpc_streamed_particles.tsv",
        "mpc_streaming_summary": output_dir / "mpc_streaming_summary.txt",
        "mpc_collided_particles": output_dir / "mpc_collided_particles.tsv",
        "mpc_collision_summary": output_dir / "mpc_collision_summary.txt",
        "mpc_cell_collisions": output_dir / "mpc_cell_collisions.tsv",
        "mpc_concentration_summary": output_dir / "mpc_concentration_summary.txt",
        "mpc_concentration_times": output_dir / "mpc_concentration_times.tsv",
        "mpc_concentration_initial_map": output_dir / "mpc_concentration_initial.pgm",
        "mpc_concentration_final_map": output_dir / "mpc_concentration_final.pgm",
        "mpc_high_concentration_initial_map": output_dir
        / "mpc_high_concentration_initial.pgm",
        "mpc_high_concentration_final_map": output_dir
        / "mpc_high_concentration_final.pgm",
        "simulation_log": output_dir / "simulation.log",
    }


def _ensure_result_files_exist(result_paths):
    missing_files = [
        path.name for path in result_paths.values()
        if not path.exists()
    ]

    if missing_files:
        raise SimulationWorkerError(
            "La simulacion finalizo, pero faltan archivos de resultado: "
            + ", ".join(missing_files)
        )


def _write_worker_log(path, command, return_code, stdout, stderr):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as log_file:
        log_file.write("MammographySimulationWorker\n")
        log_file.write(f"command={' '.join(command)}\n")
        log_file.write(f"return_code={return_code if return_code is not None else ''}\n")
        log_file.write("\n[stdout]\n")
        log_file.write(stdout or "")
        log_file.write("\n\n[stderr]\n")
        log_file.write(stderr or "")


def _safe_process_output(value):
    if value is None:
        return ""

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    return str(value)
