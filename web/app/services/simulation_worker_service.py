from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from ..extensions import db
from ..models import CaseStatus, Result
from .case_notification_service import notify_case_completed
from .storage_service import (
    get_case_simulation_results_directory,
    get_case_upload_directory,
    to_relative_storage_path,
)


class SimulationWorkerError(RuntimeError):
    def __init__(self, message, *, category="worker_error", technical_message=None):
        super().__init__(message)
        self.category = category
        self.user_message = message
        self.technical_message = technical_message or message


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
    simulation_box_visualization_path: Path
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
    velocity_autocorrelation_path: Path
    velocity_autocorrelation_summary_path: Path
    velocity_autocorrelation_realizations_path: Path
    diffusion_metrics_json_path: Path
    diffusion_metrics_tsv_path: Path
    diffusion_metrics_summary_path: Path
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
    output_dir = get_case_simulation_results_directory(case.id, upload_folder)
    output_dir.mkdir(parents=True, exist_ok=True)
    worker_log_path, latest_worker_log_path = _build_worker_log_paths(output_dir)

    try:
        input_path = _resolve_simulation_input_path(case, upload_folder)
        _validate_pgm_input_file(input_path)
        _ensure_runtime_configuration(
            app_config,
            steps=steps,
            density=density,
        )
        command = _build_julia_command(
            app_config,
            input_path,
            output_dir,
            seed=seed,
            steps=steps,
            density=density,
        )
    except SimulationWorkerError as exc:
        _write_worker_logs(
            worker_log_path,
            latest_worker_log_path,
            [],
            None,
            "",
            "",
            status="error",
            error_category=exc.category,
            error_message=exc.technical_message,
            timeout_seconds=_get_process_timeout(app_config),
            app_config=app_config,
        )
        _mark_case_error(case, exc.user_message, output_dir=output_dir)
        db.session.commit()
        raise

    _mark_case_processing(case, output_dir)
    db.session.commit()

    try:
        timeout_seconds = _get_process_timeout(app_config)
        completed_process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        message = "No se encontro el ejecutable de Julia configurado."
        _write_worker_logs(
            worker_log_path,
            latest_worker_log_path,
            command,
            None,
            "",
            message,
            status="error",
            error_category="julia_executable",
            error_message=str(exc),
            timeout_seconds=_get_process_timeout(app_config),
            app_config=app_config,
        )
        _mark_case_error(case, message)
        db.session.commit()
        raise SimulationWorkerError(message, category="julia_executable") from exc
    except subprocess.TimeoutExpired as exc:
        message = "La ejecucion del simulador Julia supero el tiempo maximo configurado."
        stdout = _safe_process_output(exc.stdout)
        stderr = _safe_process_output(exc.stderr)
        _write_worker_logs(
            worker_log_path,
            latest_worker_log_path,
            command,
            None,
            stdout,
            stderr,
            status="error",
            error_category="timeout",
            error_message=message,
            timeout_seconds=_get_process_timeout(app_config),
            app_config=app_config,
        )
        _mark_case_error(case, message)
        db.session.commit()
        raise SimulationWorkerError(message, category="timeout") from exc

    _write_worker_logs(
        worker_log_path,
        latest_worker_log_path,
        command,
        completed_process.returncode,
        completed_process.stdout,
        completed_process.stderr,
        status="completed" if completed_process.returncode == 0 else "error",
        error_category="" if completed_process.returncode == 0 else "julia_failure",
        error_message="" if completed_process.returncode == 0 else completed_process.stderr,
        timeout_seconds=_get_process_timeout(app_config),
        app_config=app_config,
    )

    if completed_process.returncode != 0:
        message = (
            "El simulador Julia finalizo con codigo "
            f"{completed_process.returncode}. Revisa worker_execution.log."
        )
        _mark_case_error(case, message)
        db.session.commit()
        raise SimulationWorkerError(
            message,
            category="julia_failure",
            technical_message=completed_process.stderr,
        )

    result_paths = _get_expected_result_paths(output_dir)
    try:
        _ensure_result_files_exist(result_paths)
    except SimulationWorkerError as exc:
        _append_worker_log_error(worker_log_path, exc.category, exc.technical_message)
        _append_worker_log_error(
            latest_worker_log_path,
            exc.category,
            exc.technical_message,
        )
        _mark_case_error(case, exc.user_message)
        db.session.commit()
        raise

    _update_case_simulation_results(case, output_dir, result_paths)
    db.session.commit()
    notify_case_completed(case)

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
        simulation_box_visualization_path=result_paths["simulation_box_visualization"],
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
        velocity_autocorrelation_path=result_paths["velocity_autocorrelation"],
        velocity_autocorrelation_summary_path=result_paths[
            "velocity_autocorrelation_summary"
        ],
        velocity_autocorrelation_realizations_path=result_paths[
            "velocity_autocorrelation_realizations"
        ],
        diffusion_metrics_json_path=result_paths["diffusion_metrics_json"],
        diffusion_metrics_tsv_path=result_paths["diffusion_metrics_tsv"],
        diffusion_metrics_summary_path=result_paths["diffusion_metrics_summary"],
        simulation_log_path=result_paths["simulation_log"],
        worker_log_path=worker_log_path,
        stdout=completed_process.stdout,
        stderr=completed_process.stderr,
    )


