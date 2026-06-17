import json
from io import BytesIO
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import RequestEntityTooLarge

from ..extensions import db
from ..models import Case, CaseStatus, InputMode
from ..services.case_export_service import (
    build_case_export_bundle,
    build_case_results_package,
)
from ..services.case_pdf_report_service import build_case_pdf_report
from ..services.case_registration_service import register_case_upload
from ..services.file_validation import ALLOWED_EXTENSIONS, validate_mammogram_file
from ..services.preview_service import ensure_preview_for_case, ensure_preview_for_path
from ..services.roi_service import RoiCrop, crop_roi_for_case
from ..services.simulation_preparation_service import prepare_simulation_input_for_case
from ..services.simulation_queue_service import (
    SimulationQueueError,
    enqueue_case_simulation,
)
from ..services.simulation_comparison_service import (
    build_case_comparison,
    is_case_mpc_comparable,
)
from ..services.simulation_results_service import (
    build_mpc_results_view,
    get_result_image_path,
)
from ..services.auth_service import get_current_user, require_authenticated_user
from ..services.storage_service import get_case_roi_directory
from ..services.upload_error_service import (
    safe_register_request_size_error,
    safe_register_upload_error,
)


upload_bp = Blueprint("upload", __name__, url_prefix="/mamografias")


@upload_bp.before_request
def _require_authenticated_user():
    """Toda ruta de casos/cargas exige sesion iniciada (se restringe por dueño aparte)."""
    return require_authenticated_user()


def _get_owned_case(case_id):
    """Devuelve el caso solo si pertenece al usuario autenticado.

    Si el caso no existe o es de otro usuario, devuelve None. Las rutas que lo usan
    ya hacen `abort(404)` ante None, asi que un caso ajeno responde 404 (no revela su
    existencia). El dueño va en la consulta, no en un chequeo posterior.
    """
    user = get_current_user()

    if user is None:
        return None

    return Case.query.filter_by(id=case_id, user_id=user.id).first()

SIMULATION_METRIC_FIELDS = (
    ("Particulas", "particle_count", "integer"),
    ("Pasos", "steps", "integer"),
    ("Obstaculos", "obstacle_count", "integer"),
    ("Celdas visitadas", "visited_cell_count", "integer"),
    ("Choques", "collision_count", "integer"),
    ("Tasa de colision", "collision_rate", "percent"),
    ("Maximo de visitas", "max_visits", "integer"),
)

PROCESSING_ERROR_MESSAGES = {
    "invalid_parameters": {
        "category": "Configuracion del simulador",
        "message": (
            "La simulacion no pudo iniciar porque la configuracion del simulador "
            "necesita un ajuste."
        ),
        "action": (
            "Revisa los parametros de simulacion y vuelve a encolar el caso. "
            "No necesitas cargar la imagen otra vez."
        ),
    },
    "invalid_pgm": {
        "category": "Entrada PGM invalida",
        "message": (
            "La imagen preparada para simulacion no tiene un formato PGM valido."
        ),
        "action": (
            "Vuelve a preparar la entrada PGM desde la ROI confirmada o carga otra imagen."
        ),
    },
    "missing_pgm": {
        "category": "Entrada PGM pendiente",
        "message": "El caso todavia no tiene una imagen PGM lista para simular.",
        "action": "Prepara la entrada PGM y luego envia nuevamente el caso a procesamiento.",
    },
    "missing_roi": {
        "category": "ROI pendiente",
        "message": "El caso no tiene una ROI disponible para procesar.",
        "action": "Asocia o recorta una ROI, confirmala y vuelve a intentar la simulacion.",
    },
    "missing_input_file": {
        "category": "Archivo no disponible",
        "message": "No se encontro el archivo preparado para iniciar la simulacion.",
        "action": "Vuelve a preparar la entrada de simulacion y reintenta el procesamiento.",
    },
    "invalid_state": {
        "category": "Estado del caso",
        "message": "El caso no esta en un estado valido para ejecutar la simulacion.",
        "action": "Revisa que la ROI este confirmada y que la entrada PGM este generada.",
    },
    "runtime_config": {
        "category": "Entorno de simulacion",
        "message": "El entorno de ejecucion del simulador no esta listo.",
        "action": "Verifica la configuracion del contenedor y reintenta el procesamiento.",
    },
    "julia_executable": {
        "category": "Julia no disponible",
        "message": "No se pudo iniciar el motor Julia del simulador.",
        "action": "Verifica que Julia este instalado en el entorno de procesamiento.",
    },
    "julia_failure": {
        "category": "Simulacion interrumpida",
        "message": "El simulador no pudo completar la corrida de este caso.",
        "action": "Reintenta la simulacion. Si vuelve a fallar, revisa la trazabilidad tecnica.",
    },
    "timeout": {
        "category": "Tiempo de procesamiento",
        "message": "La simulacion tardo mas de lo permitido por la configuracion actual.",
        "action": "Reintenta con mas tiempo disponible o ejecuta el caso en el servidor.",
    },
    "missing_results": {
        "category": "Resultados incompletos",
        "message": "La simulacion termino sin generar todos los archivos esperados.",
        "action": "Vuelve a encolar la simulacion y revisa la trazabilidad si se repite.",
    },
    "worker_error": {
        "category": "Procesamiento",
        "message": "Ocurrio un problema durante el procesamiento del caso.",
        "action": "Reintenta la simulacion desde el detalle del caso.",
    },
    "queue_error": {
        "category": "Servicio de procesamiento",
        "message": "No se pudo enviar el caso a la cola de procesamiento.",
        "action": "Verifica que Redis y el worker esten activos y vuelve a intentarlo.",
    },
}

