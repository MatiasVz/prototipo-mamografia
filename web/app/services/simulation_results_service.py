import csv
import json
import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


STATIC_RESULT_IMAGES = {
    "velocity_autocorrelation_chart": {
        "filename": "velocity_autocorrelation_chart.png",
        "title": "Memoria del movimiento (Cv)",
        "description": (
            "Evolucion normalizada de la memoria de velocidad y ajuste exponencial "
            "usado para estimar el tiempo caracteristico tauC."
        ),
        "reading": (
            "La curva azul muestra el resultado MPC promedio. La curva roja es el "
            "ajuste exp(-t/tauC): una caida mas rapida indica que las particulas "
            "pierden antes la memoria de su direccion inicial."
        ),
        "legend": (
            "Azul: Cv normalizada calculada",
            "Rojo: ajuste exponencial exp(-t/tauC)",
            "Linea gris: referencia Cv=0",
        ),
    },
    "simulation_box_3d": {
        "filename": "simulation_box_3d.png",
        "title": "Caja de simulacion mesoscopica",
        "description": (
            "Seccion reproducible de la caja MPC con celdas, radios reales de "
            "obstaculos y una muestra de particulas con sus direcciones."
        ),
        "reading": (
            "Esta imagen no es una reconstruccion anatomica 3D real; muestra el "
            "dominio artificial del simulador. Cuando la ROI es grande se presenta "
            "una seccion reproducible con diversidad de radios para evitar oclusion; "
            "el calculo siempre utiliza el dominio mamario completo."
        ),
        "legend": (
            "Lineas azules: celdas",
            "Cilindros grises: obstaculos; oscuro mayor, claro menor",
            "Puntos negros: particulas MPC",
            "Lineas verdes: direccion de movimiento",
        ),
    },
    "simulation_radius_top_view": {
        "filename": "simulation_radius_top_view.png",
        "title": "Radios por celda",
        "description": (
            "Vista superior de la misma seccion de la caja. El diametro de cada "
            "circulo corresponde al radio calculado para ese obstaculo."
        ),
        "reading": (
            "Esta vista complementa la perspectiva pseudo-3D para que las diferencias "
            "de tamano sean comparables sin modificar la geometria simulada."
        ),
        "legend": (
            "Cuadricula clara: celdas del dominio",
            "Circulos grandes y oscuros: intensidades menores",
            "Circulos pequenos y claros: intensidades mayores",
            "Celdas oscuras: fondo fuera del dominio",
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
            "Las zonas claras son el tejido que entra al modelo. Las zonas "
            "oscuras representan fondo externo o regiones que se excluyen para "
            "que la simulacion no se ejecute fuera de la mama."
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
            "En el modelo, los tonos mas oscuros de la ROI tienden a generar "
            "cilindros mas grandes y los tonos mas claros cilindros mas pequenos. "
            "Esos cilindros no son tumores: son obstaculos matematicos que "
            "representan la heterogeneidad del tejido."
        ),
    },
    "mpc_concentration_representative_final": {
        "filename": "mpc_concentration_representative_final.pgm",
        "title": "Realizacion representativa final",
        "description": "Conteo final de particulas de una corrida MPC real.",
        "reading": "Resume la distribucion final sin mezclar realizaciones.",
    },
    "mpc_concentration_representative_initial": {
        "filename": "mpc_concentration_representative_initial.pgm",
        "title": "Realizacion representativa inicial",
        "description": "Conteo inicial de particulas de una corrida MPC real.",
        "reading": "Es el punto de partida de la realizacion representativa.",
    },
    "mpc_concentration_mean_initial": {
        "filename": "mpc_concentration_mean_initial.pgm",
        "title": "Concentracion promedio inicial",
        "description": "Promedio inicial entre todas las realizaciones MPC.",
        "reading": "Resume la tendencia inicial de las corridas configuradas.",
    },
    "mpc_concentration_mean_final": {
        "filename": "mpc_concentration_mean_final.pgm",
        "title": "Concentracion promedio final",
        "description": "Promedio final entre todas las realizaciones MPC.",
        "reading": "Resume la tendencia final de las corridas configuradas.",
    },
}

