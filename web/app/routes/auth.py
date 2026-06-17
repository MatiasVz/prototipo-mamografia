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
from ..models import User
from ..services.auth_service import get_current_user, login_user, logout_user
from ..services.user_registration_service import register_user

auth_bp = Blueprint("auth", __name__, url_prefix="/cuenta")


@auth_bp.app_context_processor
def inject_current_user():
    """Expose the authenticated user to every template (e.g. the nav bar)."""
    return {"current_user": get_current_user()}


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


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        user = User.query.filter_by(email=User.normalize_email(email)).first()

        if user is None or not user.check_password(password):
            # Mensaje generico a proposito: no revela si el correo existe o no.
            flash("Correo o contraseña incorrectos.", "error")
            return render_template("auth/login.html", form={"email": email})

        login_user(user)
        flash("Sesion iniciada correctamente.", "success")
        return redirect(url_for("upload.case_list"))

    return render_template("auth/login.html", form={})


@auth_bp.post("/logout")
def logout():
    logout_user()
    flash("Cerraste sesion correctamente.", "success")
    return redirect(url_for("main.index"))
