import csv
import json
import re
from pathlib import Path


STATIC_RESULT_IMAGES = {
    "domain_mask": {
        "filename": "domain_mask.pgm",
        "title": "Region mamaria valida",
        "description": (
            "Muestra la caja plana usada por el simulador y separa la region "
            "mamaria del fondo externo."
        ),
    },
    "obstacle_radius_map": {
        "filename": "obstacle_radius_map.pgm",
        "title": "Radios de obstaculos",
        "description": (
            "Resume como las intensidades PGM se transformaron en obstaculos "
            "cilindricos del dominio mesoscopico."
        ),
    },
    "density_map": {
        "filename": "density_map.pgm",
        "title": "Mapa de densidad preliminar",
        "description": (
            "Representa la acumulacion de visitas o particulas sobre la ROI "
            "durante la corrida."
        ),
    },
    "mpc_concentration_initial": {
        "filename": "mpc_concentration_initial.pgm",
        "title": "Concentracion inicial",
        "description": "Particulas por celda al inicio de la simulacion MPC.",
    },
    "mpc_concentration_final": {
        "filename": "mpc_concentration_final.pgm",
        "title": "Concentracion final",
        "description": "Particulas por celda al final de la simulacion MPC.",
    },
    "mpc_high_concentration_initial": {
        "filename": "mpc_high_concentration_initial.pgm",
        "title": "Zonas altas iniciales",
        "description": "Celdas que superan el umbral de concentracion al inicio.",
    },
    "mpc_high_concentration_final": {
        "filename": "mpc_high_concentration_final.pgm",
        "title": "Zonas altas finales",
        "description": "Celdas que superan el umbral de concentracion al final.",
    },
}

CONCENTRATION_KEY_PATTERN = re.compile(r"^mpc_concentration_t_(\d+)$")


def build_mpc_results_view(results_dir: Path | None):
    if results_dir is None or not results_dir.exists():
        return _empty_results_view()

    metrics = _read_json(results_dir / "metrics.json")
    config = _read_json(results_dir / "mpc_config.json")
    diffusion = _read_json(results_dir / "diffusion_metrics.json")
    concentration_summary = _read_key_value_file(
        results_dir / "mpc_concentration_summary.txt",
    )
    velocity_summary = _read_key_value_file(
        results_dir / "velocity_autocorrelation_summary.txt",
    )

    domain_maps = _build_domain_maps(results_dir)
    concentration_maps = _build_concentration_maps(results_dir, concentration_summary)
    primary_metrics = _build_primary_metrics(metrics, config, diffusion)
    parameter_items = _build_parameter_items(metrics, config, diffusion)
    autocorrelation_rows = _read_autocorrelation_rows(
        results_dir / "velocity_autocorrelation.tsv",
    )
    technical_files = _build_technical_files(results_dir)
    velocity_summary_items = _build_velocity_summary(velocity_summary)
    has_advanced_outputs = bool(
        config
        or diffusion
        or concentration_summary
        or velocity_summary
        or autocorrelation_rows
        or concentration_maps
        or [result_map for result_map in domain_maps if result_map["key"] != "density_map"]
    )

    return {
        "available": has_advanced_outputs,
        "primary_metrics": primary_metrics,
        "parameter_items": parameter_items,
        "domain_maps": domain_maps,
        "concentration_maps": concentration_maps,
        "autocorrelation_rows": autocorrelation_rows,
        "technical_files": technical_files,
        "velocity_summary": velocity_summary_items,
        "explanation": (
            "Los obstaculos cilindricos representan heterogeneidad del tejido: "
            "cada intensidad de la ROI en PGM se convierte en un radio dentro "
            "de una caja plana de simulacion."
        ),
    }


def get_result_image_path(results_dir: Path, result_key: str):
    static_definition = STATIC_RESULT_IMAGES.get(result_key)

    if static_definition is not None:
        return results_dir / static_definition["filename"]

    match = CONCENTRATION_KEY_PATTERN.match(result_key)
    if match:
        return results_dir / f"mpc_concentration_t_{match.group(1)}.pgm"

    return None


def _empty_results_view():
    return {
        "available": False,
        "primary_metrics": (),
        "parameter_items": (),
        "domain_maps": (),
        "concentration_maps": (),
        "autocorrelation_rows": (),
        "technical_files": (),
        "velocity_summary": (),
        "explanation": "",
    }


def _build_domain_maps(results_dir):
    return tuple(
        _build_image_card(results_dir, key)
        for key in ("domain_mask", "obstacle_radius_map", "density_map")
        if get_result_image_path(results_dir, key).exists()
    )


def _build_concentration_maps(results_dir, concentration_summary):
    captured_times = _parse_int_csv(concentration_summary.get("captured_output_times"))
    maps = []

    for time_value in captured_times:
        key = f"mpc_concentration_t_{time_value}"
        path = get_result_image_path(results_dir, key)

        if path is not None and path.exists():
            maps.append(
                {
                    "key": key,
                    "title": f"Concentracion t={time_value}",
                    "description": (
                        "Particulas por celda capturadas en este tiempo de "
                        "simulacion."
                    ),
                }
            )

    if not maps:
        maps.extend(
            _build_image_card(results_dir, key)
            for key in (
                "mpc_concentration_initial",
                "mpc_concentration_final",
            )
            if get_result_image_path(results_dir, key).exists()
        )

    maps.extend(
        _build_image_card(results_dir, key)
        for key in (
            "mpc_high_concentration_initial",
            "mpc_high_concentration_final",
        )
        if get_result_image_path(results_dir, key).exists()
    )

    return tuple(maps)