DEFAULT_PROCESSING_ERROR_MESSAGE = {
    "category": "Procesamiento",
    "message": "Ocurrio un problema durante el procesamiento del caso.",
    "action": "Reintenta la simulacion. Si se repite, revisa la trazabilidad tecnica.",
}


@upload_bp.route("/cargar", methods=["GET", "POST"])
def upload_mammogram():
    accepted_formats = [extension.upper() for extension in sorted(ALLOWED_EXTENSIONS)]
    accepted_formats.insert(accepted_formats.index("DCM") + 1, "DICOM")

    if request.method == "POST":
        mammogram_file = request.files.get("mammogram_file")
        input_mode = _get_requested_input_mode()

        if input_mode is None:
            flash("Modalidad de entrada no valida.", "error")
            return redirect(url_for("upload.upload_mammogram"))

        validation_result = validate_mammogram_file(
            mammogram_file,
            current_app.config["MAX_CONTENT_LENGTH"],
        )

        if validation_result.is_valid:
            try:
                registration = register_case_upload(
                    mammogram_file,
                    validation_result,
                    current_app.config["UPLOAD_FOLDER"],
                    input_mode=input_mode,
                    user_id=get_current_user().id,
                )
            except (OSError, SQLAlchemyError):
                db.session.rollback()
                current_app.logger.exception("No se pudo almacenar el archivo cargado.")
                flash(
                    "No se pudo almacenar el archivo cargado. Intenta nuevamente.",
                    "error",
                )
            else:
                case = registration.case
                flash(_format_success_message(case), "success")
                return redirect(url_for("upload.case_detail", case_id=case.id))
        else:
            error_case = safe_register_upload_error(
                mammogram_file,
                validation_result,
                current_app.logger,
                input_mode=input_mode,
            )
            current_app.logger.warning(
                "Error de carga registrado. case_id=%s message=%s",
                error_case.id if error_case else "no_registrado",
                validation_result.message,
            )
            flash(validation_result.message, "error")

        return redirect(url_for("upload.upload_mammogram"))

    return render_template("upload.html", accepted_formats=accepted_formats)


@upload_bp.get("/casos")
def case_list():
    user = get_current_user()
    cases = Case.query.filter_by(user_id=user.id).order_by(Case.id.desc()).all()
    case_rows = tuple(_build_case_list_row(case) for case in cases)

    return render_template(
        "case_list.html",
        case_rows=case_rows,
        case_summary=_build_case_list_summary(cases),
    )


@upload_bp.get("/comparar")
def compare_cases():
    case_options = _get_comparable_case_options()
    selected_case_a_id = _get_optional_case_id("case_a_id")
    selected_case_b_id = _get_optional_case_id("case_b_id")
    comparison = None
    comparison_errors = []

    if selected_case_a_id is not None and selected_case_b_id is not None:
        if selected_case_a_id == selected_case_b_id:
            comparison_errors.append(
                "Selecciona dos casos distintos: no se puede comparar un caso "
                "consigo mismo."
            )

        case_a = _get_owned_case(selected_case_a_id)
        case_b = _get_owned_case(selected_case_b_id)

        if case_a is None:
            comparison_errors.append(f"No existe el caso #{selected_case_a_id}.")

        if case_b is None:
            comparison_errors.append(f"No existe el caso #{selected_case_b_id}.")

        if not comparison_errors:
            results_dir_a = _get_case_simulation_results_path(case_a)
            results_dir_b = _get_case_simulation_results_path(case_b)
            comparison = build_case_comparison(
                case_a,
                case_b,
                results_dir_a,
                results_dir_b,
            )

            for map_pair in comparison["map_pairs"]:
                map_pair["case_a_url"] = url_for(
                    "upload.case_simulation_result_image",
                    case_id=case_a.id,
                    result_key=map_pair["key"],
                )
                map_pair["case_b_url"] = url_for(
                    "upload.case_simulation_result_image",
                    case_id=case_b.id,
                    result_key=map_pair["key"],
                )

    return render_template(
        "case_compare.html",
        case_options=case_options,
        selected_case_a_id=selected_case_a_id,
        selected_case_b_id=selected_case_b_id,
        comparison=comparison,
        comparison_errors=tuple(comparison_errors),
    )


