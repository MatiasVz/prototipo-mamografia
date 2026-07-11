from dataclasses import dataclass
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .preview_service import ensure_preview_for_path


RESULT_FILE_DESCRIPTIONS = {
    "domain_mask.pgm": "Mapa de la region mamaria valida usada por el simulador.",
    "mpc_config.json": "Parametros usados por el modelo MPC.",
    "space_summary.txt": "Resumen de la caja plana y obstaculos construidos desde la ROI.",
    "obstacle_radius_matrix.tsv": "Matriz de radios de obstaculos por celda.",
    "obstacle_radius_map.pgm": "Visualizacion de cilindros derivados de tonos de gris de la ROI.",
    "obstacle_radius_histogram.tsv": "Distribucion de radios de obstaculos.",
    "simulation_box_3d.png": "Visualizacion pseudo-3D de la caja de simulacion con cilindros y particulas.",
    "mpc_initial_particles.tsv": "Estado inicial de particulas MPC.",
    "mpc_streamed_particles.tsv": "Particulas despues de traslacion libre y rebotes.",
    "mpc_streaming_summary.txt": "Resumen de traslacion y rebotes.",
    "mpc_collided_particles.tsv": "Particulas despues de colision multiparticula.",
    "mpc_collision_summary.txt": "Resumen de colisiones MPC.",
    "mpc_cell_collisions.tsv": "Detalle de colisiones agrupadas por celda.",
    "mpc_concentration_summary.txt": "Resumen de mapas que muestran distribucion de particulas.",
    "mpc_concentration_times.tsv": "Concentracion de particulas por tiempos capturados.",
    "mpc_concentration_representative_initial.pgm": "Conteo inicial de particulas en la realizacion representativa.",
    "mpc_concentration_representative_final.pgm": "Conteo final de particulas en la realizacion representativa.",
    "mpc_concentration_mean_initial.pgm": "Concentracion inicial promedio entre realizaciones.",
    "mpc_concentration_mean_final.pgm": "Concentracion final promedio entre realizaciones.",
    "mpc_high_concentration_mean_initial.pgm": "Celdas iniciales cuyo promedio supera 2 x n0.",
    "mpc_high_concentration_mean_final.pgm": "Celdas finales cuyo promedio supera 2 x n0.",
    "velocity_autocorrelation.tsv": "Serie Cv que resume memoria del movimiento.",
    "velocity_autocorrelation_summary.txt": "Resumen legible del calculo de Cv.",
    "velocity_autocorrelation_realizations.tsv": "Detalle por realizacion de Cv.",
    "diffusion_metrics.json": "Metricas MDC, MDC0 y MDC* en formato JSON.",
    "diffusion_metrics.tsv": "Metricas MDC, MDC0 y MDC* en formato tabular.",
    "diffusion_metrics_summary.txt": "Resumen legible de movilidad y difusion simulada.",
    "simulation_summary.txt": "Resumen general de la simulacion.",
    "simulation_state.json": "Estado tecnico de la simulacion.",
    "simulation.log": "Log producido por el simulador Julia.",
    "worker_execution.log": "Log de ejecucion del worker Python.",
}


@dataclass(frozen=True)
class ExportFile:
    label: str
    description: str
    source_path: Path
    archive_path: str
    registered_path: str
    category: str


@dataclass(frozen=True)
class CaseExportBundle:
    case_id: int
    report_filename: str
    package_filename: str
    report_markdown: str
    files: tuple[ExportFile, ...]
    missing_items: tuple[str, ...]
    manifest: dict


def build_case_export_bundle(case, upload_folder):
    paths = _build_case_paths(case, upload_folder)
    export_files, missing_items = _collect_export_files(case, paths)
    preview_files = _collect_preview_files(export_files)
    all_files = _deduplicate_files(export_files + preview_files)
    metrics = _read_result_data(paths["results_dir"])
    manifest = _build_manifest(case, all_files, missing_items, metrics)
    report_markdown = _build_report_markdown(case, all_files, missing_items, metrics)

    return CaseExportBundle(
        case_id=case.id,
        report_filename=f"caso_{case.id}_reporte_academico.md",
        package_filename=f"caso_{case.id}_paquete_resultados.zip",
        report_markdown=report_markdown,
        files=all_files,
        missing_items=tuple(missing_items),
        manifest=manifest,
    )