RESULT_CONCEPTS = (
    {
        "term": "MDC",
        "meaning": (
            "Coeficiente de difusion calculado desde el movimiento de las particulas. "
            "En simple, resume que tan facil pudieron moverse dentro de la ROI "
            "simulada."
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
            "aproximadamente al 30% de la referencia libre. Sirve para comparar "
            "casos o corridas en una misma escala."
        ),
    },
    {
        "term": "Cv",
        "meaning": (
            "Autocorrelacion de velocidades. En palabras sencillas, observa si "
            "las particulas siguen moviendose parecido a como empezaron o si "
            "los choques hicieron que perdieran esa direccion inicial."
        ),
    },
    {
        "term": "tauC",
        "meaning": (
            "Tiempo caracteristico estimado desde la caida inicial de Cv. Resume "
            "cuanto tarda el movimiento en perder memoria de su direccion inicial."
        ),
    },
    {
        "term": "Incertidumbre entre realizaciones",
        "meaning": (
            "La desviacion estandar describe cuanto variaron las corridas; el "
            "error estandar expresa la incertidumbre del promedio calculado."
        ),
    },
    {
        "term": "Mapas de concentracion",
        "meaning": (
            "Imagenes que muestran donde habia mas particulas en distintos "
            "momentos. Ayudan a ver si el movimiento se distribuye o se concentra "
            "en ciertas zonas de la ROI."
        ),
    },
    {
        "term": "Zonas altas",
        "meaning": (
            "Celdas que superan un umbral de concentracion. No significan lesion "
            "ni diagnostico; solo indican puntos donde el modelo acumulo mas "
            "particulas."
        ),
    },
)

RESULT_READING_STEPS = (
    {
        "number": "1",
        "label": "ROI",
        "caption": "Regi\u00f3n que se analiza",
        "detail": (
            "Es el recorte de mamograf\u00eda que se usa como zona de trabajo. El "
            "prototipo analiza esta regi\u00f3n, no toda la imagen cl\u00ednica."
        ),
    },
    {
        "number": "2",
        "label": "Caja y cilindros",
        "caption": "Modelo del tejido",
        "detail": (
            "La ROI se convierte en una caja de simulaci\u00f3n. Cada zona de gris "
            "ayuda a definir obst\u00e1culos cil\u00edndricos: oscuros m\u00e1s grandes, claros "
            "m\u00e1s peque\u00f1os, seg\u00fan el modelo del art\u00edculo base."
        ),
    },
    {
        "number": "3",
        "label": "Part\u00edculas MPC",
        "caption": "Movimiento simulado",
        "detail": (
            "El simulador coloca part\u00edculas matem\u00e1ticas dentro de la caja. Al "
            "moverse, chocar y cambiar de direcci\u00f3n, dejan evidencia de c\u00f3mo se "
            "comporta la difusi\u00f3n en esa ROI."
        ),
    },
    {
        "number": "4",
        "label": "Mapas",
        "caption": "Distribuci\u00f3n observada",
        "detail": (
            "Los mapas no son una nueva mamograf\u00eda. Son representaciones del "
            "comportamiento de la simulaci\u00f3n: dominio v\u00e1lido, obst\u00e1culos, concentraci\u00f3n "
            "y visitas de part\u00edculas."
        ),
    },
    {
        "number": "5",
        "label": "M\u00e9tricas",
        "caption": "Resultados comparables",
        "detail": (
            "MDC, MDC* y Cv resumen el movimiento en n\u00fameros para compararlo de "
            "forma acad\u00e9mica. No clasifican lesiones ni entregan diagn\u00f3stico."
        ),
    },
)

CONCENTRATION_KEY_PATTERN = re.compile(
    r"^mpc_concentration_(representative|mean|scientific)_t_(\d+)$",
)
HIGH_CONCENTRATION_KEY_PATTERN = re.compile(r"^mpc_high_concentration_mean_t_(\d+)$")