@upload_bp.get("/casos/<int:case_id>")
def case_detail(case_id):
    case = _get_owned_case(case_id)

    if case is None:
        abort(404)

    preview = _get_case_preview(case)
    simulation_metrics = _get_simulation_metrics(case)
    simulation_density_map_url = _get_simulation_density_map_url(case)
    mpc_results = _get_mpc_results(case)

    return render_template(
        "case_detail.html",
        case=case,
        created_at=_format_datetime(case.created_at),
        file_size=_format_file_size(case.file_size_bytes),
        roi_file_size=_format_optional_file_size(case.roi_size_bytes),
        simulation_input_file_size=_format_optional_generated_file_size(
            case.simulation_input_size_bytes,
        ),
        input_mode_label=_format_input_mode(case.input_mode),
        file_type_label=_format_file_type(case.file_type),
        roi_state_label=_get_roi_state_label(case),
        pgm_state_label=_get_pgm_state_label(case),
        simulation_result_state_label=_get_simulation_result_state_label(case),
        simulation_metrics=simulation_metrics,
        simulation_density_map_url=simulation_density_map_url,
        mpc_results=mpc_results,
        simulation_results_status_title=_get_simulation_results_status_title(case),
        simulation_results_status_message=_get_simulation_results_status_message(case),
        processing_error_detail=_get_processing_error_detail(case),
        case_flow_steps=_get_case_flow_steps(case),
        can_confirm_roi=_can_confirm_roi(case),
        can_crop_roi=_can_crop_roi(case, preview),
        can_retry_pgm=_can_retry_simulation_input(case),
        roi_status_title=_get_roi_status_title(case),
        roi_status_message=_get_roi_status_message(case),
        simulation_status_title=_get_simulation_status_title(case),
        simulation_status_message=_get_simulation_status_message(case),
        roi_preview_url=_get_roi_preview_url(case),
        preview_message=_get_preview_message(case, preview),
        preview_is_generated=preview.is_generated if preview else False,
        preview_url=url_for("upload.case_preview", case_id=case.id) if preview else None,
        auto_refresh_seconds=_get_auto_refresh_seconds(case),
        can_enqueue_simulation=_can_enqueue_simulation(case),
    )


@upload_bp.get("/casos/<int:case_id>/exportar/reporte")
def export_case_report(case_id):
    case = _get_owned_case(case_id)

    if case is None:
        abort(404)

    pdf_report = build_case_pdf_report(case, current_app.config["UPLOAD_FOLDER"])

    return send_file(
        pdf_report.buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=pdf_report.filename,
    )


@upload_bp.get("/casos/<int:case_id>/exportar/reporte-md")
def export_case_markdown_report(case_id):
    case = _get_owned_case(case_id)

    if case is None:
        abort(404)

    bundle = build_case_export_bundle(case, current_app.config["UPLOAD_FOLDER"])
    report_buffer = BytesIO(bundle.report_markdown.encode("utf-8"))

    return send_file(
        report_buffer,
        mimetype="text/markdown",
        as_attachment=True,
        download_name=bundle.report_filename,
    )


@upload_bp.get("/casos/<int:case_id>/exportar/paquete")
def export_case_package(case_id):
    case = _get_owned_case(case_id)

    if case is None:
        abort(404)

    bundle = build_case_export_bundle(case, current_app.config["UPLOAD_FOLDER"])
    package_buffer = build_case_results_package(bundle)

    return send_file(
        package_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=bundle.package_filename,
    )


@upload_bp.post("/casos/<int:case_id>/simulacion/preparar-pgm")
def prepare_case_simulation_input(case_id):
    case = _get_owned_case(case_id)

    if case is None:
        abort(404)

    try:
        prepare_simulation_input_for_case(case, current_app.config["UPLOAD_FOLDER"])
        db.session.commit()
        queued_job = enqueue_case_simulation(case, current_app.config)
    except (OSError, SQLAlchemyError, ValueError) as exc:
        db.session.rollback()
        current_app.logger.warning(
            "No se pudo preparar el PGM del caso %s: %s",
            case.id,
            exc,
        )
        flash(_format_pgm_preparation_error_message(exc), "error")
    except SimulationQueueError as exc:
        current_app.logger.warning(
            "No se pudo encolar la simulacion del caso %s: %s",
            case.id,
            exc,
        )
        flash(_format_queue_error_message(exc), "error")
    else:
        flash(_format_queue_success_message(queued_job), "success")

    return redirect(url_for("upload.case_detail", case_id=case.id))


@upload_bp.post("/casos/<int:case_id>/simulacion/encolar")
def enqueue_case_for_simulation(case_id):
    case = _get_owned_case(case_id)

    if case is None:
        abort(404)

    try:
        queued_job = enqueue_case_simulation(case, current_app.config)
    except (SQLAlchemyError, SimulationQueueError) as exc:
        db.session.rollback()
        current_app.logger.warning(
            "No se pudo encolar la simulacion del caso %s: %s",
            case.id,
            exc,
        )
        flash(_format_queue_error_message(exc), "error")
    else:
        flash(_format_queue_success_message(queued_job), "success")

    return redirect(url_for("upload.case_detail", case_id=case.id))


@upload_bp.route("/casos/<int:case_id>/roi/recortar", methods=["GET", "POST"])
def crop_case_roi(case_id):
    case = _get_owned_case(case_id)

    if case is None:
        abort(404)

    preview = _get_case_preview(case)

    if not _can_crop_roi(case, preview):
        flash("Este caso no tiene una mamografia completa disponible para recortar.", "error")
        return redirect(url_for("upload.case_detail", case_id=case.id))

    if request.method == "POST":
        try:
            crop = _get_requested_roi_crop()
            crop_roi_for_case(case, current_app.config["UPLOAD_FOLDER"], crop)
            db.session.commit()
        except (OSError, SQLAlchemyError, ValueError) as exc:
            db.session.rollback()
            current_app.logger.warning(
                "No se pudo recortar la ROI del caso %s: %s",
                case.id,
                exc,
            )
            flash(str(exc), "error")
        else:
            flash(
                "Recorte guardado como ROI del caso. Revisala y confirmala para "
                "preparar la simulacion automaticamente.",
                "success",
            )
            return redirect(url_for("upload.case_detail", case_id=case.id))

    return render_template(
        "crop_roi.html",
        case=case,
        preview_url=url_for("upload.case_preview", case_id=case.id),
    )


