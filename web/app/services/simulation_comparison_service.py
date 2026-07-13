import json
import math
from pathlib import Path


COMPARABLE_METRICS = (
    (
        "Difusión calculada (MDC)",
        "mdc",
        "Qué tan fácil se movieron las partículas dentro de la ROI simulada.",
    ),
    (
        "Referencia libre (MDC0)",
        "mdc0",
        "Valor esperado si no existieran obstáculos en el dominio.",
    ),
    (
        "Difusión normalizada (MDC*)",
        "mdc_star",
        "Relación entre la difusión calculada y la referencia libre.",
    ),
    (
        "Tiempo característico (tauC)",
        "characteristic_time",
        "Tiempo estimado en que Cv pierde memoria de la dirección inicial.",
    ),
    (
        "Desviación estándar de MDC",
        "mdc_standard_deviation",
        "Dispersión de MDC entre realizaciones independientes.",
    ),
    (
        "Error estándar de MDC",
        "mdc_standard_error",
        "Incertidumbre del MDC promedio entre realizaciones.",
    ),
    (
        "Desviación estándar de MDC*",
        "mdc_star_standard_deviation",
        "Dispersión de la difusión normalizada entre realizaciones.",
    ),
    (
        "Error estándar de MDC*",
        "mdc_star_standard_error",
        "Incertidumbre del promedio de difusión normalizada.",
    ),
)

REQUIRED_METRIC_KEYS = tuple(metric[1] for metric in COMPARABLE_METRICS)

COMPARABLE_PARAMETERS = (
    ("Pasos ejecutados", "steps"),
    ("Densidad media de partículas (n0)", "n0"),
    ("Paso temporal (tau)", "tau"),
    ("Energía térmica (kBT)", "kbt"),
    ("Masa por partícula", "mass"),
    ("Número de corridas", "realizations"),
    ("Partículas seguidas para Cv", "velocity_autocorrelation_labeled_particle_count"),
    ("Tiempos iniciales de Cv", "correlation_initial_times"),
    ("Ángulo de rotación MPC", "rotation_angle"),
    ("Política de rotación", "rotation_policy"),
    ("Tiempos de salida", "output_times"),
    ("Desplazamiento de grilla", "grid_shift_enabled"),
)

COMMON_MAPS = (
    (
        "simulation_box_3d",
        "Caja MPC y sección visualizada",
        "Compara la geometría reproducible usada para presentar celdas y obstáculos.",
    ),
    (
        "simulation_radius_top_view",
        "Radios por celda",
        "Compara el tamaño relativo de los obstáculos en una vista superior legible.",
    ),
    (
        "domain_mask",
        "Región usada por la simulación",
        "Compara qué zona de cada ROI se tomó como tejido válido.",
    ),
    (
        "obstacle_radius_map",
        "Obstáculos derivados del tejido",
        "Compara cómo se transformó la ROI en obstáculos del modelo.",
    ),
)


def is_case_mpc_comparable(results_dir: Path | None):
    if results_dir is None or not results_dir.exists():
        return False

    diffusion = _read_json(results_dir / "diffusion_metrics.json")

    return all(key in diffusion for key in REQUIRED_METRIC_KEYS)


def build_case_comparison(case_a, case_b, results_dir_a: Path | None, results_dir_b: Path | None):
    result_a = _build_case_result(case_a, results_dir_a)
    result_b = _build_case_result(case_b, results_dir_b)
    errors = []

    if not result_a["comparable"]:
        errors.append(f"El caso #{case_a.id} no tiene métricas MPC comparables.")

    if not result_b["comparable"]:
        errors.append(f"El caso #{case_b.id} no tiene métricas MPC comparables.")

    if case_a.id == case_b.id:
        errors.append("Selecciona dos casos diferentes para comparar.")

    compatibility_errors = _build_compatibility_errors(result_a, result_b)
    errors.extend(compatibility_errors)

    return {
        "available": not errors,
        "errors": tuple(errors),
        "case_a": result_a,
        "case_b": result_b,
        "metric_rows": _build_metric_rows(result_a, result_b),
        "parameter_rows": _build_parameter_rows(result_a, result_b),
        "map_pairs": _build_map_pairs(results_dir_a, results_dir_b),
        "compatible": not compatibility_errors,
        "compatibility_warnings": (),
        "trace_rows": _build_trace_rows(case_a, case_b, results_dir_a, results_dir_b),
    }


