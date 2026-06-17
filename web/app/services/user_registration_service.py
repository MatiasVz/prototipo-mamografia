import re
from dataclasses import dataclass, field

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..extensions import db
from ..models import User

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
MAX_NAME_LENGTH = 120
MAX_EMAIL_LENGTH = 255


@dataclass
class UserRegistrationResult:
    user: User | None = None
    errors: dict = field(default_factory=dict)

    @property
    def is_valid(self):
        return self.user is not None and not self.errors


def validate_registration(email, name, password, password_confirm):
    """Validate the registration fields without touching the database session."""
    errors = {}
    email_norm = User.normalize_email(email)
    clean_name = (name or "").strip()

    if not email_norm:
        errors["email"] = "El correo es obligatorio."
    elif not EMAIL_PATTERN.match(email_norm):
        errors["email"] = "Ingresa un correo electronico valido."
    elif len(email_norm) > MAX_EMAIL_LENGTH:
        errors["email"] = "El correo es demasiado largo."

    if clean_name and len(clean_name) > MAX_NAME_LENGTH:
        errors["name"] = "El nombre es demasiado largo."

    if not password:
        errors["password"] = "La contraseña es obligatoria."
    elif len(password) < MIN_PASSWORD_LENGTH:
        errors["password"] = (
            f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
        )
    elif password != password_confirm:
        errors["password_confirm"] = "Las contraseñas no coinciden."

    return errors, email_norm, clean_name


def register_user(email, name, password, password_confirm):
    """Validate and create a new user. Returns a UserRegistrationResult."""
    errors, email_norm, clean_name = validate_registration(
        email, name, password, password_confirm
    )

    if "email" not in errors and User.query.filter_by(email=email_norm).first():
        errors["email"] = "Ya existe una cuenta con este correo."

    if errors:
        return UserRegistrationResult(errors=errors)

    user = User(email=email_norm, name=clean_name or None)
    user.set_password(password)
    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        # Respaldo ante una condicion de carrera: la restriccion unica de la base
        # garantiza que no haya dos cuentas con el mismo correo.
        db.session.rollback()
        return UserRegistrationResult(
            errors={"email": "Ya existe una cuenta con este correo."}
        )
    except SQLAlchemyError:
        db.session.rollback()
        raise

    return UserRegistrationResult(user=user)