@upload_bp.post("/casos/<int:case_id>/roi/confirmar")
def confirm_case_roi(case_id):
    case = _get_owned_case(case_id)

    if case is None:
        abort(404)

    if not case.roi_file_path:
        flash("No existe una ROI asociada para confirmar en este caso.", "error")
        return redirect(url_for("upload.case_detail", case_id=case.id))

    if _is_roi_confirmed_state(case):
        flash("La ROI de este caso ya se encuentra confirmada.", "warning")
        return redirect(url_for("upload.case_detail", case_id=case.id))

    try:
        case.status = CaseStatus.ROI_CONFIRMED
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("No se pudo confirmar la ROI del caso %s.", case.id)
        flash("No se pudo confirmar la ROI. Intenta nuevamente.", "error")
        return redirect(url_for("upload.case_detail", case_id=case.id))

    _auto_prepare_simulation_input(case)
    return redirect(url_for("upload.case_detail", case_id=case.id))


def _auto_prepare_simulation_input(case):
    try:
        prepare_simulation_input_for_case(case, current_app.config["UPLOAD_FOLDER"])
        db.session.commit()
    except (OSError, SQLAlchemyError, ValueError) as exc:
        db.session.rollback()
        current_app.logger.warning(
            "No se pudo preparar automaticamente el PGM del caso %s: %s",
            case.id,
            exc,
        )
        flash(
            f"ROI confirmada para el caso #{case.id}. No se pudo generar el archivo "
            f"PGM automaticamente. {_format_pgm_preparation_error_message(exc)}",
            "warning",
        )
    else:
        _auto_enqueue_simulation(case)


def _auto_enqueue_simulation(case):
    try:
        queued_job = enqueue_case_simulation(case, current_app.config)
    except (SQLAlchemyError, SimulationQueueError) as exc:
        db.session.rollback()
        current_app.logger.warning(
            "No se pudo encolar automaticamente la simulacion del caso %s: %s",
            case.id,
            exc,
        )
        flash(
            f"ROI confirmada y archivo PGM generado para el caso #{case.id}, "
            f"pero no se pudo enviar a procesamiento. {_format_queue_error_message(exc)}",
            "warning",
        )
    else:
        flash(
            f"ROI confirmada, archivo PGM generado y simulacion encolada "
            f"para el caso #{queued_job.case_id}.",
            "success",
        )


@upload_bp.get("/casos/<int:case_id>/roi/vista-previa")
def case_roi_preview(case_id):
    case = _get_owned_case(case_id)

    if case is None:
        abort(404)

    roi_path = _get_case_roi_path(case)

    if roi_path is None or not roi_path.exists():
        abort(404)

    preview = ensure_preview_for_path(roi_path)

    if preview is None:
        abort(404)

    return send_file(preview.absolute_path, mimetype=preview.mimetype)


@upload_bp.get("/casos/<int:case_id>/simulacion/mapa-densidad")
def case_simulation_density_map(case_id):
    case = _get_owned_case(case_id)

    if case is None:
        abort(404)

    density_map_path = _resolve_storage_path(case.simulation_density_map_file_path)

    if density_map_path is None or not density_map_path.exists():
        abort(404)

    preview = ensure_preview_for_path(density_map_path)

    if preview is None:
        abort(404)

    return send_file(preview.absolute_path, mimetype=preview.mimetype)


@upload_bp.get("/casos/<int:case_id>/simulacion/resultados/<result_key>")
def case_simulation_result_image(case_id, result_key):
    case = _get_owned_case(case_id)

    if case is None:
        abort(404)

    results_dir = _get_case_simulation_results_path(case)

    if results_dir is None or not results_dir.exists():
        abort(404)

    result_path = get_result_image_path(results_dir, result_key)

    if result_path is None or not result_path.exists():
        abort(404)

    preview = ensure_preview_for_path(result_path)

    if preview is None:
        abort(404)

    return send_file(preview.absolute_path, mimetype=preview.mimetype)


@upload_bp.get("/casos/<int:case_id>/vista-previa")
def case_preview(case_id):
    case = _get_owned_case(case_id)

    if case is None:
        abort(404)

    preview = _get_case_preview(case)

    if preview is None:
        abort(404)

    return send_file(preview.absolute_path, mimetype=preview.mimetype)


@upload_bp.app_errorhandler(RequestEntityTooLarge)
def handle_request_entity_too_large(error):
    max_size = current_app.config["MAX_CONTENT_LENGTH"]
    message = f"El archivo supera el tamano maximo permitido de {_format_file_size(max_size)}."
    error_case = safe_register_request_size_error(message, current_app.logger)
    current_app.logger.warning(
        "Error de tamano de carga registrado. case_id=%s message=%s",
        error_case.id if error_case else "no_registrado",
        message,
    )
    flash(message, "error")
    return redirect(url_for("upload.upload_mammogram"))


def _get_requested_input_mode():
    input_mode = request.form.get("input_mode", InputMode.MAMMOGRAM)

    if input_mode not in InputMode.values():
        return None

    return input_mode


def _get_optional_case_id(field_name):
    raw_value = request.args.get(field_name)

    if not raw_value:
        return None

    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _get_requested_roi_crop():
    try:
        return RoiCrop(
            x=int(float(request.form.get("x", ""))),
            y=int(float(request.form.get("y", ""))),
            width=int(float(request.form.get("width", ""))),
            height=int(float(request.form.get("height", ""))),
        )
    except (TypeError, ValueError):
        raise ValueError("Selecciona una region valida antes de guardar la ROI.")