def _build_case_result(case, results_dir):
    if results_dir is None or not results_dir.exists():
        diffusion = {}
        config = {}
        metrics = {}
        results_path = "No registrada"
        diffusion_path = "No registrada"
    else:
        diffusion = _read_json(results_dir / "diffusion_metrics.json")
        config = _read_json(results_dir / "mpc_config.json")
        metrics = {}
        results_path = str(results_dir)
        diffusion_path = str(results_dir / "diffusion_metrics.json")

    return {
        "id": case.id,
        "status": case.status,
        "created_at": case.created_at,
        "results_path": results_path,
        "metrics_path": diffusion_path,
        "comparable": all(key in diffusion for key in REQUIRED_METRIC_KEYS),
        "diffusion": diffusion,
        "config": config,
        "metrics": metrics,
    }


def _build_metric_rows(result_a, result_b):
    rows = []

    for label, key, description in COMPARABLE_METRICS:
        value_a = _numeric_value(result_a["diffusion"].get(key))
        value_b = _numeric_value(result_b["diffusion"].get(key))
        delta = _calculate_delta(value_a, value_b)

        rows.append(
            {
                "label": label,
                "description": description,
                "case_a": _format_number(value_a),
                "case_b": _format_number(value_b),
                "delta": _format_signed_number(delta["absolute"]),
                "relative_delta": _format_percent(delta["relative"]),
            }
        )

    return tuple(rows)


def _build_parameter_rows(result_a, result_b):
    rows = []

    for label, key in COMPARABLE_PARAMETERS:
        value_a = _first_present(result_a["config"], result_a["diffusion"], key)
        value_b = _first_present(result_b["config"], result_b["diffusion"], key)

        if value_a in (None, "") and value_b in (None, ""):
            continue

        rows.append(
            {
                "label": label,
                "case_a": _format_raw_value(value_a),
                "case_b": _format_raw_value(value_b),
                "matches": _format_raw_value(value_a) == _format_raw_value(value_b),
            }
        )

    return tuple(rows)


def _build_map_pairs(results_dir_a, results_dir_b):
    if results_dir_a is None or results_dir_b is None:
        return ()

    map_pairs = []

    for key, title, description in COMMON_MAPS:
        if _result_image_exists(results_dir_a, key) and _result_image_exists(
            results_dir_b,
            key,
        ):
            map_pairs.append(
                {
                    "key": key,
                    "title": title,
                    "description": description,
                }
            )

    concentration_key = _select_common_concentration_key(results_dir_a, results_dir_b)
    if concentration_key is not None:
        map_pairs.append(
            {
                "key": concentration_key,
                "title": "Concentración MPC comparable",
                "description": (
                    "Muestra la distribución de partículas capturada en un "
                    "tiempo común para ambos casos."
                ),
            }
        )

    return tuple(map_pairs)


def _select_common_concentration_key(results_dir_a, results_dir_b):
    times_a = _read_captured_times(results_dir_a)
    times_b = _read_captured_times(results_dir_b)
    common_times = sorted(set(times_a).intersection(times_b))

    for time_value in reversed(common_times):
        key = f"mpc_concentration_mean_t_{time_value}"
        if _result_image_exists(results_dir_a, key) and _result_image_exists(
            results_dir_b,
            key,
        ):
            return key

    for fallback_key in (
        "mpc_concentration_mean_final",
        "mpc_concentration_mean_initial",
    ):
        if _result_image_exists(results_dir_a, fallback_key) and _result_image_exists(
            results_dir_b,
            fallback_key,
        ):
            return fallback_key

    return None


def _build_compatibility_errors(result_a, result_b):
    missing = []
    different = []

    for label, key in COMPARABLE_PARAMETERS:
        value_a = _first_present(result_a["config"], result_a["diffusion"], key)
        value_b = _first_present(result_b["config"], result_b["diffusion"], key)
        if value_a in (None, "") or value_b in (None, ""):
            missing.append(label)
        elif not _values_match(value_a, value_b):
            different.append(label)

    errors = []
    if missing:
        errors.append(
            "No se puede garantizar una comparación reproducible porque faltan "
            "parámetros en uno de los casos: " + ", ".join(missing) + "."
        )
    if different:
        errors.append(
            "Los casos no son compatibles: deben procesarse con la misma "
            "configuración. Parámetros diferentes: " + ", ".join(different) + "."
        )

    return tuple(errors)