def build_mpc_results_view(results_dir: Path | None):
    if results_dir is None or not results_dir.exists():
        return _empty_results_view()

    metrics = {}
    config = _read_json(results_dir / "mpc_config.json")
    diffusion = _read_json(results_dir / "diffusion_metrics.json")
    concentration_summary = _read_key_value_file(
        results_dir / "mpc_concentration_summary.txt",
    )
    velocity_summary = _read_key_value_file(
        results_dir / "velocity_autocorrelation_summary.txt",
    )

    domain_maps = _build_domain_maps(results_dir)
    concentration_maps = _build_concentration_maps(
        results_dir,
        concentration_summary,
        config,
    )
    primary_metrics = _build_primary_metrics(metrics, config, diffusion)
    parameter_items = _build_parameter_items(metrics, config, diffusion)
    autocorrelation_rows = _read_autocorrelation_rows(
        results_dir / "velocity_autocorrelation.tsv",
    )
    autocorrelation_chart = _build_autocorrelation_chart(
        results_dir,
        velocity_summary,
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
        or autocorrelation_chart
        or concentration_maps
        or domain_maps
    )

    return {
        "available": has_advanced_outputs,
        "primary_metrics": primary_metrics,
        "parameter_items": parameter_items,
        "domain_maps": domain_maps,
        "concentration_maps": concentration_maps,
        "autocorrelation_rows": autocorrelation_rows,
        "autocorrelation_chart": autocorrelation_chart,
        "technical_files": technical_files,
        "velocity_summary": velocity_summary_items,
        "interpretation_items": interpretation_items,
        "concept_items": RESULT_CONCEPTS,
        "reading_steps": RESULT_READING_STEPS,
        "explanation": (
            "La ROI funciona como el terreno de la simulacion. Sus intensidades "
            "se convierten en obstaculos cilindricos y las particulas MPC se "
            "mueven dentro de ese espacio para estimar como cambia la difusion. "
            "Todo se interpreta como evidencia academica del modelo, no como "
            "diagnostico clinico."
        ),
    }


def get_result_image_path(results_dir: Path, result_key: str):
    static_definition = STATIC_RESULT_IMAGES.get(result_key)

    if static_definition is not None:
        return results_dir / static_definition["filename"]

    match = CONCENTRATION_KEY_PATTERN.match(result_key)
    if match:
        aggregation, time_value = match.groups()
        extension = "ppm" if aggregation == "scientific" else "pgm"
        return results_dir / f"mpc_concentration_{aggregation}_t_{time_value}.{extension}"

    high_match = HIGH_CONCENTRATION_KEY_PATTERN.match(result_key)
    if high_match:
        return results_dir / f"mpc_high_concentration_mean_t_{high_match.group(1)}.pgm"

    return None


def _empty_results_view():
    return {
        "available": False,
        "primary_metrics": (),
        "parameter_items": (),
        "domain_maps": (),
        "concentration_maps": (),
        "autocorrelation_rows": (),
        "autocorrelation_chart": None,
        "technical_files": (),
        "velocity_summary": (),
        "interpretation_items": (),
        "concept_items": RESULT_CONCEPTS,
        "reading_steps": RESULT_READING_STEPS,
        "explanation": "",
    }


def _build_domain_maps(results_dir):
    return tuple(
        _build_image_card(results_dir, key)
        for key in (
            "simulation_box_3d",
            "simulation_radius_top_view",
            "domain_mask",
            "obstacle_radius_map",
        )
        if get_result_image_path(results_dir, key).exists()
    )