def _build_worker_log_paths(output_dir):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return output_dir / f"worker_execution_{run_id}.log", output_dir / "worker_execution.log"


def _build_julia_command(app_config, input_path, output_dir, *, seed, steps, density):
    simulation_seed = app_config["SIMULATION_DEFAULT_SEED"] if seed is None else seed
    simulation_steps = app_config["SIMULATION_DEFAULT_STEPS"] if steps is None else steps
    simulation_density = (
        app_config["SIMULATION_DEFAULT_DENSITY"] if density is None else density
    )

    return [
        app_config["JULIA_EXECUTABLE"],
        f"--threads={app_config['SIMULATION_CPU_THREADS']}",
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
        "--correlation-initial-times",
        str(app_config["SIMULATION_CORRELATION_INITIAL_TIMES"]),
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
            "No se encontro el archivo PGM de entrada para la simulacion.",
            category="missing_input_file",
            technical_message=f"simulation_input_file_path={case.simulation_input_file_path}",
        )

    return input_path


def _validate_pgm_input_file(input_path):
    try:
        content = input_path.read_bytes()
    except OSError as exc:
        raise SimulationWorkerError(
            "No se pudo leer el archivo PGM de entrada para la simulacion.",
            category="missing_input_file",
            technical_message=str(exc),
        ) from exc

    try:
        tokens, payload_start = _extract_pgm_header_tokens(content)
    except UnicodeDecodeError as exc:
        raise SimulationWorkerError(
            "El archivo PGM de entrada tiene una cabecera ilegible.",
            category="invalid_pgm",
            technical_message=str(exc),
        ) from exc

    if len(tokens) < 4:
        raise SimulationWorkerError(
            "El archivo PGM de entrada esta incompleto.",
            category="invalid_pgm",
            technical_message=f"path={input_path}",
        )

    magic, width_text, height_text, max_value_text = tokens

    if magic not in {"P2", "P5"}:
        raise SimulationWorkerError(
            "El archivo PGM de entrada debe estar en formato P2 o P5.",
            category="invalid_pgm",
            technical_message=f"magic={magic}",
        )

    try:
        width = int(width_text)
        height = int(height_text)
        max_value = int(max_value_text)
    except ValueError as exc:
        raise SimulationWorkerError(
            "La cabecera PGM contiene dimensiones o intensidad maxima invalidas.",
            category="invalid_pgm",
            technical_message=f"header={tokens}",
        ) from exc

    if width <= 0 or height <= 0 or max_value <= 0:
        raise SimulationWorkerError(
            "La cabecera PGM no define una caja de simulacion valida.",
            category="invalid_pgm",
            technical_message=(
                f"width={width}, height={height}, max_value={max_value}"
            ),
        )

    expected_pixels = width * height

    if magic == "P5":
        bytes_per_pixel = 1 if max_value < 256 else 2
        available_bytes = len(content) - payload_start
        expected_bytes = expected_pixels * bytes_per_pixel

        if available_bytes < expected_bytes:
            raise SimulationWorkerError(
                "El archivo PGM binario no contiene todos los pixeles esperados.",
                category="invalid_pgm",
                technical_message=(
                    f"available_bytes={available_bytes}, expected_bytes={expected_bytes}"
                ),
            )
        return

    value_count = 0

    try:
        for token in _iter_ascii_pgm_value_tokens(content[payload_start:]):
            value = int(token)
            if value < 0 or value > max_value:
                raise ValueError(f"value={value}, max_value={max_value}")
            value_count += 1
    except (UnicodeDecodeError, ValueError) as exc:
        raise SimulationWorkerError(
            "El archivo PGM ASCII contiene pixeles invalidos.",
            category="invalid_pgm",
            technical_message=str(exc),
        ) from exc

    if value_count < expected_pixels:
        raise SimulationWorkerError(
            "El archivo PGM ASCII no contiene todos los pixeles esperados.",
            category="invalid_pgm",
            technical_message=(
                f"value_count={value_count}, expected_pixels={expected_pixels}"
            ),
        )