def build_case_results_package(bundle):
    zip_buffer = BytesIO()
    case_folder = f"caso_{bundle.case_id}"

    with ZipFile(zip_buffer, "w", ZIP_DEFLATED) as zip_file:
        zip_file.writestr("README.txt", _build_package_readme(bundle))
        zip_file.writestr(f"{case_folder}/{bundle.report_filename}", bundle.report_markdown)
        zip_file.writestr(
            f"{case_folder}/manifest_trazabilidad.json",
            json.dumps(bundle.manifest, indent=2, ensure_ascii=False),
        )

        for export_file in bundle.files:
            if not export_file.source_path.exists():
                continue

            zip_file.write(
                export_file.source_path,
                f"{case_folder}/{export_file.archive_path}",
            )

    zip_buffer.seek(0)
    return zip_buffer


def _build_case_paths(case, upload_folder):
    upload_folder_path = Path(upload_folder)
    case_dir = upload_folder_path / f"case_{case.id}"

    return {
        "case_dir": case_dir,
        "original": _resolve_stored_path(case.original_file_path, upload_folder_path),
        "roi": _resolve_stored_path(case.roi_file_path, upload_folder_path),
        "simulation_input": _resolve_stored_path(
            case.simulation_input_file_path,
            upload_folder_path,
        ),
        "simulation_grayscale": case_dir / "simulation_grayscale.png",
        "simulation_preparation": case_dir / "simulation_preparation.json",
        "results_dir": _resolve_results_dir(case, upload_folder_path, case_dir),
    }


def _resolve_results_dir(case, upload_folder_path, case_dir):
    configured_dir = _resolve_stored_path(case.simulation_results_path, upload_folder_path)

    if configured_dir is not None:
        return configured_dir

    fallback_dir = case_dir / "results"
    if fallback_dir.exists():
        return fallback_dir

    return None


def _resolve_stored_path(stored_path, upload_folder_path):
    if not stored_path:
        return None

    path = Path(stored_path)

    if path.is_absolute():
        return path

    cwd_candidate = Path.cwd() / path
    if cwd_candidate.exists():
        return cwd_candidate

    parts = path.parts
    if "uploads" in parts:
        uploads_index = parts.index("uploads")
        relative_to_uploads = Path(*parts[uploads_index + 1 :])
        return upload_folder_path / relative_to_uploads

    return upload_folder_path / path


def _collect_export_files(case, paths):
    export_files = []
    missing_items = []

    _append_file_or_missing(
        export_files,
        missing_items,
        label="Imagen original",
        description="Archivo cargado inicialmente por el usuario.",
        path=paths["original"],
        archive_path=f"01_imagen_original/{_filename(paths['original'], 'original')}",
        registered_path=case.original_file_path,
        category="imagen_original",
    )
    _append_file_or_missing(
        export_files,
        missing_items,
        label="ROI utilizada",
        description="Region de interes asociada al caso.",
        path=paths["roi"],
        archive_path=f"02_roi/{_filename(paths['roi'], 'roi')}",
        registered_path=case.roi_file_path,
        category="roi",
        required=False,
    )
    _append_file_or_missing(
        export_files,
        missing_items,
        label="Entrada PGM",
        description="Imagen en escala de grises preparada para la simulacion.",
        path=paths["simulation_input"],
        archive_path="03_entrada_simulacion/simulation_input.pgm",
        registered_path=case.simulation_input_file_path,
        category="entrada_simulacion",
        required=False,
    )
    _append_file_or_missing(
        export_files,
        missing_items,
        label="Imagen en escala de grises",
        description="Conversion determinista de la ROI previa a la entrada PGM.",
        path=paths["simulation_grayscale"],
        archive_path="03_entrada_simulacion/simulation_grayscale.png",
        registered_path=str(paths["simulation_grayscale"]),
        category="entrada_simulacion",
        required=False,
    )
    _append_file_or_missing(
        export_files,
        missing_items,
        label="Metadatos de preparacion",
        description="Politica de conversion, dimensiones y huella de la entrada PGM.",
        path=paths["simulation_preparation"],
        archive_path="03_entrada_simulacion/simulation_preparation.json",
        registered_path=str(paths["simulation_preparation"]),
        category="entrada_simulacion",
        required=False,
    )

    results_dir = paths["results_dir"]
    if results_dir is None or not results_dir.exists():
        missing_items.append("Carpeta de resultados de simulacion")
    else:
        for result_path in sorted(results_dir.iterdir()):
            if not result_path.is_file() or result_path.name.endswith("_preview.png"):
                continue

            export_files.append(
                ExportFile(
                    label=_result_file_label(result_path.name),
                    description=_result_file_description(result_path.name),
                    source_path=result_path,
                    archive_path=f"04_resultados/{result_path.name}",
                    registered_path=str(result_path),
                    category="resultado",
                )
            )

    return tuple(export_files), tuple(missing_items)