def _build_image_card(results_dir, key):
    definition = STATIC_RESULT_IMAGES[key]
    return {
        "key": key,
        "title": definition["title"],
        "description": definition["description"],
    }


def _build_primary_metrics(metrics, config, diffusion):
    return tuple(
        item
        for item in (
            _metric("MDC", diffusion.get("mdc"), "Coeficiente calculado por Green-Kubo."),
            _metric("MDC0", diffusion.get("mdc0"), "Referencia teorica sin obstaculos."),
            _metric(
                "MDC*",
                diffusion.get("mdc_star"),
                "MDC normalizado para comparar corridas.",
            ),
            _metric(
                "Particulas MPC",
                config.get("mpc_particle_count"),
                "Particulas continuas usadas en la simulacion.",
                value_type="integer",
            ),
            _metric(
                "Pasos",
                config.get("steps") or metrics.get("steps"),
                "Iteraciones ejecutadas por el simulador.",
                value_type="integer",
            ),
            _metric(
                "Choques con obstaculos",
                config.get("mpc_streaming_obstacle_collision_count"),
                "Rebotes registrados contra obstaculos cilindricos.",
                value_type="integer",
            ),
        )
        if item is not None
    )


def _build_parameter_items(metrics, config, diffusion):
    return tuple(
        item
        for item in (
            _metric("n0", config.get("n0") or diffusion.get("n0"), "Densidad media."),
            _metric("tau", config.get("tau") or diffusion.get("tau"), "Paso temporal."),
            _metric("kBT", config.get("kbt") or diffusion.get("kbt"), "Energia termica."),
            _metric("Masa", config.get("mass") or diffusion.get("mass"), "Masa por particula."),
            _metric(
                "Semilla",
                config.get("seed") or metrics.get("seed"),
                "Valor usado para reproducibilidad.",
                value_type="integer",
            ),
            _metric(
                "Realizaciones",
                config.get("realizations") or diffusion.get("realizations"),
                "Corridas usadas para promediar metricas.",
                value_type="integer",
            ),
            _metric(
                "Particulas etiquetadas",
                config.get("velocity_autocorrelation_labeled_particle_count")
                or diffusion.get("labeled_particle_count"),
                "Particulas seguidas para calcular Cv.",
                value_type="integer",
            ),
            _metric(
                "Angulo de rotacion",
                config.get("rotation_angle"),
                "Parametro de colision MPC.",
            ),
        )
        if item is not None
    )


def _build_velocity_summary(summary):
    return tuple(
        item
        for item in (
            _metric("MDC", summary.get("mdc"), "Integral de la autocorrelacion."),
            _metric(
                "Tiempo caracteristico",
                summary.get("characteristic_time"),
                "Referencia temporal estimada desde Cv.",
            ),
            _metric(
                "Particulas etiquetadas",
                summary.get("labeled_particle_count"),
                "Particulas usadas en la muestra.",
                value_type="integer",
            ),
        )
        if item is not None
    )


def _build_technical_files(results_dir):
    definitions = (
        ("Configuracion MPC", "mpc_config.json"),
        ("Resumen del espacio", "space_summary.txt"),
        ("Radios por celda", "obstacle_radius_matrix.tsv"),
        ("Histograma de radios", "obstacle_radius_histogram.tsv"),
        ("Concentracion por tiempo", "mpc_concentration_times.tsv"),
        ("Autocorrelacion Cv", "velocity_autocorrelation.tsv"),
        ("Metricas de difusion", "diffusion_metrics.json"),
        ("Log de simulacion", "simulation.log"),
    )
    files = []

    for label, filename in definitions:
        path = results_dir / filename
        if path.exists():
            files.append({"label": label, "path": str(path)})

    return tuple(files)


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


def _read_autocorrelation_rows(path, limit=8):
    try:
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file, delimiter="\t")
            rows = []

            for row in reader:
                rows.append(
                    {
                        "lag": _format_value(row.get("lag"), "integer"),
                        "time": _format_value(row.get("time"), "decimal"),
                        "cv": _format_value(row.get("cv"), "decimal"),
                    }
                )

                if len(rows) >= limit:
                    break

            return tuple(rows)
    except OSError:
        return ()


def _parse_int_csv(value):
    if not value:
        return ()

    parsed = []
    for raw_item in str(value).split(","):
        try:
            parsed.append(int(raw_item.strip()))
        except ValueError:
            continue

    return tuple(parsed)


def _metric(label, value, hint, value_type="decimal"):
    if value in (None, ""):
        return None

    return {
        "label": label,
        "value": _format_value(value, value_type),
        "hint": hint,
    }


def _format_value(value, value_type):
    if value in (None, ""):
        return "No disponible"

    if value_type == "integer":
        try:
            return f"{int(float(value)):,}".replace(",", ".")
        except (TypeError, ValueError):
            return str(value)

    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    if number == 0:
        return "0"

    if abs(number) >= 1000:
        return f"{number:,.0f}".replace(",", ".")

    if abs(number) < 0.001:
        return f"{number:.3e}"

    return f"{number:.4g}"