def _extract_pgm_header_tokens(content):
    tokens = []
    index = 0

    while len(tokens) < 4 and index < len(content):
        index = _skip_pgm_whitespace_and_comments(content, index)
        start = index

        while index < len(content) and content[index] not in b" \t\r\n":
            index += 1

        if start == index:
            break

        tokens.append(content[start:index].decode("ascii"))

    payload_start = _skip_pgm_whitespace_and_comments(content, index)
    return tokens, payload_start


def _skip_pgm_whitespace_and_comments(content, index):
    while index < len(content):
        current = content[index]

        if current in b" \t\r\n":
            index += 1
            continue

        if current == ord("#"):
            while index < len(content) and content[index] not in b"\r\n":
                index += 1
            continue

        break

    return index


def _iter_ascii_pgm_value_tokens(payload):
    text = payload.decode("ascii")

    for line in text.splitlines():
        line = line.split("#", 1)[0]
        for token in line.split():
            yield token


def _ensure_case_can_be_processed(case):
    if case.status == CaseStatus.PROCESSING:
        raise SimulationWorkerError(
            "El caso ya se encuentra en procesamiento.",
            category="invalid_state",
        )

    if not case.roi_file_path:
        raise SimulationWorkerError(
            "El caso debe tener una ROI asociada y confirmada antes de simular.",
            category="missing_roi",
        )

    if not case.simulation_input_file_path:
        raise SimulationWorkerError(
            "El caso no tiene archivo PGM preparado para la simulacion.",
            category="missing_pgm",
        )

    if case.status not in {CaseStatus.ROI_CONFIRMED, CaseStatus.PENDING, CaseStatus.ERROR}:
        raise SimulationWorkerError(
            "El caso debe tener la ROI confirmada antes de ejecutar la simulacion.",
            category="invalid_state",
        )