def _append_file_or_missing(
    export_files,
    missing_items,
    *,
    label,
    description,
    path,
    archive_path,
    registered_path,
    category,
    required=True,
):
    if path is not None and path.exists():
        export_files.append(
            ExportFile(
                label=label,
                description=description,
                source_path=path,
                archive_path=archive_path,
                registered_path=registered_path or str(path),
                category=category,
            )
        )
        return

    if required or registered_path:
        missing_items.append(label)


def _collect_preview_files(export_files):
    preview_files = []

    for export_file in export_files:
        try:
            preview = ensure_preview_for_path(export_file.source_path)
        except (OSError, TypeError, ValueError):
            continue

        if preview is None or not preview.is_generated:
            continue

        archive_path = _preview_archive_path(export_file.archive_path)
        preview_files.append(
            ExportFile(
                label=f"{export_file.label} - vista PNG",
                description=(
                    "Version PNG generada para abrir el contenido facilmente "
                    "sin software especializado."
                ),
                source_path=preview.absolute_path,
                archive_path=archive_path,
                registered_path=str(preview.absolute_path),
                category=f"{export_file.category}_preview",
            )
        )

    return tuple(preview_files)


def _preview_archive_path(archive_path):
    path = Path(archive_path)
    preview_name = f"{path.stem}_vista.png"

    if path.parent == Path("."):
        return f"visualizaciones/{preview_name}"

    return str(Path("visualizaciones") / path.parent / preview_name).replace("\\", "/")


def _deduplicate_files(export_files):
    seen_archive_paths = set()
    unique_files = []

    for export_file in export_files:
        if export_file.archive_path in seen_archive_paths:
            continue

        seen_archive_paths.add(export_file.archive_path)
        unique_files.append(export_file)

    return tuple(unique_files)


def _read_result_data(results_dir):
    if results_dir is None or not results_dir.exists():
        return {
            "metrics": {},
            "config": {},
            "diffusion": {},
            "concentration_summary": {},
            "velocity_summary": {},
        }

    return {
        "metrics": {},
        "config": _read_json(results_dir / "mpc_config.json"),
        "diffusion": _read_json(results_dir / "diffusion_metrics.json"),
        "concentration_summary": _read_key_value_file(
            results_dir / "mpc_concentration_summary.txt",
        ),
        "velocity_summary": _read_key_value_file(
            results_dir / "velocity_autocorrelation_summary.txt",
        ),
    }


def _build_manifest(case, export_files, missing_items, metrics):
    return {
        "case_id": case.id,
        "status": case.status,
        "input_mode": case.input_mode,
        "original_filename": case.original_filename,
        "generated_files": [
            {
                "label": export_file.label,
                "description": export_file.description,
                "archive_path": export_file.archive_path,
                "registered_path": export_file.registered_path,
                "category": export_file.category,
            }
            for export_file in export_files
        ],
        "missing_items": list(missing_items),
        "available_metric_keys": {
            "metrics": sorted(metrics["metrics"].keys()),
            "config": sorted(metrics["config"].keys()),
            "diffusion": sorted(metrics["diffusion"].keys()),
        },
        "academic_notice": (
            "Este paquete es evidencia academica del prototipo. No constituye "
            "diagnostico clinico."
        ),
    }


