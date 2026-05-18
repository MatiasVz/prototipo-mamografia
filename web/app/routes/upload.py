from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import RequestEntityTooLarge

from ..extensions import db
from ..models import Case, CaseStatus, InputMode
from ..services.file_validation import ALLOWED_EXTENSIONS, validate_mammogram_file
from ..services.storage_service import store_original_file


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
                case = Case(
                    input_mode=InputMode.MAMMOGRAM,
                    original_filename=mammogram_file.filename,
                    original_file_path="",
                    file_type=validation_result.file_type,
                    file_size_bytes=validation_result.size_bytes or 0,
                    status=CaseStatus.REGISTERED,
                )
                db.session.add(case)
                db.session.flush()

                stored_file = store_original_file(
                    mammogram_file,
                    case.id,
                    validation_result.extension,
                    current_app.config["UPLOAD_FOLDER"],
                )
                case.original_filename = stored_file.original_filename
                case.original_file_path = stored_file.relative_path
                db.session.commit()
            except (OSError, SQLAlchemyError):
                db.session.rollback()
                current_app.logger.exception("No se pudo almacenar la mamografia.")
                flash(
                    "No se pudo almacenar el archivo cargado. Intenta nuevamente.",
                    "error",
                )
            else:
                metadata_message = _format_metadata_message(validation_result.metadata)
                flash(
                    f"{validation_result.message} Caso #{case.id} registrado en "
                    f"{stored_file.relative_path}." + metadata_message,
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