def _build_concentration_maps(results_dir, concentration_summary, config):
    captured_times = _parse_int_csv(concentration_summary.get("captured_output_times"))
    threshold = _float_or_none(
        concentration_summary.get("high_concentration_threshold")
        or config.get("mpc_concentration_high_threshold")
    )
    representative_index = _int_or_none(
        concentration_summary.get("representative_realization_index")
    )
    representative_seed = _int_or_none(concentration_summary.get("representative_seed"))
    maps = []

    selected_times = tuple(dict.fromkeys(captured_times[:1] + captured_times[-1:]))
    for time_value in selected_times:
        scientific_key = f"mpc_concentration_scientific_t_{time_value}"
        representative_key = f"mpc_concentration_representative_t_{time_value}"
        key = (
            scientific_key
            if get_result_image_path(results_dir, scientific_key).exists()
            else representative_key
        )
        path = get_result_image_path(results_dir, key)
        if path is None or not path.exists():
            continue

        moment = "inicial" if time_value == selected_times[0] else "final"
        map_card = {
            "key": key,
            "scientific": key == scientific_key,
            "title": f"Concentracion {moment} en t={time_value}",
            "description": (
                "Instantanea reproducible de particulas MPC por celda tomada de "
                "una realizacion individual."
            ),
            "reading": (
                "El exterior de la ROI se distingue del negro interno sin particulas. "
                "El amarillo aumenta con la concentracion y el rojo identifica "
                "celdas que superan 2 x n0."
            ),
        }
        if key == scientific_key:
            map_card["legend"] = (
                "Azul oscuro: exterior de la ROI",
                "Negro: celda valida sin particulas",
                "Amarillo: concentracion de particulas",
                "Rojo: concentracion superior a 2 x n0",
            )
        if representative_index is not None and representative_seed is not None:
            map_card["sampling_note"] = (
                f"Realizacion reproducible {representative_index}; "
                f"semilla {representative_seed}; umbral {threshold:g}."
                if threshold is not None
                else f"Realizacion reproducible {representative_index}; semilla {representative_seed}."
            )
        maps.append(map_card)

    return tuple(maps)


def _build_autocorrelation_chart(results_dir, velocity_summary):
    source_path = results_dir / "velocity_autocorrelation.tsv"
    chart_path = results_dir / STATIC_RESULT_IMAGES["velocity_autocorrelation_chart"]["filename"]
    characteristic_time = _float_or_none(velocity_summary.get("characteristic_time"))

    if not source_path.exists():
        return None

    source_mtime = max(
        source_path.stat().st_mtime,
        (results_dir / "velocity_autocorrelation_summary.txt").stat().st_mtime
        if (results_dir / "velocity_autocorrelation_summary.txt").exists()
        else 0,
    )
    if not chart_path.exists() or chart_path.stat().st_mtime < source_mtime:
        series = _read_autocorrelation_series(source_path)
        if not series or not _write_autocorrelation_chart(
            chart_path,
            series,
            characteristic_time,
        ):
            return None

    card = _build_image_card(results_dir, "velocity_autocorrelation_chart")
    card["fit_available"] = characteristic_time is not None
    if characteristic_time is not None:
        card["sampling_note"] = f"Tiempo caracteristico estimado: tauC = {characteristic_time:.4g}."
    else:
        card["description"] = (
            "Evolucion normalizada de la memoria de velocidad calculada por el "
            "simulador MPC."
        )
        card["legend"] = (
            "Azul: Cv normalizada calculada",
            "Linea gris: referencia Cv=0",
        )
        card["reading"] = (
            "La curva azul muestra el resultado MPC promedio. En esta corrida la "
            "resolucion temporal no permitio obtener un ajuste exponencial estable, "
            "por lo que tauC no se informa."
        )
    return card


def _read_autocorrelation_series(path):
    try:
        with path.open("r", encoding="utf-8", newline="") as file:
            rows = []
            for row in csv.DictReader(file, delimiter="\t"):
                time_value = _float_or_none(row.get("time"))
                cv_value = _float_or_none(
                    row.get("cv_normalized") or row.get("cv") or row.get("cv_raw")
                )
                if time_value is not None and cv_value is not None:
                    rows.append((time_value, cv_value))
            return tuple(rows)
    except OSError:
        return ()