def _build_report_markdown(case, export_files, missing_items, metrics):
    lines = [
        f"# Reporte academico del caso #{case.id}",
        "",
        (
            "Este reporte resume la informacion del caso, los archivos usados y "
            "los resultados generados por el prototipo. Esta escrito para lectura "
            "academica y no corresponde a un diagnostico clinico."
        ),
        "",
        "## Lectura rapida",
        "",
        (
            f"- El caso #{case.id} fue registrado como "
            f"**{_format_input_mode(case.input_mode)}**."
        ),
        f"- Estado actual del caso: **{_format_status(case.status)}**.",
        (
            "- El paquete conserva archivos originales, ROI, entrada PGM, mapas, "
            "metricas y logs cuando estan disponibles."
        ),
        "- Las imagenes PNG dentro de `visualizaciones/` son copias faciles de abrir.",
        "",
        "## Como interpretar este reporte",
        "",
        (
            "La lectura recomendada es seguir el camino completo: primero la ROI, "
            "luego la caja de simulacion, despues los mapas y finalmente las "
            "metricas numericas."
        ),
        "",
        "### De la ROI al resultado",
        "",
        "- **ROI**: region de interes usada como zona de trabajo del prototipo.",
        (
            "- **PGM**: version en escala de grises que permite que el simulador "
            "trabaje con intensidades numericas."
        ),
        (
            "- **Caja plana**: representacion bidimensional construida desde la ROI "
            "para ejecutar la simulacion."
        ),
        (
            "- **Obstaculos**: elementos derivados de intensidades de la ROI que "
            "representan heterogeneidad del tejido en el modelo; los tonos oscuros "
            "tienden a formar cilindros mayores y los tonos claros cilindros menores."
        ),
        (
            "- **Particulas MPC**: puntos matematicos que se mueven en la caja, "
            "chocan con obstaculos y dejan evidencia de su distribucion."
        ),
        (
            "- **Mapas**: imagenes generadas por el modelo; no son una mamografia "
            "nueva, sino visualizaciones de dominio, obstaculos, visitas y "
            "concentracion de particulas."
        ),
        "",
        "### Guia simple de metricas",
        "",
        (
            "- **MDC**: resume que tan facil se movieron las particulas dentro de "
            "la ROI simulada."
        ),
        (
            "- **MDC0**: referencia teorica de movimiento si no existieran obstaculos."
        ),
        (
            "- **MDC***: MDC normalizado respecto a MDC0. Sirve para comparar "
            "corridas o casos en una escala comun."
        ),
        (
            "- **Cv**: autocorrelacion de velocidades; observa si las particulas "
            "conservan su direccion inicial o si los choques hacen que pierdan "
            "esa memoria."
        ),
        (
            "- **Zonas altas**: celdas con concentracion superior al umbral del "
            "modelo. No significan diagnostico ni presencia de lesion."
        ),
        "",
        "## Datos principales del caso",
        "",
        _markdown_table(
            ("Campo", "Valor"),
            (
                ("ID del caso", case.id),
                ("Fecha de carga", _format_datetime(case.created_at)),
                ("Fecha de actualizacion", _format_datetime(case.updated_at)),
                ("Modalidad", _format_input_mode(case.input_mode)),
                ("Archivo original", case.original_filename or "No registrado"),
                ("Tipo de archivo", case.file_type or "No registrado"),
                ("Tamano original", _format_file_size(case.file_size_bytes)),
                ("Estado", _format_status(case.status)),
            ),
        ),
        "",
        "## Resultados principales",
        "",
    ]

    metric_rows = _build_metric_rows(metrics)
    if metric_rows:
        lines.append(_markdown_table(("Resultado", "Valor", "Que significa"), metric_rows))
    else:
        lines.append("No se encontraron metricas de simulacion disponibles para este caso.")

    parameter_rows = _build_parameter_rows(metrics)
    lines.extend(["", "## Parametros de simulacion", ""])
    if parameter_rows:
        lines.append(_markdown_table(("Parametro", "Valor", "Uso"), parameter_rows))
    else:
        lines.append("No se encontro configuracion MPC disponible para este caso.")

    lines.extend(["", "## Archivos incluidos", ""])
    if export_files:
        lines.append(
            _markdown_table(
                ("Archivo", "Ubicacion en el paquete", "Para que sirve"),
                (
                    (
                        export_file.label,
                        export_file.archive_path,
                        export_file.description,
                    )
                    for export_file in export_files
                ),
            )
        )
    else:
        lines.append("No se encontraron archivos para incluir en el paquete.")

    lines.extend(["", "## Elementos no disponibles", ""])
    if missing_items:
        lines.extend(f"- {item}" for item in missing_items)
    else:
        lines.append("No se detectaron elementos esperados como faltantes.")

    lines.extend(
        [
            "",
            "## Trazabilidad registrada",
            "",
            _markdown_table(
                ("Elemento", "Ruta registrada"),
                (
                    ("Archivo original", case.original_file_path or "No registrada"),
                    ("ROI", case.roi_file_path or "No registrada"),
                    ("Entrada PGM", case.simulation_input_file_path or "No registrada"),
                    (
                        "Carpeta de resultados",
                        case.simulation_results_path or "No registrada",
                    ),
                    ("Metricas", case.simulation_metrics_file_path or "No registrada"),
                    (
                        "Concentracion MPC representativa final",
                        case.simulation_density_map_file_path or "No registrada",
                    ),
                    ("Log de simulacion", case.simulation_log_file_path or "No registrada"),
                ),
            ),
            "",
            "## Nota academica",
            "",
            (
                "El prototipo organiza una region de interes y resultados de "
                "simulacion mesoscopica con fines de investigacion. No interpreta "
                "lesiones, no clasifica hallazgos y no reemplaza la evaluacion "
                "medica profesional. Las metricas y mapas describen el comportamiento "
                "del modelo computacional sobre la ROI seleccionada."
            ),
            "",
        ]
    )

    return "\n".join(lines)