def _ensure_runtime_configuration(app_config, *, steps, density):
    simulator_project_path = Path(app_config["SIMULATOR_PROJECT_PATH"])
    simulator_run_script_path = Path(app_config["SIMULATOR_RUN_SCRIPT_PATH"])

    if not simulator_project_path.exists():
        raise SimulationWorkerError(
            "No se encontro el proyecto Julia del simulador.",
            category="runtime_config",
            technical_message=f"SIMULATOR_PROJECT_PATH={simulator_project_path}",
        )

    if not simulator_run_script_path.exists():
        raise SimulationWorkerError(
            "No se encontro el script Julia de ejecucion del simulador.",
            category="runtime_config",
            technical_message=f"SIMULATOR_RUN_SCRIPT_PATH={simulator_run_script_path}",
        )

    simulation_steps = app_config["SIMULATION_DEFAULT_STEPS"] if steps is None else steps
    simulation_density = (
        app_config["SIMULATION_DEFAULT_DENSITY"] if density is None else density
    )

    _ensure_positive_int("SIMULATION_DEFAULT_STEPS", simulation_steps)
    _ensure_positive_float("SIMULATION_DEFAULT_DENSITY", simulation_density)
    _ensure_positive_float("SIMULATION_DEFAULT_N0", app_config["SIMULATION_DEFAULT_N0"])
    _ensure_positive_float("SIMULATION_DEFAULT_MASS", app_config["SIMULATION_DEFAULT_MASS"])
    _ensure_positive_float("SIMULATION_DEFAULT_KBT", app_config["SIMULATION_DEFAULT_KBT"])
    _ensure_positive_float("SIMULATION_DEFAULT_TAU", app_config["SIMULATION_DEFAULT_TAU"])
    _ensure_positive_int(
        "SIMULATION_DEFAULT_REALIZATIONS",
        app_config["SIMULATION_DEFAULT_REALIZATIONS"],
    )
    _ensure_positive_int(
        "SIMULATION_DEFAULT_LABELED_PARTICLES",
        app_config["SIMULATION_DEFAULT_LABELED_PARTICLES"],
    )
    _ensure_positive_int(
        "SIMULATION_CORRELATION_INITIAL_TIMES",
        app_config["SIMULATION_CORRELATION_INITIAL_TIMES"],
    )
    _ensure_non_negative_output_times(app_config["SIMULATION_DEFAULT_OUTPUT_TIMES"])


def _ensure_positive_int(name, value):
    try:
        parsed_value = int(value)
    except (TypeError, ValueError) as exc:
        raise SimulationWorkerError(
            "La configuracion minima del simulador contiene parametros invalidos.",
            category="invalid_parameters",
            technical_message=f"{name}={value}",
        ) from exc

    if parsed_value <= 0:
        raise SimulationWorkerError(
            "La configuracion minima del simulador contiene parametros invalidos.",
            category="invalid_parameters",
            technical_message=f"{name}={value}",
        )


def _ensure_positive_float(name, value):
    try:
        parsed_value = float(value)
    except (TypeError, ValueError) as exc:
        raise SimulationWorkerError(
            "La configuracion minima del simulador contiene parametros invalidos.",
            category="invalid_parameters",
            technical_message=f"{name}={value}",
        ) from exc

    if parsed_value <= 0:
        raise SimulationWorkerError(
            "La configuracion minima del simulador contiene parametros invalidos.",
            category="invalid_parameters",
            technical_message=f"{name}={value}",
        )


def _ensure_non_negative_output_times(value):
    try:
        output_times = [
            int(token.strip())
            for token in str(value).split(",")
            if token.strip()
        ]
    except ValueError as exc:
        raise SimulationWorkerError(
            "Los tiempos de salida configurados para la simulacion son invalidos.",
            category="invalid_parameters",
            technical_message=f"SIMULATION_DEFAULT_OUTPUT_TIMES={value}",
        ) from exc

    if not output_times or any(output_time < 0 for output_time in output_times):
        raise SimulationWorkerError(
            "Los tiempos de salida configurados para la simulacion son invalidos.",
            category="invalid_parameters",
            technical_message=f"SIMULATION_DEFAULT_OUTPUT_TIMES={value}",
        )


def _mark_case_processing(case, output_dir):
    case.status = CaseStatus.PROCESSING
    case.error_message = None
    if not case.simulation_results_path:
        case.simulation_results_path = to_relative_storage_path(output_dir)


