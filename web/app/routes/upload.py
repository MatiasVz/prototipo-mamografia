from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from werkzeug.exceptions import RequestEntityTooLarge

from ..services.file_validation import ALLOWED_IMAGE_EXTENSIONS, validate_image_file


upload_bp = Blueprint("upload", __name__, url_prefix="/mamografias")


@upload_bp.route("/cargar", methods=["GET", "POST"])
def upload_mammogram():
    accepted_formats = [extension.upper() for extension in sorted(ALLOWED_IMAGE_EXTENSIONS)]

    if request.method == "POST":
        mammogram_file = request.files.get("mammogram_file")
        validation_result = validate_image_file(
            mammogram_file,
            current_app.config["MAX_CONTENT_LENGTH"],
        )

        if validation_result.is_valid:
            flash(
                "Imagen validada correctamente. El almacenamiento del archivo se "
                "implementara en una issue posterior.",
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