def _write_autocorrelation_chart(path, series, characteristic_time):
    width, height = 1100, 620
    left, top, right, bottom = 100, 55, 1050, 520
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = _chart_font(20)
    small_font = _chart_font(16)
    title_font = _chart_font(25, bold=True)
    x_values = [item[0] for item in series]
    y_values = [item[1] for item in series]
    x_min, x_max = min(x_values), max(x_values)
    if x_max <= x_min:
        x_max = x_min + 1
    y_min = min(-0.1, min(y_values))
    y_max = max(1.05, max(y_values))
    if y_max <= y_min:
        y_max = y_min + 1

    def point(x_value, y_value):
        x = left + (x_value - x_min) * (right - left) / (x_max - x_min)
        y = bottom - (y_value - y_min) * (bottom - top) / (y_max - y_min)
        return round(x), round(y)

    draw.text((left, 15), "Autocorrelacion normalizada de velocidades Cv", fill="#0b4866", font=title_font)
    for tick_index in range(6):
        x_value = x_min + tick_index * (x_max - x_min) / 5
        x, _ = point(x_value, y_min)
        draw.line((x, top, x, bottom), fill="#e1e8ef", width=1)
        draw.text((x - 14, bottom + 12), f"{x_value:g}", fill="#4a5d72", font=small_font)
    for tick_index in range(6):
        y_value = y_min + tick_index * (y_max - y_min) / 5
        _, y = point(x_min, y_value)
        draw.line((left, y, right, y), fill="#e1e8ef", width=1)
        draw.text((20, y - 10), f"{y_value:.2f}", fill="#4a5d72", font=small_font)

    zero_y = point(x_min, 0)[1]
    draw.line((left, zero_y, right, zero_y), fill="#8c99a8", width=2)
    draw.line((left, top, left, bottom), fill="#243b53", width=2)
    draw.line((left, bottom, right, bottom), fill="#243b53", width=2)
    cv_points = [point(x_value, y_value) for x_value, y_value in series]
    if len(cv_points) > 1:
        draw.line(cv_points, fill="#0875b7", width=4, joint="curve")
    for x, y in cv_points:
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill="#0875b7")

    if characteristic_time is not None and characteristic_time > 0:
        fit_points = [
            point(x_value, math.exp(-x_value / characteristic_time))
            for x_value in x_values
        ]
        if len(fit_points) > 1:
            draw.line(fit_points, fill="#c9332b", width=4)

    draw.text((right - 300, 70), "Cv calculada", fill="#0875b7", font=font)
    if characteristic_time is not None and characteristic_time > 0:
        draw.text((right - 300, 102), "Ajuste exp(-t/tauC)", fill="#c9332b", font=font)
    draw.text(((left + right) // 2 - 55, height - 55), "Tiempo t", fill="#243b53", font=font)
    image.save(path, format="PNG")
    return True


def _chart_font(size, bold=False):
    font_name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(font_name, size)
    except OSError:
        return ImageFont.load_default()


def _build_image_card(results_dir, key):
    definition = STATIC_RESULT_IMAGES[key]
    card = {
        "key": key,
        "title": definition["title"],
        "description": definition["description"],
        "reading": definition["reading"],
        "legend": definition.get("legend", ()),
    }
    if key in {"simulation_box_3d", "simulation_radius_top_view"}:
        metadata = _read_key_value_file(results_dir / "simulation_box_visualization.txt")
        if metadata:
            card["sampling_note"] = (
                f"Seccion mostrada: {metadata.get('section_columns', '?')} x "
                f"{metadata.get('section_rows', '?')} celdas, desde "
                f"x={metadata.get('section_x_start', '?')} y "
                f"y={metadata.get('section_y_start', '?')}; "
                f"{metadata.get('visualized_cylinder_count', '?')} cilindros visibles."
            )

    return card


def _build_interpretation_items(metrics, config, diffusion):
    items = [
        {
            "label": "De la ROI al resultado",
            "detail": (
                "El flujo parte de una ROI en escala de grises. Esa ROI se transforma "
                "en una caja de simulacion con cilindros; luego las particulas se "
                "mueven, chocan y generan mapas y metricas como MDC, MDC* y Cv."
            ),
        },
        {
            "label": "Alcance academico",
            "detail": (
                "Los resultados describen el comportamiento del modelo computacional. "
                "No detectan cancer, no clasifican lesiones y no reemplazan una "
                "revision medica."
            ),
        },
    ]
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
                "Numero que resume la facilidad de movimiento dentro de la ROI simulada.",
            ),
            _metric(
                "Referencia libre (MDC0)",
                diffusion.get("mdc0"),
                "Valor de comparacion para un espacio ideal sin obstaculos.",
            ),
            _metric(
                "Difusion normalizada (MDC*)",
                diffusion.get("mdc_star"),
                "MDC dividido para MDC0; permite comparar corridas en una escala comun.",
            ),
            _metric(
                "Desviacion estandar de MDC",
                diffusion.get("mdc_standard_deviation"),
                "Dispersion de los valores MDC obtenidos entre realizaciones.",
            ),
            _metric(
                "Error estandar de MDC",
                diffusion.get("mdc_standard_error"),
                "Incertidumbre del MDC promedio calculado entre realizaciones.",
            ),
            _metric(
                "Desviacion estandar de MDC*",
                diffusion.get("mdc_star_standard_deviation"),
                "Dispersion de la difusion normalizada entre realizaciones.",
            ),
            _metric(
                "Error estandar de MDC*",
                diffusion.get("mdc_star_standard_error"),
                "Incertidumbre del promedio de difusion normalizada.",
            ),
            _metric(
                "Tiempo caracteristico (tauC)",
                diffusion.get("characteristic_time"),
                "Tiempo estimado en que Cv pierde memoria de la direccion inicial.",
            ),
            _metric(
                "Particulas simuladas",
                config.get("mpc_particle_count"),
                "Puntos matematicos que se mueven dentro de la caja de simulacion.",
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
                "Cantidad promedio de particulas que el modelo intenta ubicar por celda.",
            ),
            _metric(
                "Paso temporal (tau)",
                config.get("tau") or diffusion.get("tau"),
                "Tamano del salto de tiempo que avanza en cada paso de simulacion.",
            ),
            _metric(
                "Energia termica (kBT)",
                config.get("kbt") or diffusion.get("kbt"),
                "Controla que tan intenso es el movimiento aleatorio de las particulas.",
            ),
            _metric(
                "Masa por particula",
                config.get("mass") or diffusion.get("mass"),
                "Peso matematico usado para calcular como cambia la velocidad.",
            ),
            _metric(
                "Semilla de simulacion",
                config.get("seed") or metrics.get("seed"),
                "Numero inicial que permite repetir una corrida con condiciones comparables.",
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
                "Cantidad objetivo de particulas seguidas para observar la memoria del movimiento.",
                value_type="integer",
            ),
            _metric(
                "Particulas usadas para Cv",
                config.get("velocity_autocorrelation_labeled_particle_count")
                or diffusion.get("labeled_particle_count"),
                "Cantidad realmente seguida para Cv; si hay menos disponibles, se usa el total posible.",
                value_type="integer",
            ),
            _metric(
                "Angulo de rotacion MPC",
                config.get("rotation_angle"),
                "Regla del modelo que gira velocidades durante la colision multiparticula.",
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
                "Resultado obtenido al resumir la memoria del movimiento de las particulas.",
            ),
            _metric(
                "Tiempo caracteristico",
                summary.get("characteristic_time"),
                "Tiempo aproximado en que la curva Cv pierde parte de su memoria inicial.",
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
                cv_value = (
                    row.get("cv_normalized")
                    or row.get("cv")
                    or row.get("cv_raw")
                )
                rows.append(
                    {
                        "lag": _format_value(row.get("lag"), "integer"),
                        "time": _format_value(row.get("time"), "decimal"),
                        "cv": _format_value(cv_value, "decimal"),
                        "meaning": _interpret_cv(cv_value),
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


def _int_or_none(value):
    try:
        return int(float(value))
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
