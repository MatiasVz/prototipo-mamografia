from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import RequestEntityTooLarge

from ..extensions import db
from ..services.case_registration_service import register_mammogram_upload
from ..services.file_validation import ALLOWED_EXTENSIONS, validate_mammogram_file


upload_bp = Blueprint("upload", __name__, url_prefix="/mamografias")


@upload_bp.route("/cargar", methods=["GET", "POST"])
def upload_mammogram():
    accepted_formats = [extension.upper() for extension in sorted(ALLOWED_EXTENSIONS)]
    accepted_formats.insert(accepted_formats.index("DCM") + 1, "DICOM")

    if request.method == "POST":
        mammogram_file = request.files.get("mammogram_file")
        validation_result = validate_mammogram_file(
            mammogram_file,
            current_app.config["MAX_CONTENT_LENGTH"],
        )

        if validation_result.is_valid:
            try:
                registration = register_mammogram_upload(
                    mammogram_file,
                    validation_result,
                    current_app.config["UPLOAD_FOLDER"],
                )
            except (OSError, SQLAlchemyError):
                db.session.rollback()
                current_app.logger.exception("No se pudo almacenar la mamografia.")
                flash(
                    "No se pudo almacenar el archivo cargado. Intenta nuevamente.",
                    "error",
                )
            else:
                case = registration.case
                metadata_message = _format_metadata_message(validation_result.metadata)
                flash(
                    f"{validation_result.message} ID del caso: {case.id}. "
                    f"Ruta registrada: {case.original_file_path}. "
                    f"Estado inicial: {case.status}." + metadata_message,
                    "success",
                )
        else:
            flash(validation_result.message, "error")

        return redirect(url_for("upload.upload_mammogram"))

    return render_template("upload.html", accepted_formats=accepted_formats)


@upload_bp.app_errorhandler(RequestEntityTooLarge)
def handle_request_entity_too_large(error):
    max_size = current_app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024)
    flash(f"El archivo supera el tamano maximo permitido de {max_size:.0f} MB.", "error")
    return redirect(url_for("upload.upload_mammogram"))


def _format_metadata_message(metadata):
    if not metadata:
        return " La confirmacion de ROI se implementara en una issue posterior."

    readable_metadata = ", ".join(f"{key}: {value}" for key, value in metadata.items())
    return (
        f" Metadatos extraidos: {readable_metadata}. "
        "La confirmacion de ROI se implementara en una issue posterior."
    )