def _build_metric_rows(metrics):
    diffusion = metrics["diffusion"]
    config = metrics["config"]
    preliminary = metrics["metrics"]

    candidates = (
        (
            "MDC",
            diffusion.get("mdc"),
            "Resume la facilidad de movimiento de las particulas dentro de la ROI simulada.",
        ),
        (
            "MDC0",
            diffusion.get("mdc0"),
            "Referencia de movimiento en un espacio ideal sin obstaculos.",
        ),
        (
            "MDC*",
            diffusion.get("mdc_star"),
            "MDC dividido para MDC0; permite comparar corridas en una escala comun.",
        ),
        (
            "Variacion MDC",
            diffusion.get("mdc_standard_deviation"),
            "Diferencia entre corridas cuando se ejecutan varias realizaciones.",
        ),
        (
            "Particulas MPC",
            _first_value(config, preliminary, "mpc_particle_count", "particle_count"),
            "Puntos matematicos usados para representar movimiento en la caja.",
        ),
        (
            "Pasos",
            _first_value(config, preliminary, "steps"),
            "Iteraciones ejecutadas.",
        ),
        (
            "Choques con obstaculos",
            config.get("mpc_streaming_obstacle_collision_count"),
            "Rebotes contra cilindros generados desde las intensidades de la ROI.",
        ),
        (
            "Rebotes con borde de ROI",
            config.get("mpc_streaming_domain_boundary_collision_count"),
            "Intentos de salida del dominio mamario contenidos por la mascara.",
        ),
        (
            "Tasa de colision",
            preliminary.get("collision_rate"),
            "Proporcion preliminar de choques detectados.",
        ),
    )

    return tuple(
        (label, _format_metric_value(value), description)
        for label, value, description in candidates
        if value not in (None, "")
    )


def _build_parameter_rows(metrics):
    diffusion = metrics["diffusion"]
    config = metrics["config"]

    candidates = (
        (
            "Semilla",
            config.get("seed"),
            "Numero inicial para repetir condiciones aleatorias comparables.",
        ),
        (
            "n0",
            _first_value(config, diffusion, "n0"),
            "Cantidad promedio de particulas que el modelo intenta ubicar por celda.",
        ),
        (
            "tau",
            _first_value(config, diffusion, "tau"),
            "Tamano del salto de tiempo aplicado en cada paso.",
        ),
        (
            "kBT",
            _first_value(config, diffusion, "kbt"),
            "Parametro que controla la intensidad del movimiento aleatorio.",
        ),
        (
            "Masa",
            _first_value(config, diffusion, "mass"),
            "Peso matematico usado para calcular cambios de velocidad.",
        ),
        (
            "Angulo de rotacion",
            config.get("rotation_angle"),
            "Regla que gira velocidades durante la colision multiparticula.",
        ),
        (
            "Realizaciones",
            _first_value(config, diffusion, "realizations"),
            "Corridas usadas para promediar metricas.",
        ),
        (
            "Particulas solicitadas para Cv",
            _first_value(
                config,
                diffusion,
                "velocity_autocorrelation_requested_labeled_particles",
                "requested_labeled_particles",
                "labeled_particles",
            ),
            "Cantidad objetivo de particulas seguidas para medir memoria del movimiento.",
        ),
        (
            "Particulas usadas para Cv",
            _first_value(
                config,
                diffusion,
                "velocity_autocorrelation_labeled_particle_count",
                "labeled_particle_count",
            ),
            "Cantidad real seguida para Cv y MDC; si no hay 500 disponibles, se usa el total posible.",
        ),
    )

    return tuple(
        (label, _format_metric_value(value), description)
        for label, value, description in candidates
        if value not in (None, "")
    )


