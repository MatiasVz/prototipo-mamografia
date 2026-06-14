import csv
import json
import re
from pathlib import Path


STATIC_RESULT_IMAGES = {
    "simulation_box_3d": {
        "filename": "simulation_box_3d.png",
        "title": "Caja de simulacion mesoscopica",
        "description": (
            "Representacion pseudo-3D de la caja plana construida desde la ROI, "
            "con cilindros derivados de intensidades y una muestra de particulas."
        ),
        "reading": (
            "Esta imagen no es una reconstruccion anatomica 3D real; muestra el "
            "dominio artificial que usa el simulador para explicar la transformacion "
            "de la imagen en celdas, obstaculos y particulas."
        ),
    },
    "domain_mask": {
        "filename": "domain_mask.pgm",
        "title": "Region usada por la simulacion",
        "description": (
            "Muestra que parte de la ROI fue considerada tejido valido y separa "
            "esa zona del fondo externo."
        ),
        "reading": (
            "Las zonas claras forman el dominio donde se permite simular; las "
            "zonas oscuras corresponden al fondo o a regiones excluidas."
        ),
    },
    "obstacle_radius_map": {
        "filename": "obstacle_radius_map.pgm",
        "title": "Obstaculos derivados del tejido",
        "description": (
            "Muestra como las intensidades claras y oscuras de la ROI se "
            "tradujeron en obstaculos para el modelo MPC."
        ),
        "reading": (
            "Las variaciones de gris representan diferencias del tejido que el "
            "modelo convierte en obstaculos para las particulas."
        ),
    },
    "density_map": {
        "filename": "density_map.pgm",
        "title": "Mapa de visitas de particulas",
        "description": (
            "Indica por donde pasaron o se acumularon mas particulas durante "
            "la simulacion."
        ),
        "reading": (
            "Las zonas mas claras tuvieron mas visitas de particulas; las zonas "
            "oscuras recibieron menos visitas o quedaron fuera del dominio."
        ),
    },
    "mpc_concentration_initial": {
        "filename": "mpc_concentration_initial.pgm",
        "title": "Concentracion al inicio",
        "description": "Distribucion de particulas al comenzar la simulacion.",
        "reading": "Sirve como punto de partida para comparar como cambia la distribucion.",
    },
    "mpc_concentration_final": {
        "filename": "mpc_concentration_final.pgm",
        "title": "Concentracion al final",
        "description": "Distribucion de particulas despues de ejecutar la simulacion.",
        "reading": "Permite observar hacia donde se desplazaron o acumularon las particulas.",
    },
    "mpc_high_concentration_initial": {
        "filename": "mpc_high_concentration_initial.pgm",
        "title": "Zonas mas concentradas al inicio",
        "description": "Marca las celdas con mayor acumulacion inicial de particulas.",
        "reading": "Los puntos claros senalan las zonas con concentracion superior al umbral.",
    },
    "mpc_high_concentration_final": {
        "filename": "mpc_high_concentration_final.pgm",
        "title": "Zonas mas concentradas al final",
        "description": "Marca las celdas con mayor acumulacion final de particulas.",
        "reading": "Ayuda a comparar si las zonas de mayor acumulacion cambiaron con el tiempo.",
    },
}

RESULT_CONCEPTS = (
    {
        "term": "MDC",
        "meaning": (
            "Coeficiente de difusion calculado desde el movimiento de las particulas. "
            "En simple, resume que tan facil se movieron dentro de la ROI."
        ),
    },
    {
        "term": "MDC0",
        "meaning": (
            "Referencia teorica sin obstaculos. Funciona como una comparacion contra "
            "un espacio libre ideal."
        ),
    },
    {
        "term": "MDC*",
        "meaning": (
            "Relacion entre MDC y MDC0. Si vale 0.30, la movilidad simulada equivale "
            "aproximadamente al 30% de la referencia libre."
        ),
    },
    {
        "term": "Cv",
        "meaning": (
            "Mide la memoria del movimiento. Valores positivos indican que las "
            "particulas conservan direccion; valores cercanos a cero indican perdida "
            "de memoria por choques y cambios de direccion."
        ),
    },
)

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
    interpretation_items = _build_interpretation_items(metrics, config, diffusion)
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
        "interpretation_items": interpretation_items,
        "concept_items": RESULT_CONCEPTS,
        "explanation": (
            "La ROI funciona como el terreno de la simulacion. Sus intensidades "
            "se convierten en obstaculos y las particulas MPC se mueven dentro "
            "de ese espacio para estimar como cambia la difusion."
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
        "interpretation_items": (),
        "concept_items": RESULT_CONCEPTS,
        "explanation": "",
    }