def _build_trace_rows(case_a, case_b, results_dir_a, results_dir_b):
    results_path_a = str(results_dir_a) if results_dir_a is not None else "No registrada"
    results_path_b = str(results_dir_b) if results_dir_b is not None else "No registrada"
    diffusion_path_a = (
        str(results_dir_a / "diffusion_metrics.json")
        if results_dir_a is not None
        else "No registrada"
    )
    diffusion_path_b = (
        str(results_dir_b / "diffusion_metrics.json")
        if results_dir_b is not None
        else "No registrada"
    )

    return (
        {
            "label": "ID del caso",
            "case_a": str(case_a.id),
            "case_b": str(case_b.id),
        },
        {
            "label": "Fecha de carga",
            "case_a": _format_datetime(case_a.created_at),
            "case_b": _format_datetime(case_b.created_at),
        },
        {
            "label": "Modalidad",
            "case_a": case_a.input_mode,
            "case_b": case_b.input_mode,
        },
        {
            "label": "Entrada PGM",
            "case_a": case_a.simulation_input_file_path or "No registrada",
            "case_b": case_b.simulation_input_file_path or "No registrada",
        },
        {
            "label": "Carpeta de resultados",
            "case_a": results_path_a,
            "case_b": results_path_b,
        },
        {
            "label": "Metricas de difusion",
            "case_a": diffusion_path_a,
            "case_b": diffusion_path_b,
        },
    )


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return {}


def _read_key_value_file(path):
    values = {}

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values

    for line in lines:
        if not line or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

    return values


def _read_captured_times(results_dir):
    summary = _read_key_value_file(results_dir / "mpc_concentration_summary.txt")
    raw_times = summary.get("captured_output_times", "")
    captured_times = []

    for raw_time in raw_times.split(","):
        try:
            captured_times.append(int(raw_time.strip()))
        except ValueError:
            continue

    return tuple(captured_times)


def _result_image_exists(results_dir, key):
    if key.startswith("mpc_concentration_mean_t_"):
        filename = f"{key}.pgm"
    else:
        filename = {
            "simulation_box_3d": "simulation_box_3d.png",
            "simulation_radius_top_view": "simulation_radius_top_view.png",
            "domain_mask": "domain_mask.pgm",
            "obstacle_radius_map": "obstacle_radius_map.pgm",
            "mpc_concentration_mean_initial": "mpc_concentration_mean_initial.pgm",
            "mpc_concentration_mean_final": "mpc_concentration_mean_final.pgm",
        }.get(key)

    return bool(filename and (results_dir / filename).exists())


def _first_present(primary, secondary, key):
    value = primary.get(key)
    if value not in (None, ""):
        return value

    value = secondary.get(key)
    if value not in (None, ""):
        return value

    return None


def _values_match(value_a, value_b):
    if isinstance(value_a, (list, tuple)) or isinstance(value_b, (list, tuple)):
        if not isinstance(value_a, (list, tuple)) or not isinstance(value_b, (list, tuple)):
            return False
        return tuple(value_a) == tuple(value_b)

    numeric_a = _numeric_value(value_a)
    numeric_b = _numeric_value(value_b)
    if numeric_a is not None and numeric_b is not None:
        return math.isclose(numeric_a, numeric_b, rel_tol=1.0e-12, abs_tol=1.0e-12)

    return str(value_a).strip().lower() == str(value_b).strip().lower()


def _calculate_delta(value_a, value_b):
    if value_a is None or value_b is None:
        return {"absolute": None, "relative": None}

    absolute = value_b - value_a
    relative = None if value_a == 0 else absolute / abs(value_a)

    return {"absolute": absolute, "relative": relative}


def _numeric_value(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_number(value):
    if value is None:
        return "No disponible"

    if value == 0:
        return "0"

    if abs(value) >= 1000:
        return f"{value:,.0f}".replace(",", ".")

    if abs(value) < 0.001:
        return f"{value:.3e}"

    return f"{value:.5g}"


def _format_signed_number(value):
    if value is None:
        return "No disponible"

    sign = "+" if value > 0 else ""
    return f"{sign}{_format_number(value)}"


def _format_percent(value):
    if value is None:
        return "No disponible"

    sign = "+" if value > 0 else ""
    return f"{sign}{value * 100:.2f}%"


def _format_raw_value(value):
    if value in (None, ""):
        return "No disponible"

    numeric = _numeric_value(value)
    if numeric is not None:
        return _format_number(numeric)

    return str(value)


def _format_datetime(value):
    if value is None:
        return "No registrada"

    return value.strftime("%Y-%m-%d %H:%M:%S")
