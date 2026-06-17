from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..services.user_registration_service import register_user

auth_bp = Blueprint("auth", __name__, url_prefix="/cuenta")


@auth_bp.route("/registro", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "")
        name = request.form.get("name", "")
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        try:
            result = register_user(email, name, password, password_confirm)
        except SQLAlchemyError:
            db.session.rollback()
            flash("No se pudo completar el registro. Intenta nuevamente.", "error")
            return render_template(
                "auth/register.html",
                form={"email": email, "name": name},
                errors={},
            )

        if result.is_valid:
            flash("Cuenta creada correctamente. Ya puedes usar el prototipo.", "success")
            return redirect(url_for("main.index"))

        flash("Revisa los datos del formulario.", "error")
        return render_template(
            "auth/register.html",
            form={"email": email, "name": name},
            errors=result.errors,
        )

    return render_template("auth/register.html", form={}, errors={})