def _build_package_readme(bundle):
    return "\n".join(
        [
            f"Paquete academico del caso #{bundle.case_id}",
            "",
            "Contenido principal:",
            f"- {bundle.report_filename}: explicacion legible del caso y resultados.",
            "- manifest_trazabilidad.json: listado estructurado de archivos incluidos.",
            "- 01_imagen_original/: archivo cargado originalmente, si esta disponible.",
            "- 02_roi/: region de interes usada, si esta disponible.",
            "- 03_entrada_simulacion/: entrada PGM enviada al simulador.",
            "- 04_resultados/: metricas, mapas y logs generados por el simulador.",
            "- visualizaciones/: versiones PNG faciles de abrir para mapas PGM.",
            "",
            "Nota:",
            (
                "Este paquete sirve como evidencia academica del prototipo. No "
                "contiene interpretacion diagnostica ni reemplaza revision medica."
            ),
            "",
        ]
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


def _markdown_table(headers, rows):
    rows = tuple(rows)
    header_line = "| " + " | ".join(_escape_markdown(value) for value in headers) + " |"
    separator_line = "| " + " | ".join("---" for _ in headers) + " |"
    body_lines = [
        "| " + " | ".join(_escape_markdown(value) for value in row) + " |"
        for row in rows
    ]

    return "\n".join((header_line, separator_line, *body_lines))


def _escape_markdown(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def _first_value(primary, secondary, *keys):
    for key in keys:
        value = primary.get(key)
        if value not in (None, ""):
            return value

        value = secondary.get(key)
        if value not in (None, ""):
            return value

    return None


def _filename(path, fallback):
    if path is None:
        return fallback

    return path.name


def _result_file_label(filename):
    if filename.startswith("mpc_concentration_representative_t_") and filename.endswith(".pgm"):
        time_value = filename.removeprefix(
            "mpc_concentration_representative_t_",
        ).removesuffix(".pgm")
        return f"Realizacion representativa en t={time_value}"

    if filename.startswith("mpc_concentration_mean_t_") and filename.endswith(".pgm"):
        time_value = filename.removeprefix("mpc_concentration_mean_t_").removesuffix(".pgm")
        return f"Concentracion promedio en t={time_value}"

    if filename.startswith("mpc_high_concentration_mean_t_") and filename.endswith(".pgm"):
        time_value = filename.removeprefix(
            "mpc_high_concentration_mean_t_",
        ).removesuffix(".pgm")
        return f"Zonas altas promedio en t={time_value}"

    if filename.startswith("worker_execution_") and filename.endswith(".log"):
        return "Log historico del worker"

    return filename.replace("_", " ").replace(".", " ").title()


def _result_file_description(filename):
    if filename in RESULT_FILE_DESCRIPTIONS:
        return RESULT_FILE_DESCRIPTIONS[filename]

    if filename.startswith("mpc_concentration_representative_t_") and filename.endswith(".pgm"):
        return "Mapa de una corrida MPC real, construido desde posiciones de particulas."

    if filename.startswith("mpc_concentration_mean_t_") and filename.endswith(".pgm"):
        return "Mapa promedio de concentracion MPC entre realizaciones."

    if filename.startswith("mpc_high_concentration_mean_t_") and filename.endswith(".pgm"):
        return "Celdas cuyo promedio de particulas supera el umbral 2 x n0."

    if filename.startswith("worker_execution_") and filename.endswith(".log"):
        return "Log historico de una corrida del worker Python."

    return "Archivo tecnico generado por el flujo de simulacion."


def _format_datetime(value):
    if value is None:
        return "No registrada"

    return value.strftime("%Y-%m-%d %H:%M:%S")


def _format_file_size(size_bytes):
    if size_bytes is None:
        return "No registrado"

    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"

    return f"{size_bytes} bytes"


def _format_input_mode(input_mode):
    if input_mode == "roi_recortada":
        return "ROI recortada"

    return "Mamografia completa"


def _format_status(status):
    labels = {
        "registrado": "Registrado",
        "roi_confirmada": "ROI confirmada",
        "pendiente": "En cola",
        "procesando": "Procesando",
        "completado": "Completado",
        "error": "Error",
        "notificado": "Notificado",
    }

    return labels.get(status, status or "No registrado")


def _format_metric_value(value):
    if value in (None, ""):
        return "No disponible"

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

    return f"{number:.5g}"
