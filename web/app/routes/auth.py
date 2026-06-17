from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import Case, User
from ..services.account_service import delete_account
from ..services.auth_service import (
    get_current_user,
    login_required,
    login_user,
    logout_user,
)
from ..services.email_service import EmailDeliveryError
from ..services.password_reset_service import (
    get_user_for_reset_token,
    request_password_reset,
    reset_password,
)
from ..services.user_registration_service import register_user

auth_bp = Blueprint("auth", __name__, url_prefix="/cuenta")

# Mensaje deliberadamente generico: se muestra exista o no la cuenta, para no
# revelar que correos estan registrados (anti-enumeracion).
RESET_REQUEST_NOTICE = (
    "Si el correo corresponde a una cuenta, te enviamos un enlace para "
    "restablecer la contraseña. Revisa tu bandeja de entrada."
)


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
    next_url = request.values.get("next", "")

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        user = User.query.filter_by(email=User.normalize_email(email)).first()

        if user is None or not user.check_password(password):
            # Mensaje generico a proposito: no revela si el correo existe o no.
            flash("Correo o contraseña incorrectos.", "error")
            return render_template(
                "auth/login.html", form={"email": email}, next_url=next_url
            )

        login_user(user)
        flash("Sesion iniciada correctamente.", "success")

        if _is_safe_next_url(next_url):
            return redirect(next_url)
        return redirect(url_for("upload.case_list"))

    return render_template("auth/login.html", form={}, next_url=next_url)


@auth_bp.post("/logout")
def logout():
    logout_user()
    flash("Cerraste sesion correctamente.", "success")
    return redirect(url_for("main.index"))


@auth_bp.get("/perfil")
@login_required
def account():
    user = get_current_user()
    case_count = Case.query.filter_by(user_id=user.id).count()
    member_since = (
        user.created_at.strftime("%d/%m/%Y") if user.created_at else None
    )

    return render_template(
        "auth/account.html",
        user=user,
        case_count=case_count,
        member_since=member_since,
    )


@auth_bp.route("/eliminar", methods=["GET", "POST"])
@login_required
def delete_account_view():
    user = get_current_user()

    if request.method == "POST":
        password = request.form.get("password", "")

        try:
            result = delete_account(
                user, password, current_app.config["UPLOAD_FOLDER"]
            )
        except SQLAlchemyError:
            db.session.rollback()
            flash("No se pudo eliminar la cuenta. Intenta nuevamente.", "error")
            return render_template("auth/delete_account.html", password_error=None)

        if result.password_invalid:
            return render_template(
                "auth/delete_account.html",
                password_error="Contraseña incorrecta.",
            )

        if result.orphaned_case_ids:
            # La cuenta y los registros si se eliminaron; solo quedaron archivos
            # sueltos en disco. Se avisa internamente sin alarmar al usuario.
            current_app.logger.warning(
                "Cuenta eliminada con archivos huerfanos en casos: %s",
                result.orphaned_case_ids,
            )

        logout_user()
        flash("Tu cuenta y todos tus casos se eliminaron definitivamente.", "success")
        return redirect(url_for("main.index"))

    return render_template("auth/delete_account.html", password_error=None)


@auth_bp.route("/recuperar", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "")

        def build_reset_url(token):
            return url_for("auth.reset_password_view", token=token, _external=True)

        try:
            request_password_reset(email, build_reset_url)
        except EmailDeliveryError:
            # El error ya quedo en el log. No revelamos si la cuenta existe.
            flash(
                "No pudimos enviar el correo en este momento. Intenta mas tarde.",
                "error",
            )
            return render_template("auth/forgot_password.html", form={"email": email})
        except SQLAlchemyError:
            db.session.rollback()
            flash("Ocurrio un error inesperado. Intenta nuevamente.", "error")
            return render_template("auth/forgot_password.html", form={"email": email})

        flash(RESET_REQUEST_NOTICE, "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form={})


@auth_bp.route("/restablecer", methods=["GET", "POST"])
def reset_password_view():
    token = request.values.get("token", "")

    if request.method == "POST":
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        try:
            result = reset_password(token, password, password_confirm)
        except SQLAlchemyError:
            db.session.rollback()
            flash("No se pudo actualizar la contraseña. Intenta nuevamente.", "error")
            return render_template("auth/reset_password.html", token=token, errors={})

        if result.token_invalid:
            flash(
                "El enlace no es valido o expiro. Solicita uno nuevo.",
                "error",
            )
            return redirect(url_for("auth.forgot_password"))

        if result.success:
            flash(
                "Contraseña actualizada. Ya puedes iniciar sesion.",
                "success",
            )
            return redirect(url_for("auth.login"))

        flash("Revisa los datos del formulario.", "error")
        return render_template(
            "auth/reset_password.html", token=token, errors=result.errors
        )

    # GET: validamos el token antes de mostrar el formulario.
    if get_user_for_reset_token(token) is None:
        flash("El enlace no es valido o expiro. Solicita uno nuevo.", "error")
        return redirect(url_for("auth.forgot_password"))

    return render_template("auth/reset_password.html", token=token, errors={})


def _is_safe_next_url(target):
    """Solo permite rutas internas relativas (evita open redirect a sitios externos)."""
    return bool(target) and target.startswith("/") and not target.startswith("//")