def _format_success_message(case):
    if case.input_mode == InputMode.ROI:
        return (
            f"Caso #{case.id} creado con la ROI cargada. "
            "Revisa la vista previa y confirma la ROI para preparar la simulacion."
        )

    return (
        f"Caso #{case.id} creado a partir de la mamografia. "
        "Ahora recorta la region de interes (ROI) sobre la imagen para continuar."
    )


def _format_queue_success_message(queued_job):
    if queued_job.already_queued:
        return (
            f"La simulacion del caso #{queued_job.case_id} ya estaba en cola "
            "para procesamiento."
        )

    return (
        f"Simulacion del caso #{queued_job.case_id} encolada para procesamiento. "
        "El worker ejecutara Julia automaticamente."
    )


def _format_pgm_preparation_error_message(exc):
    if isinstance(exc, ValueError):
        return str(exc)

    return (
        "No se pudo preparar la entrada PGM para la simulacion. "
        "Revisa que la ROI este disponible y vuelve a intentarlo."
    )


def _format_queue_error_message(exc):
    message = str(exc)

    if "Redis" in message or "cola" in message.lower():
        return (
            "No se pudo enviar el caso a procesamiento en este momento. "
            "Verifica que el servicio del worker este activo y vuelve a intentarlo."
        )

    return message or "No se pudo enviar el caso a procesamiento. Intenta nuevamente."


def _get_processing_error_copy(error_category):
    return PROCESSING_ERROR_MESSAGES.get(
        error_category or "",
        DEFAULT_PROCESSING_ERROR_MESSAGE,
    )


def _get_case_error_context(case):
    worker_log_path = _get_worker_log_path(case)
    worker_log = _read_worker_log_summary(worker_log_path)
    error_category = worker_log.get("error_category") or _infer_error_category(
        case.error_message,
    )
    error_copy = _get_processing_error_copy(error_category)
    technical_message = worker_log.get("error_message") or case.error_message or ""

    return {
        "message": error_copy["message"],
        "action": error_copy["action"],
        "category": error_copy["category"],
        "technical_category": error_category,
        "technical_message": technical_message or "No registrado",
        "timeout": _format_timeout_for_user(worker_log.get("timeout_seconds")),
        "log_path": worker_log.get("run_log_path")
        or (str(worker_log_path) if worker_log_path is not None else "No registrado"),
    }


def _infer_error_category(error_message):
    normalized_message = (error_message or "").lower()

    if "redis" in normalized_message or "cola" in normalized_message:
        return "queue_error"

    if "pgm" in normalized_message:
        return "invalid_pgm"

    if "roi" in normalized_message:
        return "missing_roi"

    return "worker_error"


def _format_timeout_for_user(timeout_seconds):
    if not timeout_seconds:
        return "Sin limite configurado"

    if str(timeout_seconds).lower() in {"none", "null", "0", "unlimited"}:
        return "Sin limite configurado"

    return f"{timeout_seconds} segundos"


def _format_error_message_for_list(case):
    if case.status != CaseStatus.ERROR:
        return None

    error_context = _get_case_error_context(case)
    return error_context["message"]


def _format_datetime(value):
    if value is None:
        return "No registrado"

    return value.strftime("%Y-%m-%d %H:%M:%S")


def _format_file_size(size_bytes):
    if size_bytes is None:
        return "No registrado"

    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"

    return f"{size_bytes} bytes"


def _format_optional_file_size(size_bytes):
    if size_bytes is None:
        return "Pendiente de asociar"

    return _format_file_size(size_bytes)


def _format_optional_generated_file_size(size_bytes):
    if size_bytes is None:
        return "Pendiente de generar"

    return _format_file_size(size_bytes)


def _format_input_mode(input_mode):
    if input_mode == InputMode.ROI:
        return "ROI recortada"

    return "Mamografia completa"


def _format_file_type(file_type):
    if file_type == "image":
        return "Imagen"

    if file_type == "dicom":
        return "DICOM"

    return file_type or "No registrado"


def _format_status_label(status):
    status_labels = {
        CaseStatus.REGISTERED: "Registrado",
        CaseStatus.ROI_CONFIRMED: "ROI confirmada",
        CaseStatus.PENDING: "En cola",
        CaseStatus.PROCESSING: "Procesando",
        CaseStatus.COMPLETED: "Completado",
        CaseStatus.ERROR: "Error",
        CaseStatus.NOTIFIED: "Notificado",
    }

    return status_labels.get(status, status or "No registrado")


def _get_roi_state_label(case):
    if _is_roi_confirmed_state(case):
        return "Confirmada"

    if case.roi_file_path:
        return "Asociada (pendiente de confirmar)"

    return "Pendiente"


def _build_case_list_row(case):
    has_results = case.status == CaseStatus.COMPLETED and _has_simulation_results(case)

    return {
        "id": case.id,
        "created_at": _format_datetime(case.created_at),
        "original_filename": case.original_filename,
        "input_mode": _format_input_mode(case.input_mode),
        "file_type": _format_file_type(case.file_type),
        "file_size": _format_file_size(case.file_size_bytes),
        "status": case.status,
        "status_label": _format_status_label(case.status),
        "roi_state": _get_roi_state_label(case),
        "pgm_state": _get_pgm_state_label(case),
        "results_state": _get_simulation_result_state_label(case),
        "has_results": has_results,
        "primary_action": _get_case_list_primary_action(case, has_results),
        "detail_url": url_for("upload.case_detail", case_id=case.id),
        "results_url": url_for("upload.case_detail", case_id=case.id)
        + "#simulation-results",
        "report_url": url_for("upload.export_case_report", case_id=case.id),
        "crop_url": url_for("upload.crop_case_roi", case_id=case.id),
        "error_message": _format_error_message_for_list(case),
    }


