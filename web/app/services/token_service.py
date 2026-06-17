import hashlib

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..extensions import db
from ..models import User

# Sal fija que aisla este tipo de token de cualquier otro firmado con la misma
# SECRET_KEY. Si en el futuro hay otros tokens (p. ej. verificacion de correo),
# cada uno usa su propia sal.
RESET_SALT = "password-reset"


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=RESET_SALT)


def _password_fingerprint(user):
    """Huella corta del hash de la contraseña actual.

    Se incrusta en el token para que, al cambiar la contraseña, los tokens
    emitidos antes dejen de ser validos (uso efectivamente unico).
    """
    raw = (user.password_hash or "").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def generate_password_reset_token(user):
    """Crear un token firmado y con caducidad para restablecer la contraseña."""
    payload = {"uid": user.id, "pw": _password_fingerprint(user)}
    return _serializer().dumps(payload)


def verify_password_reset_token(token, max_age_seconds):
    """Devolver el User del token si es valido y no expiro; en otro caso None.

    Es None cuando el token esta manipulado, expirado, el usuario ya no existe
    o la contraseña ya cambio desde que se emitio el token.
    """
    try:
        data = _serializer().loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None

    if not isinstance(data, dict):
        return None

    user = db.session.get(User, data.get("uid"))

    if user is None:
        return None

    if data.get("pw") != _password_fingerprint(user):
        return None

    return user