def _mark_case_error(case, message, *, output_dir=None):
    case.status = CaseStatus.ERROR
    case.error_message = message
    if output_dir is not None and not case.simulation_results_path:
        case.simulation_results_path = to_relative_storage_path(output_dir)


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
    _store_diffusion_metrics(case, result_paths)


def _store_diffusion_metrics(case, result_paths):
    """Persistir las metricas de difusion (MDC, MDC0, MDC*) en la tabla results.

    Lee los valores que el simulador ya calculo en diffusion_metrics.json y los
    guarda en la base de datos. Es tolerante a fallos: si el archivo falta o no se
    puede parsear, no interrumpe el cierre del caso (los archivos ya estan en disco).
    """
    diffusion = _read_diffusion_metrics(result_paths.get("diffusion_metrics_json"))

    if diffusion is None:
        return

    result = case.result
    if result is None:
        result = Result()
        case.result = result

    result.mdc = _metric_to_float(diffusion.get("mdc"))
    result.mdc0 = _metric_to_float(diffusion.get("mdc0"))
    result.mdc_star = _metric_to_float(diffusion.get("mdc_star"))
    result.mdc_standard_deviation = _metric_to_float(
        diffusion.get("mdc_standard_deviation"),
    )


def _read_diffusion_metrics(path):
    if path is None or not Path(path).exists():
        return None

    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _metric_to_float(value):
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_expected_result_paths(output_dir):
    return {
        "metrics": output_dir / "metrics.json",
        "domain_mask": output_dir / "domain_mask.pgm",
        "density_map": output_dir / "density_map.pgm",
        "mpc_config": output_dir / "mpc_config.json",
        "obstacle_radius_matrix": output_dir / "obstacle_radius_matrix.tsv",
        "obstacle_radius_map": output_dir / "obstacle_radius_map.pgm",
        "obstacle_radius_histogram": output_dir / "obstacle_radius_histogram.tsv",
        "simulation_box_visualization": output_dir / "simulation_box_3d.png",
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
        "velocity_autocorrelation": output_dir / "velocity_autocorrelation.tsv",
        "velocity_autocorrelation_summary": output_dir
        / "velocity_autocorrelation_summary.txt",
        "velocity_autocorrelation_realizations": output_dir
        / "velocity_autocorrelation_realizations.tsv",
        "diffusion_metrics_json": output_dir / "diffusion_metrics.json",
        "diffusion_metrics_tsv": output_dir / "diffusion_metrics.tsv",
        "diffusion_metrics_summary": output_dir / "diffusion_metrics_summary.txt",
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
            + ", ".join(missing_files),
            category="missing_results",
            technical_message="missing_files=" + ",".join(missing_files),
        )


def _get_process_timeout(app_config):
    timeout_seconds = app_config.get("SIMULATION_TIMEOUT_SECONDS")

    if timeout_seconds in (None, "", 0, "0"):
        return None

    timeout_seconds = int(timeout_seconds)

    if timeout_seconds <= 0:
        return None

    return timeout_seconds


def _write_worker_logs(
    path,
    latest_path,
    command,
    return_code,
    stdout,
    stderr,
    *,
    status,
    error_category,
    error_message,
    timeout_seconds,
    app_config,
):
    content = _build_worker_log_content(
        path,
        command,
        return_code,
        stdout,
        stderr,
        status=status,
        error_category=error_category,
        error_message=error_message,
        timeout_seconds=timeout_seconds,
        app_config=app_config,
    )

    for log_path in {path, latest_path}:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(content, encoding="utf-8")


