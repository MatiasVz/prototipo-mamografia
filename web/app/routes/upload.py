from flask import Blueprint, flash, redirect, render_template, request, url_for


upload_bp = Blueprint("upload", __name__, url_prefix="/mamografias")


@upload_bp.route("/cargar", methods=["GET", "POST"])
def upload_mammogram():
    accepted_formats = ["PNG", "JPG", "JPEG", "BMP", "TIF", "TIFF", "DICOM", "DCM"]

    if request.method == "POST":
        mammogram_file = request.files.get("mammogram_file")
        filename = mammogram_file.filename if mammogram_file else ""

        if filename:
            flash(
                "Formulario recibido por el backend. La validacion y almacenamiento "
                "del archivo se implementaran en las siguientes issues.",
                "success",
            )
        else:
            flash(
                "Selecciona un archivo de mamografia antes de enviar el formulario.",
                "warning",
            )

        return redirect(url_for("upload.upload_mammogram"))

    return render_template("upload.html", accepted_formats=accepted_formats)