def _build_domain_maps(results_dir):
    return tuple(
        _build_image_card(results_dir, key)
        for key in ("simulation_box_3d", "domain_mask", "obstacle_radius_map", "density_map")
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
                        "Distribucion de particulas capturada en este momento "
                        "de la simulacion."
                    ),
                    "reading": (
                        "Permite ver si la concentracion se mantiene, se dispersa "
                        "o se acumula en una zona de la ROI."
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
        "reading": definition["reading"],
    }


def _build_interpretation_items(metrics, config, diffusion):
    items = []
    mdc = _float_or_none(diffusion.get("mdc"))
    mdc0 = _float_or_none(diffusion.get("mdc0"))
    mdc_star = _float_or_none(diffusion.get("mdc_star"))
    particle_count = _float_or_none(config.get("mpc_particle_count"))
    obstacle_collisions = _float_or_none(
        config.get("mpc_streaming_obstacle_collision_count"),
    )
    domain_boundary_collisions = _float_or_none(
        config.get("mpc_streaming_domain_boundary_collision_count"),
    )
    steps = _float_or_none(config.get("steps") or metrics.get("steps"))

    if mdc_star is not None:
        items.append(
            {
                "label": "Lectura de MDC*",
                "detail": (
                    "La movilidad simulada fue aproximadamente "
                    f"{_format_percent_value(mdc_star)} de la referencia libre. "
                    "Mientras menor sea este valor, mas restringido fue el movimiento "
                    "de las particulas frente al caso sin obstaculos."
                ),
            }
        )

    if mdc is not None and mdc0 is not None:
        items.append(
            {
                "label": "Comparacion con espacio libre",
                "detail": (
                    f"El MDC calculado fue {_format_value(mdc, 'decimal')} y la "
                    f"referencia libre fue {_format_value(mdc0, 'decimal')}. "
                    "Esta diferencia resume el efecto de los obstaculos creados "
                    "desde la ROI."
                ),
            }
        )

    if obstacle_collisions is not None and particle_count is not None:
        items.append(
            {
                "label": "Choques durante la corrida",
                "detail": (
                    "Se registraron "
                    f"{_format_value(obstacle_collisions, 'integer')} rebotes contra "
                    f"obstaculos con {_format_value(particle_count, 'integer')} "
                    "particulas simuladas. Estos choques son parte del mecanismo que "
                    "reduce o desvia la difusion."
                ),
            }
        )

    if domain_boundary_collisions is not None:
        items.append(
            {
                "label": "Respeto de la region mamaria",
                "detail": (
                    "El simulador registro "
                    f"{_format_value(domain_boundary_collisions, 'integer')} rebotes contra "
                    "el borde de la ROI. Esos rebotes evitan que las particulas se muestren "
                    "como concentracion valida sobre el fondo externo de la mamografia."
                ),
            }
        )

    if steps is not None:
        items.append(
            {
                "label": "Alcance temporal",
                "detail": (
                    f"La simulacion avanzo {_format_value(steps, 'integer')} pasos. "
                    "Mas pasos permiten observar una evolucion mas larga, aunque "
                    "tambien aumentan el tiempo de procesamiento."
                ),
            }
        )

    return tuple(items)