def _build_case_list_summary(cases):
    return {
        "total": len(cases),
        "completed": sum(1 for case in cases if case.status == CaseStatus.COMPLETED),
        "processing": sum(
            1
            for case in cases
            if case.status in {CaseStatus.PENDING, CaseStatus.PROCESSING}
        ),
        "errors": sum(1 for case in cases if case.status == CaseStatus.ERROR),
    }


def _get_case_list_primary_action(case, has_results):
    if has_results:
        return {
            "label": "Ver resultados",
            "url": url_for("upload.case_detail", case_id=case.id) + "#simulation-results",
        }

    if case.status == CaseStatus.COMPLETED:
        return {
            "label": "Revisar resultados",
            "url": url_for("upload.case_detail", case_id=case.id) + "#simulation-results",
        }

    if case.status == CaseStatus.PROCESSING:
        return {
            "label": "Seguir proceso",
            "url": url_for("upload.case_detail", case_id=case.id),
        }

    if case.status == CaseStatus.PENDING:
        return {
            "label": "Ver cola",
            "url": url_for("upload.case_detail", case_id=case.id),
        }

    if case.status == CaseStatus.ERROR:
        return {
            "label": "Revisar error",
            "url": url_for("upload.case_detail", case_id=case.id),
        }

    if case.input_mode == InputMode.MAMMOGRAM and not case.roi_file_path:
        return {
            "label": "Recortar ROI",
            "url": url_for("upload.crop_case_roi", case_id=case.id),
        }

    if case.roi_file_path and not _is_roi_confirmed_state(case):
        return {
            "label": "Confirmar ROI",
            "url": url_for("upload.case_detail", case_id=case.id),
        }

    if case.status == CaseStatus.ROI_CONFIRMED and not case.simulation_input_file_path:
        return {
            "label": "Preparar PGM",
            "url": url_for("upload.case_detail", case_id=case.id),
        }

    if case.simulation_input_file_path:
        return {
            "label": "Encolar simulacion",
            "url": url_for("upload.case_detail", case_id=case.id),
        }

    return {
        "label": "Ver detalle",
        "url": url_for("upload.case_detail", case_id=case.id),
    }


def _get_pgm_state_label(case):
    if case.simulation_input_file_path:
        return "Generado"

    if _is_roi_confirmed_state(case):
        return "Pendiente de preparacion"

    return "Pendiente de ROI"


def _get_case_flow_steps(case):
    return (
        {
            "number": "1",
            "title": "Registro",
            "detail": _format_input_mode(case.input_mode),
            "state": "complete",
        },
        {
            "number": "2",
            "title": "ROI",
            "detail": _get_roi_flow_detail(case),
            "state": _get_roi_flow_state(case),
        },
        {
            "number": "3",
            "title": "PGM",
            "detail": _get_pgm_flow_detail(case),
            "state": _get_pgm_flow_state(case),
        },
        {
            "number": "4",
            "title": "Resultados",
            "detail": _get_results_flow_detail(case),
            "state": _get_results_flow_state(case),
        },
    )


def _get_roi_flow_state(case):
    if _is_roi_confirmed_state(case):
        return "complete"

    if case.roi_file_path:
        return "active"

    return "pending"


def _get_roi_flow_detail(case):
    if _is_roi_confirmed_state(case):
        return "ROI confirmada"

    if case.roi_file_path:
        return "Pendiente de confirmar"

    return "Pendiente de asociar"


def _get_pgm_flow_state(case):
    if case.simulation_input_file_path:
        return "complete"

    if case.status == CaseStatus.ROI_CONFIRMED:
        return "active"

    return "pending"


def _get_pgm_flow_detail(case):
    if case.simulation_input_file_path:
        return "Entrada generada"

    if _is_roi_confirmed_state(case):
        return "Pendiente de preparacion"

    return "Pendiente de ROI"


def _get_results_flow_state(case):
    if case.status == CaseStatus.COMPLETED and _has_simulation_results(case):
        return "complete"

    if case.status in {CaseStatus.PENDING, CaseStatus.PROCESSING, CaseStatus.ERROR}:
        return "active"

    if case.status == CaseStatus.COMPLETED:
        return "active"

    if case.simulation_input_file_path:
        return "active"

    return "pending"


def _get_results_flow_detail(case):
    if case.status == CaseStatus.COMPLETED and _has_simulation_results(case):
        return "Resultados disponibles"

    if case.status == CaseStatus.PROCESSING:
        return "Procesando"

    if case.status == CaseStatus.PENDING:
        return "En cola"

    if case.status == CaseStatus.ERROR:
        return "Error registrado"

    if case.status == CaseStatus.COMPLETED:
        return "Resultados no disponibles"

    if case.simulation_input_file_path:
        return "Pendiente de ejecucion"

    return "Pendiente de PGM"