def _build_worker_log_content(
    path,
    command,
    return_code,
    stdout,
    stderr,
    *,
    status,
    error_category,
    error_message,
    timeout_seconds,
    app_config,
):
    generated_at = datetime.now(timezone.utc).isoformat()
    simulator_config = _build_log_config_summary(app_config)
    path.parent.mkdir(parents=True, exist_ok=True)
    structured_log = {
        "generated_at": generated_at,
        "run_log_path": str(path),
        "status": status,
        "error_category": error_category,
        "error_message": error_message or "",
        "timeout_seconds": timeout_seconds,
        "timeout_enabled": timeout_seconds is not None,
        "command": command,
        "return_code": return_code,
        "simulator_config": simulator_config,
        "stdout": stdout or "",
        "stderr": stderr or "",
    }

    lines = [
        "MammographySimulationWorker\n",
        f"generated_at={generated_at}\n",
        f"run_log_path={path}\n",
        f"status={status}\n",
        f"error_category={error_category or ''}\n",
        f"error_message={error_message or ''}\n",
        (
            "timeout_seconds="
            f"{timeout_seconds if timeout_seconds is not None else 'unlimited'}\n"
        ),
        f"command={' '.join(command)}\n",
        f"return_code={return_code if return_code is not None else ''}\n",
        "\n[simulator_config]\n",
    ]

    for key, value in simulator_config.items():
        lines.append(f"{key}={value}\n")

    lines.extend(
        [
            "\n[stdout]\n",
            stdout or "",
            "\n\n[stderr]\n",
            stderr or "",
            "\n\n[structured_json]\n",
            json.dumps(structured_log, indent=2, ensure_ascii=False),
            "\n",
        ]
    )

    return "".join(lines)


def _build_log_config_summary(app_config):
    return {
        "julia_executable": app_config["JULIA_EXECUTABLE"],
        "simulator_project_path": app_config["SIMULATOR_PROJECT_PATH"],
        "simulator_run_script_path": app_config["SIMULATOR_RUN_SCRIPT_PATH"],
        "simulator_version": _read_simulator_version(app_config),
        "simulation_default_seed": app_config["SIMULATION_DEFAULT_SEED"],
        "simulation_default_steps": app_config["SIMULATION_DEFAULT_STEPS"],
        "simulation_default_density": app_config["SIMULATION_DEFAULT_DENSITY"],
        "simulation_default_n0": app_config["SIMULATION_DEFAULT_N0"],
        "simulation_default_mass": app_config["SIMULATION_DEFAULT_MASS"],
        "simulation_default_kbt": app_config["SIMULATION_DEFAULT_KBT"],
        "simulation_default_tau": app_config["SIMULATION_DEFAULT_TAU"],
        "simulation_default_rotation_angle": app_config[
            "SIMULATION_DEFAULT_ROTATION_ANGLE"
        ],
        "simulation_default_realizations": app_config[
            "SIMULATION_DEFAULT_REALIZATIONS"
        ],
        "simulation_default_labeled_particles": app_config[
            "SIMULATION_DEFAULT_LABELED_PARTICLES"
        ],
        "simulation_correlation_initial_times": app_config[
            "SIMULATION_CORRELATION_INITIAL_TIMES"
        ],
        "simulation_default_output_times": app_config[
            "SIMULATION_DEFAULT_OUTPUT_TIMES"
        ],
        "simulation_grid_shift_enabled": app_config["SIMULATION_GRID_SHIFT_ENABLED"],
    }


def _read_simulator_version(app_config):
    project_toml_path = Path(app_config["SIMULATOR_PROJECT_PATH"]) / "Project.toml"

    try:
        for line in project_toml_path.read_text(encoding="utf-8").splitlines():
            normalized_line = line.strip()
            if normalized_line.startswith("version"):
                return normalized_line.split("=", 1)[1].strip().strip('"')
    except OSError:
        return "No registrada"

    return "No registrada"


def _append_worker_log_error(path, error_category, error_message):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as log_file:
        log_file.write("\n[post_validation_error]\n")
        log_file.write(f"error_category={error_category}\n")
        log_file.write(f"error_message={error_message}\n")


def _safe_process_output(value):
    if value is None:
        return ""

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    return str(value)