def _build_primary_metrics(metrics, config, diffusion):
    return tuple(
        item
        for item in (
            _metric(
                "Difusion calculada (MDC)",
                diffusion.get("mdc"),
                "Resume que tan facil se movieron las particulas dentro de la ROI.",
            ),
            _metric(
                "Referencia libre (MDC0)",
                diffusion.get("mdc0"),
                "Valor teorico si no existieran obstaculos que frenen el movimiento.",
            ),
            _metric(
                "Difusion normalizada (MDC*)",
                diffusion.get("mdc_star"),
                "Compara la difusion del caso frente a la referencia libre.",
            ),
            _metric(
                "Variacion entre corridas",
                diffusion.get("mdc_standard_deviation"),
                "Indica cuanto cambiaron los valores MDC entre realizaciones.",
            ),
            _metric(
                "Particulas simuladas",
                config.get("mpc_particle_count"),
                "Elementos matematicos usados para representar movimiento en la ROI.",
                value_type="integer",
            ),
            _metric(
                "Pasos ejecutados",
                config.get("steps") or metrics.get("steps"),
                "Cantidad de iteraciones que avanzo el simulador.",
                value_type="integer",
            ),
            _metric(
                "Choques con obstaculos",
                config.get("mpc_streaming_obstacle_collision_count"),
                "Rebotes registrados contra obstaculos derivados de la imagen.",
                value_type="integer",
            ),
            _metric(
                "Rebotes con borde de ROI",
                config.get("mpc_streaming_domain_boundary_collision_count"),
                "Intentos de salida del dominio mamario que fueron contenidos por la mascara.",
                value_type="integer",
            ),
        )
        if item is not None
    )


def _build_parameter_items(metrics, config, diffusion):
    return tuple(
        item
        for item in (
            _metric(
                "Densidad media de particulas (n0)",
                config.get("n0") or diffusion.get("n0"),
                "Cantidad promedio de particulas simuladas por cada celda.",
            ),
            _metric(
                "Paso temporal (tau)",
                config.get("tau") or diffusion.get("tau"),
                "Avance de tiempo aplicado en cada iteracion del simulador.",
            ),
            _metric(
                "Energia termica (kBT)",
                config.get("kbt") or diffusion.get("kbt"),
                "Controla la intensidad del movimiento aleatorio de las particulas.",
            ),
            _metric(
                "Masa por particula",
                config.get("mass") or diffusion.get("mass"),
                "Valor matematico asignado al peso de cada particula simulada.",
            ),
            _metric(
                "Semilla de simulacion",
                config.get("seed") or metrics.get("seed"),
                "Numero usado para repetir una corrida con condiciones comparables.",
                value_type="integer",
            ),
            _metric(
                "Numero de corridas",
                config.get("realizations") or diffusion.get("realizations"),
                "Cantidad de ejecuciones usadas para calcular o promediar resultados.",
                value_type="integer",
            ),
            _metric(
                "Particulas solicitadas para Cv",
                config.get("velocity_autocorrelation_requested_labeled_particles")
                or config.get("labeled_particles")
                or diffusion.get("requested_labeled_particles"),
                "Cantidad objetivo indicada para calcular la autocorrelacion de velocidades.",
                value_type="integer",
            ),
            _metric(
                "Particulas usadas para Cv",
                config.get("velocity_autocorrelation_labeled_particle_count")
                or diffusion.get("labeled_particle_count"),
                "Cantidad realmente seguida; si la ROI tiene menos particulas, se usa el total disponible.",
                value_type="integer",
            ),
            _metric(
                "Angulo de rotacion MPC",
                config.get("rotation_angle"),
                "Define como se modifican las velocidades durante la colision MPC.",
            ),
        )
        if item is not None
    )


def _build_velocity_summary(summary):
    return tuple(
        item
        for item in (
            _metric(
                "Difusion calculada (MDC)",
                summary.get("mdc"),
                "Resultado obtenido al integrar la autocorrelacion de velocidades.",
            ),
            _metric(
                "Tiempo caracteristico",
                summary.get("characteristic_time"),
                "Tiempo de referencia estimado desde la curva Cv.",
            ),
            _metric(
                "Particulas solicitadas para Cv",
                summary.get("requested_labeled_particles"),
                "Cantidad objetivo configurada para observar la memoria del movimiento.",
                value_type="integer",
            ),
            _metric(
                "Particulas usadas para Cv",
                summary.get("labeled_particle_count"),
                "Muestra real usada para calcular Cv y MDC.",
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
                        "meaning": _interpret_cv(row.get("cv")),
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


def _float_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_percent_value(value):
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "No disponible"


def _interpret_cv(value):
    numeric_value = _float_or_none(value)

    if numeric_value is None:
        return "No disponible"

    if numeric_value > 0.1:
        return "Conserva parte de la direccion inicial"

    if numeric_value < -0.1:
        return "Cambio fuerte de direccion"

    return "Memoria del movimiento casi perdida"


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
