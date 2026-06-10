import json
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
from ..services.case_registration_service import register_case_upload
from ..services.file_validation import ALLOWED_EXTENSIONS, validate_mammogram_file
from ..services.preview_service import ensure_preview_for_case, ensure_preview_for_path
from ..services.roi_service import RoiCrop, crop_roi_for_case
from ..services.simulation_preparation_service import prepare_simulation_input_for_case
from ..services.storage_service import get_case_roi_directory
from ..services.upload_error_service import (
    safe_register_request_size_error,
    safe_register_upload_error,
)


upload_bp = Blueprint("upload", __name__, url_prefix="/mamografias")

SIMULATION_METRIC_FIELDS = (
    ("Particulas", "particle_count", "integer"),
    ("Pasos", "steps", "integer"),
    ("Obstaculos", "obstacle_count", "integer"),
    ("Celdas visitadas", "visited_cell_count", "integer"),
    ("Choques", "collision_count", "integer"),
    ("Tasa de colision", "collision_rate", "percent"),
    ("Maximo de visitas", "max_visits", "integer"),
)


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


@upload_bp.get("/casos/<int:case_id>")
def case_detail(case_id):
    case = db.session.get(Case, case_id)

    if case is None:
        abort(404)

    preview = _get_case_preview(case)
    simulation_metrics = _get_simulation_metrics(case)
    simulation_density_map_url = _get_simulation_density_map_url(case)

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
        simulation_results_status_title=_get_simulation_results_status_title(case),
        simulation_results_status_message=_get_simulation_results_status_message(case),
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
    )


@upload_bp.post("/casos/<int:case_id>/simulacion/preparar-pgm")
def prepare_case_simulation_input(case_id):
    case = db.session.get(Case, case_id)

    if case is None:
        abort(404)

    try:
        prepare_simulation_input_for_case(case, current_app.config["UPLOAD_FOLDER"])
        db.session.commit()
    except (OSError, SQLAlchemyError, ValueError) as exc:
        db.session.rollback()
        current_app.logger.warning(
            "No se pudo preparar el PGM del caso %s: %s",
            case.id,
            exc,
        )
        flash(str(exc), "error")
    else:
        flash("Archivo PGM generado para la simulacion.", "success")

    return redirect(url_for("upload.case_detail", case_id=case.id))


@upload_bp.route("/casos/<int:case_id>/roi/recortar", methods=["GET", "POST"])
def crop_case_roi(case_id):
    case = db.session.get(Case, case_id)

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
    case = db.session.get(Case, case_id)

    if case is None:
        abort(404)

    if not case.roi_file_path:
        flash("No existe una ROI asociada para confirmar en este caso.", "error")
        return redirect(url_for("upload.case_detail", case_id=case.id))

    if case.status == CaseStatus.ROI_CONFIRMED:
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
            f"PGM automaticamente ({exc}). Puedes reintentar la preparacion desde el detalle.",
            "warning",
        )
    else:
        flash(
            f"ROI confirmada y archivo PGM generado para el caso #{case.id}. "
            "El caso queda listo para la etapa de simulacion.",
            "success",
        )


@upload_bp.get("/casos/<int:case_id>/roi/vista-previa")
def case_roi_preview(case_id):
    case = db.session.get(Case, case_id)

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
    case = db.session.get(Case, case_id)

    if case is None:
        abort(404)

    density_map_path = _resolve_storage_path(case.simulation_density_map_file_path)

    if density_map_path is None or not density_map_path.exists():
        abort(404)

    preview = ensure_preview_for_path(density_map_path)

    if preview is None:
        abort(404)

    return send_file(preview.absolute_path, mimetype=preview.mimetype)


@upload_bp.get("/casos/<int:case_id>/vista-previa")
def case_preview(case_id):
    case = db.session.get(Case, case_id)

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


def _get_roi_state_label(case):
    if case.status == CaseStatus.ROI_CONFIRMED:
        return "Confirmada"

    if case.roi_file_path:
        return "Asociada (pendiente de confirmar)"

    return "Pendiente"


def _get_pgm_state_label(case):
    if case.simulation_input_file_path:
        return "Generado"

    if case.status == CaseStatus.ROI_CONFIRMED:
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
    if case.status == CaseStatus.ROI_CONFIRMED:
        return "complete"

    if case.roi_file_path:
        return "active"

    return "pending"


def _get_roi_flow_detail(case):
    if case.status == CaseStatus.ROI_CONFIRMED:
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

    if case.status == CaseStatus.ROI_CONFIRMED:
        return "Pendiente de preparacion"

    return "Pendiente de ROI"


def _get_results_flow_state(case):
    if case.status == CaseStatus.COMPLETED and _has_simulation_results(case):
        return "complete"

    if case.status in {CaseStatus.PROCESSING, CaseStatus.ERROR}:
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

    if case.status == CaseStatus.ERROR:
        return "Error registrado"

    if case.status == CaseStatus.COMPLETED:
        return "Resultados no disponibles"

    if case.simulation_input_file_path:
        return "Pendiente de ejecucion"

    return "Pendiente de PGM"


def _get_roi_status_title(case):
    if case.status == CaseStatus.ROI_CONFIRMED:
        return "ROI confirmada"

    if case.roi_file_path:
        return "ROI cargada"

    return "ROI pendiente"


def _get_roi_status_message(case):
    if case.status == CaseStatus.ROI_CONFIRMED:
        return "La ROI esta confirmada. El archivo PGM se prepara automaticamente."

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
    return bool(case.roi_file_path) and case.status != CaseStatus.ROI_CONFIRMED


def _can_prepare_simulation_input(case):
    return bool(case.roi_file_path) and case.status == CaseStatus.ROI_CONFIRMED


def _can_retry_simulation_input(case):
    return _can_prepare_simulation_input(case) and not case.simulation_input_file_path


def _get_simulation_status_title(case):
    if case.simulation_input_file_path:
        return "PGM generado"

    return "Entrada PGM pendiente"


def _get_simulation_status_message(case):
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

    if case.status == CaseStatus.ERROR:
        return "Procesamiento con error"

    if case.status == CaseStatus.COMPLETED:
        return "Resultados no disponibles"

    if case.simulation_input_file_path:
        return "Listo para procesamiento"

    return "Resultados pendientes"


def _get_simulation_results_status_message(case):
    if case.status == CaseStatus.COMPLETED and _has_simulation_results(case):
        return "El caso tiene metricas preliminares y mapa de densidad asociados."

    if case.status == CaseStatus.PROCESSING:
        return "El worker esta ejecutando la simulacion del caso."

    if case.status == CaseStatus.ERROR:
        return case.error_message or "Se registro un error durante el procesamiento."

    if case.status == CaseStatus.COMPLETED:
        return "El caso figura como completado, pero no se encontraron los archivos de resultados."

    if case.simulation_input_file_path:
        return "La entrada PGM esta preparada para que el worker ejecute la simulacion."

    return "Los resultados apareceran cuando exista una entrada PGM procesada."


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
            return "Vista previa DICOM generada como preview.png."

        if preview.is_generated:
            return "Archivo compatible generado como preview.png."

        return "Archivo original compatible con visualizacion web."

    if case.file_type == "dicom":
        return (
            "No se pudo generar una vista previa para este DICOM. "
            "El caso se conserva registrado para continuar el flujo."
        )

    return "La vista previa inicial aplica para PNG, JPG, JPEG, BMP, TIF, TIFF y DICOM."
