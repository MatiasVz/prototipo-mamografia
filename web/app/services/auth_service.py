from flask import session

from ..extensions import db
from ..models import User

SESSION_USER_KEY = "user_id"


def login_user(user):
    """Start a session for the given user using Flask's signed session cookie."""
    session[SESSION_USER_KEY] = user.id
    session.permanent = False


def logout_user():
    """Clear the authenticated user from the session."""
    session.pop(SESSION_USER_KEY, None)


def get_current_user():
    """Return the authenticated User, or None if there is no valid session."""
    user_id = session.get(SESSION_USER_KEY)

    if user_id is None:
        return None

    user = db.session.get(User, user_id)

    if user is None:
        # La cuenta ya no existe (p. ej. fue eliminada): limpiamos la sesion.
        session.pop(SESSION_USER_KEY, None)

    return user
