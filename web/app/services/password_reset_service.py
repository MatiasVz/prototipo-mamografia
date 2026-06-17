from dataclasses import dataclass, field

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import User
from .email_service import EmailDeliveryError, send_email
from .token_service import (
    generate_password_reset_token,
    verify_password_reset_token,
)
from .user_registration_service import validate_password

RESET_SUBJECT = "Recuperacion de contraseña"


def _default_token_max_age():
    return int(current_app.config.get("PASSWORD_RESET_TOKEN_MAX_AGE", 3600))


def _build_reset_email_body(user, reset_url, max_age_seconds):
    minutes = max(1, max_age_seconds // 60)
    greeting = f"Hola {user.name}," if user.name else "Hola,"
    return (
        f"{greeting}\n\n"
        "Recibimos una solicitud para restablecer la contraseña de tu cuenta "
        "en el Prototipo de Analisis Mamografico.\n\n"
        "Para definir una nueva contraseña, abre el siguiente enlace:\n"
        f"{reset_url}\n\n"
        f"El enlace caduca en {minutes} minutos y solo puede usarse una vez.\n\n"
        "Si no solicitaste este cambio, puedes ignorar este correo: tu "
        "contraseña actual seguira funcionando.\n"
    )


def request_password_reset(email, build_reset_url):
    """Enviar el correo de recuperacion si el correo corresponde a una cuenta.

    No revela si el correo existe o no (anti-enumeracion): la capa de ruta
    muestra siempre el mismo mensaje generico, exista o no la cuenta. Si el
    envio falla, se registra en el log y se eleva EmailDeliveryError para que
    la ruta lo gestione, sin filtrar la existencia de la cuenta al usuario.
    """
    user = User.query.filter_by(email=User.normalize_email(email)).first()

    if user is None:
        return

    token = generate_password_reset_token(user)
    reset_url = build_reset_url(token)
    max_age = _default_token_max_age()
    body = _build_reset_email_body(user, reset_url, max_age)

    try:
        send_email(user.email, RESET_SUBJECT, body)
    except EmailDeliveryError:
        current_app.logger.exception(
            "No se pudo enviar el correo de recuperacion al usuario id=%s", user.id
        )
        raise


def get_user_for_reset_token(token):
    """Devolver el User si el token es valido (para mostrar el formulario), o None."""
    return verify_password_reset_token(token, _default_token_max_age())


@dataclass
class PasswordResetResult:
    success: bool = False
    errors: dict = field(default_factory=dict)
    token_invalid: bool = False


def reset_password(token, password, password_confirm):
    """Validar el token y, si es valido, fijar la nueva contraseña del usuario."""
    user = verify_password_reset_token(token, _default_token_max_age())

    if user is None:
        return PasswordResetResult(token_invalid=True)

    errors = validate_password(password, password_confirm)
    if errors:
        return PasswordResetResult(errors=errors)

    user.set_password(password)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise

    return PasswordResetResult(success=True)