def _get_roi_status_title(case):
    if _is_roi_confirmed_state(case):
        return "ROI confirmada"

    if case.roi_file_path:
        return "ROI cargada"

    return "ROI pendiente"


def _get_roi_status_message(case):
    if case.status == CaseStatus.PENDING:
        return "La ROI esta confirmada y la simulacion quedo en cola."

    if case.status == CaseStatus.PROCESSING:
        return "La ROI esta confirmada y el worker esta procesando el caso."

    if _is_roi_confirmed_state(case):
        return "La ROI esta confirmada. La preparacion y simulacion se realizan automaticamente."

    if case.roi_file_path:
        return (
            "La ROI ya esta asociada al caso. Al confirmarla se generara "
            "automaticamente el archivo PGM para la simulacion."
        )

    return (
        "Aun no hay una ROI asociada. Recorta la region de interes sobre la "
        "mamografia para continuar."
    )


def _can_confirm_roi(case):
    return bool(case.roi_file_path) and case.status == CaseStatus.REGISTERED


def _can_prepare_simulation_input(case):
    return bool(case.roi_file_path) and case.status == CaseStatus.ROI_CONFIRMED


def _can_retry_simulation_input(case):
    return _can_prepare_simulation_input(case) and not case.simulation_input_file_path


def _can_enqueue_simulation(case):
    return bool(case.simulation_input_file_path) and case.status in {
        CaseStatus.ROI_CONFIRMED,
        CaseStatus.ERROR,
    }


def _get_simulation_status_title(case):
    if case.status == CaseStatus.PENDING:
        return "Simulacion en cola"

    if case.status == CaseStatus.PROCESSING:
        return "Simulacion en proceso"

    if case.status == CaseStatus.COMPLETED:
        return "Simulacion completada"

    if case.status == CaseStatus.ERROR:
        return "Simulacion con error"

    if case.simulation_input_file_path:
        return "PGM generado"

    return "Entrada PGM pendiente"


def _get_simulation_status_message(case):
    if case.status == CaseStatus.PENDING:
        return "El caso ya esta en cola. El worker lo tomara automaticamente."

    if case.status == CaseStatus.PROCESSING:
        return "El worker esta ejecutando la simulacion del caso."

    if case.status == CaseStatus.COMPLETED:
        return "La simulacion termino y los resultados estan disponibles."

    if case.status == CaseStatus.ERROR:
        error_context = _get_case_error_context(case)
        return f"{error_context['message']} {error_context['action']}"

    if case.simulation_input_file_path:
        return "La ROI confirmada ya cuenta con su archivo PGM para la simulacion."

    if case.status == CaseStatus.ROI_CONFIRMED:
        return (
            "No se pudo generar el PGM automaticamente. Reintenta la preparacion "
            "para dejar el caso listo."
        )

    return "Al confirmar la ROI se generara automaticamente el archivo PGM."


def _get_simulation_result_state_label(case):
    if case.status == CaseStatus.COMPLETED and _has_simulation_results(case):
        return "Disponibles"

    if case.status == CaseStatus.PROCESSING:
        return "Procesando"

    if case.status == CaseStatus.PENDING:
        return "En cola"

    if case.status == CaseStatus.ERROR:
        return "Error"

    if case.status == CaseStatus.COMPLETED:
        return "No disponibles"

    if case.simulation_input_file_path:
        return "Pendiente de procesamiento"

    return "Pendiente"


def _get_simulation_results_status_title(case):
    if case.status == CaseStatus.COMPLETED and _has_simulation_results(case):
        return "Resultados disponibles"

    if case.status == CaseStatus.PROCESSING:
        return "Procesamiento en curso"

    if case.status == CaseStatus.PENDING:
        return "Procesamiento en cola"

    if case.status == CaseStatus.ERROR:
        return "Procesamiento con error"

    if case.status == CaseStatus.COMPLETED:
        return "Resultados no disponibles"

    if case.simulation_input_file_path:
        return "Listo para procesamiento"

    return "Resultados pendientes"


def _get_simulation_results_status_message(case):
    if case.status == CaseStatus.COMPLETED and _has_simulation_results(case):
        return (
            "El caso tiene resultados MPC, mapas de concentracion y metricas "
            "relativas de difusion asociadas."
        )

    if case.status == CaseStatus.PROCESSING:
        return "El worker esta ejecutando la simulacion del caso."

    if case.status == CaseStatus.PENDING:
        return (
            "El caso esta en cola. Esta pagina se actualizara mientras el worker "
            "genera los resultados."
        )

    if case.status == CaseStatus.ERROR:
        error_context = _get_case_error_context(case)
        return f"{error_context['message']} {error_context['action']}"

    if case.status == CaseStatus.COMPLETED:
        return "El caso figura como completado, pero no se encontraron los archivos de resultados."

    if case.simulation_input_file_path:
        return "La entrada PGM esta preparada para que el worker ejecute la simulacion."

    return "Los resultados apareceran cuando exista una entrada PGM procesada."


def _get_processing_error_detail(case):
    if case.status != CaseStatus.ERROR:
        return None

    return _get_case_error_context(case)


def _get_worker_log_path(case):
    results_dir = _get_case_simulation_results_path(case)

    if results_dir is None:
        return None

    worker_log_path = results_dir / "worker_execution.log"

    if worker_log_path.exists():
        return worker_log_path

    return None


def _read_worker_log_summary(worker_log_path):
    summary = {}

    if worker_log_path is None:
        return summary

    try:
        lines = worker_log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return summary

    for line in lines:
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        if key in {
            "error_category",
            "error_message",
            "run_log_path",
            "timeout_seconds",
            "status",
        }:
            summary[key] = value.strip()

    return summary


def _get_auto_refresh_seconds(case):
    if case.status in {CaseStatus.PENDING, CaseStatus.PROCESSING}:
        return 5

    return None


def _is_roi_confirmed_state(case):
    return bool(case.roi_file_path) and case.status in {
        CaseStatus.ROI_CONFIRMED,
        CaseStatus.PENDING,
        CaseStatus.PROCESSING,
        CaseStatus.COMPLETED,
        CaseStatus.ERROR,
        CaseStatus.NOTIFIED,
    }


def _get_simulation_metrics(case):
    metrics_path = _resolve_storage_path(case.simulation_metrics_file_path)

    if metrics_path is None or not metrics_path.exists():
        return ()

    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        current_app.logger.warning(
            "No se pudieron leer las metricas del caso %s.",
            case.id,
        )
        return ()

    formatted_metrics = []
    for label, key, value_type in SIMULATION_METRIC_FIELDS:
        if key not in metrics:
            continue

        formatted_metrics.append(
            {
                "label": label,
                "value": _format_metric_value(metrics[key], value_type),
            }
        )

    return tuple(formatted_metrics)


def _get_simulation_density_map_url(case):
    density_map_path = _resolve_storage_path(case.simulation_density_map_file_path)

    if density_map_path is None or not density_map_path.exists():
        return None

    return url_for("upload.case_simulation_density_map", case_id=case.id)


def _get_mpc_results(case):
    results_dir = _get_case_simulation_results_path(case)
    results_view = build_mpc_results_view(results_dir)

    for result_map in (
        list(results_view["domain_maps"]) + list(results_view["concentration_maps"])
    ):
        result_map["url"] = url_for(
            "upload.case_simulation_result_image",
            case_id=case.id,
            result_key=result_map["key"],
        )

    return results_view


def _get_comparable_case_options():
    user = get_current_user()
    completed_cases = (
        Case.query.filter_by(user_id=user.id, status=CaseStatus.COMPLETED)
        .order_by(Case.id.desc())
        .all()
    )
    options = []

    for case in completed_cases:
        results_dir = _get_case_simulation_results_path(case)

        if not is_case_mpc_comparable(results_dir):
            continue

        options.append(
            {
                "id": case.id,
                "label": f"Caso #{case.id} - {_format_datetime(case.created_at)}",
                "input_mode": _format_input_mode(case.input_mode),
            }
        )

    return tuple(options)


def _get_case_simulation_results_path(case):
    return _resolve_storage_path(case.simulation_results_path)


def _has_simulation_results(case):
    metrics_path = _resolve_storage_path(case.simulation_metrics_file_path)
    density_map_path = _resolve_storage_path(case.simulation_density_map_file_path)

    return bool(
        metrics_path is not None
        and metrics_path.exists()
        and density_map_path is not None
        and density_map_path.exists()
    )


def _format_metric_value(value, value_type):
    if value_type == "percent":
        try:
            return f"{float(value) * 100:.2f}%"
        except (TypeError, ValueError):
            return "No disponible"

    if value_type == "integer":
        try:
            return f"{int(value):,}".replace(",", ".")
        except (TypeError, ValueError):
            return "No disponible"

    return str(value)


def _can_crop_roi(case, preview):
    return case.input_mode == InputMode.MAMMOGRAM and preview is not None


def _get_roi_preview_url(case):
    roi_path = _get_case_roi_path(case)

    if roi_path is None or not roi_path.exists():
        return None

    return url_for("upload.case_roi_preview", case_id=case.id)


def _get_case_roi_path(case):
    if not case.roi_file_path:
        return None

    roi_filename = Path(case.roi_file_path).name

    return get_case_roi_directory(
        case.id,
        current_app.config["UPLOAD_FOLDER"],
    ) / roi_filename


def _resolve_storage_path(stored_path):
    if not stored_path:
        return None

    path = Path(stored_path)

    if path.is_absolute():
        return path

    cwd_candidate = Path.cwd() / path
    if cwd_candidate.exists():
        return cwd_candidate

    repo_candidate = Path.cwd().parent / path
    if repo_candidate.exists():
        return repo_candidate

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    parts = path.parts

    if "uploads" in parts:
        uploads_index = parts.index("uploads")
        relative_to_uploads = Path(*parts[uploads_index + 1 :])
        return upload_folder / relative_to_uploads

    return upload_folder / path


def _get_case_preview(case):
    try:
        return ensure_preview_for_case(case, current_app.config["UPLOAD_FOLDER"])
    except (AttributeError, OSError, TypeError, ValueError):
        current_app.logger.exception(
            "No se pudo generar la vista previa del caso %s.",
            case.id,
        )
        return None


def _get_preview_message(case, preview):
    if preview is not None:
        if case.file_type == "dicom":
            return "Vista previa DICOM generada en formato PNG."

        if preview.is_generated:
            return "Archivo compatible convertido a vista previa PNG."

        return "Archivo original compatible con visualizacion web."

    if case.file_type == "dicom":
        return (
            "No se pudo generar una vista previa para este DICOM. "
            "El caso se conserva registrado para continuar el flujo."
        )

    return "La vista previa inicial aplica para PNG, JPG, JPEG, BMP, TIF, TIFF y DICOM."
